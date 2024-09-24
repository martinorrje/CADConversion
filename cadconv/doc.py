import logging

from dataclasses import dataclass, field
from typing import Optional, Dict, List

import OCC
from OCC.Core.BinXCAFDrivers import binxcafdrivers_DefineFormat
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.IFSelect import (
    IFSelect_RetVoid,
    IFSelect_RetDone,
    IFSelect_RetError,
    IFSelect_RetFail,
    IFSelect_RetStop,
)
from OCC.Core.Quantity import Quantity_Color
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TCollection import TCollection_ExtendedString
from OCC.Core.TDF import TDF_LabelSequence, TDF_Label
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.XCAFApp import XCAFApp_Application_GetApplication
from OCC.Core.XCAFDoc import (
    XCAFDoc_DocumentTool_ShapeTool,
    XCAFDoc_DocumentTool_ColorTool,
    XCAFDoc_ColorSurf,
)

from .data import Joint, Part, Label
from .data.utils import Serializable

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())

IFSELECT = {
    IFSelect_RetVoid:  "IFSelect_RetVoid",
    IFSelect_RetDone:  "IFSelect_RetDone",
    IFSelect_RetError: "IFSelect_RetError",
    IFSelect_RetFail:  "IFSelect_RetFail",
    IFSelect_RetStop:  "IFSelect_RetStop",
}


@dataclass
class DocModel(Serializable):
    joints: Dict[str, Joint] = field(default_factory=dict)
    parts: Dict[str, Part] = field(default_factory=dict)
    labels: Dict[str, Label] = field(default_factory=dict)
    root_uid: Optional[str] = None

    def __post_init__(self):
        LOG.debug("(Post Dataclass Init) DocModel variables:", dir(self))

        LOG.debug("Creating doc and app")
        doc_format = TCollection_ExtendedString("BinXCAF")
        self.doc = TDocStd_Document(doc_format)
        self.app = XCAFApp_Application_GetApplication()
        self.app.NewDocument(doc_format, self.doc)
        binxcafdrivers_DefineFormat(self.app)

        self._uid_nextvalue = dict()

    def _gen_uid(self, entry):
        LOG.debug(f"Generating UID for entry \"{entry}\"")
        value = self._uid_nextvalue.get(entry, -1)
        value += 1
        self._uid_nextvalue[entry] = value
        return entry + "." + str(value)

    def uid_parents(self, uid) -> List[str]:
        """
        Returns a list of parents, lowest index being nearest parent and the
        highest index being the root uid.
        """
        parents = []
        label = self.labels[uid]
        while label.parent_uid != None:
            parents.append(label.parent_uid)
            label = self.labels[label.parent_uid]
        return parents

    def uid_children(self, uid) -> List[str]:
        """
        Returns a list of children uid's to the specified uid.
        """
        return [
            c_uid
            for c_uid, lbl in self.labels.items()
            if lbl.parent_uid == uid
        ]

    def load_step(self, path):
        LOG.debug(f"Loading STEP file from {path} into this DocModel")

        step_reader = STEPCAFControl_Reader()
        step_reader.SetColorMode(True)
        step_reader.SetLayerMode(True)
        step_reader.SetNameMode(True)
        step_reader.SetMatMode(True)

        status = step_reader.ReadFile(path)
        if status == IFSelect_RetDone:
            LOG.debug("Transferring doc to STEPCAFControl_Reader")
            step_reader.Transfer(self.doc)
            LOG.debug("Loading OK")
        else:
            msg = f"Received error code {status} ({IFSELECT[status]}) when loading STEP file from \"{path}\"."
            LOG.error(msg)
            raise RuntimeError(msg)

    def parse(self):
        LOG.debug("Generate the parts & labels dicts from document contents")

        shape_tool = XCAFDoc_DocumentTool_ShapeTool(self.doc.Main())
        color_tool = XCAFDoc_DocumentTool_ColorTool(self.doc.Main())

        LOG.debug("Find root label of self.doc")
        labels = TDF_LabelSequence()
        LOG.debug(f"Number of labels at doc root: {labels.Length()}")
        shape_tool.GetShapes(labels)
        root_label = labels.Value(1) # <TDF_Label>
        root_shape = TopoDS_Shape()  # <TopoDS_Shape>
        shape_tool.GetShape(root_label, root_shape)
        LOG.debug(f"Root Label: {root_label} (type: {type(root_label)})")
        LOG.debug(f"Root Shape: {root_shape} (type: {type(root_shape)})")

        LOG.debug("Get root label information")
        root_entry = root_label.EntryDumpToString()
        root_uid = self._gen_uid(root_entry)
        LOG.debug(f"Root Entry: {root_entry} | Root UID: {root_uid}")

        LOG.debug("Recording the Part Root UID")
        self.part_root_uid = root_uid

        self.labels[root_uid] = Label(
            entry = root_entry,
            name  = root_label.GetLabelName(),
            loc   = shape_tool.GetLocation(root_label),
            parent_uid      = None,
            is_assembly     = bool(shape_tool.IsAssembly(root_label)),
            is_simple_shape = bool(shape_tool.IsSimpleShape(root_label)),
        )
        LOG.debug(f"labels: {self.labels}")

        if not self.labels[root_uid].is_assembly:
            raise RuntimeError(f"root_label {self.labels[root_uid]} is not an assembly")

        stack = [(root_uid, root_label)]

        while len(stack) > 0:
            (uid, lbl) = stack.pop()
            LOG.debug(f"Handling {self.labels[uid]}")

            if self.labels[uid].is_assembly:
                LOG.debug("Fetching components from shape_tool")
                comps = TDF_LabelSequence()
                sub_children = False
                shape_tool.GetComponents(lbl, comps, sub_children)

                for j in range(comps.Length()):
                    LOG.debug(f"Component {j+1}")
                    c_label = comps.Value(j + 1)
                    c_entry = c_label.EntryDumpToString()
                    c_uid = self._gen_uid(c_entry)
                    ref_label = TDF_Label()
                    if not shape_tool.GetReferredShape(c_label, ref_label):
                        raise RuntimeError(f"Expected a referred shape label for \"{c_label.GetLabelName()}\"")

                    self.labels[c_uid] = Label(
                        entry = c_entry,
                        name  = c_label.GetLabelName(),
                        loc   = shape_tool.GetLocation(c_label),
                        ref_entry       = ref_label.EntryDumpToString(),
                        parent_uid      = uid,
                        is_assembly     = bool(shape_tool.IsAssembly(ref_label)),
                        is_simple_shape = bool(shape_tool.IsSimpleShape(ref_label)),
                    )
                    stack.append((c_uid, ref_label))
            elif self.labels[uid].is_simple_shape:
                LOG.debug("Extracting shape")
                shape = shape_tool.GetShape(lbl)

                # Multiply parent locations to arrive at an absolute location
                locs = [
                    self.labels[p_uid].loc
                    for p_uid in reversed([uid] + self.uid_parents(uid))
                ]
                abs_loc = locs[0]
                for p_loc in locs[1:]:
                    abs_loc = abs_loc.Multiplied(p_loc)

                part_shape = BRepBuilderAPI_Transform(shape, abs_loc.Transformation()).Shape()

                color = Quantity_Color()
                color_tool.GetColor(shape, XCAFDoc_ColorSurf, color)

                self.parts[uid] = Part(
                    shape = part_shape,
                    color = color,
                    name  = self.labels[uid].name,
                    loc   = abs_loc,
                )
            else:
                raise RuntimeError(f"Label {self.labels[uid].name} is neither shape or assembly")

        LOG.debug("parse() done")

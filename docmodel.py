import logging
import os

from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.Quantity import Quantity_Color
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TCollection import TCollection_ExtendedString
from OCC.Core.TDF import TDF_LabelSequence, TDF_Label
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.BinXCAFDrivers import binxcafdrivers_DefineFormat
from OCC.Core.XCAFApp import XCAFApp_Application_GetApplication
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.XCAFDoc import (
    XCAFDoc_DocumentTool_ShapeTool,
    XCAFDoc_DocumentTool_ColorTool,
    XCAFDoc_ColorSurf,
)
from PyQt5 import QtWidgets

from structures import Part

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # set to DEBUG | INFO | ERROR


def create_doc():
    doc_format = "BinXCAF"
    doc = TDocStd_Document(TCollection_ExtendedString(doc_format))
    app = XCAFApp_Application_GetApplication()
    app.NewDocument(TCollection_ExtendedString(doc_format), doc)
    binxcafdrivers_DefineFormat(app)
    return doc, app


class DocModel:
    def __init__(self):
        self.doc, self.app = create_doc()

        # Used by redraw()
        self.part_dict = {}  # {uid : Part}
        # Used to construct tree_view and access labels
        # {uid : {keys : .'entry', 'name', 'parent_uid', 'ref_entry', 'is_assembly'}}
        self.label_dict = {}
        self._share_dict = {}
        self.parent_dict = {}             # For each assembly with uid, parent_dict[uid] contains uids of all children
        self.parent_uid_stack = []  # uid of parent lineage, topmost first
        self.assembly_entry_stack = []  # entries of containing assemblies, immediate last
        self.assembly_loc_stack = []  # applicable <TopLoc_Location> locations
        self.root_uid = None
        self.root_shape = None

    def get_uid_from_entry(self, entry):
        if entry in self._share_dict:
            value = self._share_dict[entry]
        else:
            value = -1
        value += 1
        self._share_dict[entry] = value
        return entry + '.' + str(value)

    def parse_doc(self):
        """Generate new part_dict & label_dict from self.doc

        part_dict (dict of dicts) is used primarily for 3D display
        There is a one-to-one correspondence between each 'display-able'
        part (instance) and each item in part_dict

        part_dict = {uid:  {'shape': ,
                            'name': ,
                            'color': ,
                            'loc': }}

        label_dict (dict of dicts) is used primarily for tree view display
        There is a one-to-one correspondence between each item in the
        tree view and each item in label_dict

        label_dict = {uid: {'entry': ,
                            'name': ,
                            'parent_uid': ,
                            'ref_entry': ,
                            'is_assembly': }}
        """
        self._share_dict = {'0:1:1': 0}  # {entry : serial_number}
        self.part_dict = {}
        self.label_dict = {}
        # Temporary use during unpacking
        self.parent_uid_stack = []  # uid of parent (topmost first)
        self.assembly_entry_stack = ['0:1:1']  # [entries of containing assemblies]
        self.assembly_loc_stack = []  # applicable <TopLoc_Location> locations

        shape_tool = XCAFDoc_DocumentTool_ShapeTool(self.doc.Main())
        color_tool = XCAFDoc_DocumentTool_ColorTool(self.doc.Main())

        # Find root label of self.doc
        labels = TDF_LabelSequence()
        number_of_labels = labels.Length()
        logger.debug(f"Number of labels at doc root: {number_of_labels}")
        shape_tool.GetShapes(labels)
        root_label = labels.Value(1)
        self.root_shape = TopoDS_Shape()
        shape_tool.GetShape(root_label, self.root_shape)


        # Get root label information
        # The first label at root holds an assembly, it is the Top Assembly.
        # Through this label, the entire assembly is accessible.
        # There is no need to explicitly examine other labels at root.
        # Also, the first label at root (Top Assembly) is the only label
        # at root represented in the tree view (in label_dict)
        root_name = root_label.GetLabelName()
        root_entry = root_label.EntryDumpToString()
        root_uid = self.get_uid_from_entry(root_entry)
        loc = shape_tool.GetLocation(root_label)  # <TopLoc_Location>
        self.assembly_loc_stack.append(loc)
        self.assembly_entry_stack.append(root_entry)
        self.label_dict = {root_uid: {'entry': root_entry, 'name': root_name,
                                      'parent_uid': None, 'ref_entry': None,
                                      'is_assembly': True}}
        self.parent_uid_stack.append(root_uid)
        self.root_uid = root_uid
        top_comps = TDF_LabelSequence()  # Components of Top Assembly
        sub_children = False
        __ = shape_tool.GetComponents(root_label, top_comps, sub_children)
        if top_comps.Length():  # if root_label is_assembly:
            logger.debug("")
            logger.debug("Parsing components of label entry %s)", root_entry)
            self.parse_components(top_comps, shape_tool, color_tool)
        else:
            print("Something went wrong while parsing document.")

    def parse_components(self, comps, shape_tool, color_tool):
        """Parse components from comps (LabelSequence).

        Components of an assembly are, by definition, references which
        refer to either a simple shape or a compound shape (an assembly).
        Components are essentially 'instances' of a referred shape or
        assembly and carry a location vector specifying the location of
        the referred shape or assembly.
        The root label and all referred labels have Depth = 3
        All component labels (references) have Depth = 4
        """

        for j in range(comps.Length()):
            logger.debug("Assembly_entry_stack: %s", self.assembly_entry_stack)
            logger.debug("loop %i of %i", j + 1, comps.Length())
            c_label = comps.Value(j + 1)  # component label <class 'TDF_Label'>
            c_name = c_label.GetLabelName()
            c_entry = c_label.EntryDumpToString()
            c_uid = self.get_uid_from_entry(c_entry)
            c_shape = shape_tool.GetShape(c_label)
            logger.debug("Component number %i", j + 1)
            logger.debug("Component name: %s", c_name)
            logger.debug("Component entry: %s", c_entry)
            ref_label = TDF_Label()  # label of referred shape (or assembly)
            is_ref = shape_tool.GetReferredShape(c_label, ref_label)
            if is_ref:  # I think all components are references
                ref_name = ref_label.GetLabelName()
                ref_shape = shape_tool.GetShape(ref_label)
                ref_entry = ref_label.EntryDumpToString()
                self.label_dict[c_uid] = {'entry': c_entry,
                                          'name': c_name,
                                          'parent_uid': self.parent_uid_stack[-1],
                                          'ref_entry': ref_entry}
                if self.parent_uid_stack[-1] not in self.parent_dict:
                    self.parent_dict[self.parent_uid_stack[-1]] = []
                self.parent_dict[self.parent_uid_stack[-1]].append(c_uid)
                if shape_tool.IsSimpleShape(ref_label):
                    self.label_dict[c_uid].update({'is_assembly': False})
                    temp_assembly_loc_stack = list(self.assembly_loc_stack)
                    # Multiply locations in stack sequentially to a result
                    if len(temp_assembly_loc_stack) > 1:
                        res_loc = temp_assembly_loc_stack.pop(0)
                        for loc in temp_assembly_loc_stack:
                            res_loc = res_loc.Multiplied(loc)
                        display_shape = BRepBuilderAPI_Transform(
                            c_shape, res_loc.Transformation()).Shape()
                    elif len(temp_assembly_loc_stack) == 1:
                        res_loc = temp_assembly_loc_stack.pop()
                        display_shape = BRepBuilderAPI_Transform(
                            c_shape, res_loc.Transformation()).Shape()
                    else:
                        res_loc = None
                    # It is possible for this component to both specify a
                    # location 'c_loc' and refer directly to a top level shape.
                    # If this component *does* specify a location 'c_loc',
                    # it will be applied to the referred shape without being
                    # included in temp_assembly_loc_stack. But in order to keep
                    # track of the total location from the root shape to the
                    # instance, it needs to be accounted for (by mutiplying
                    # res_loc by it) before saving it to part_dict.
                    c_loc = shape_tool.GetLocation(c_label)
                    if c_loc:
                        loc = res_loc.Multiplied(c_loc)
                    color = Quantity_Color()
                    color_tool.GetColor(ref_shape, XCAFDoc_ColorSurf, color)
                    self.part_dict[c_uid] = Part(shape=display_shape,
                                                 color=color,
                                                 name=c_name,
                                                 loc=loc)
                elif shape_tool.IsAssembly(ref_label):
                    self.label_dict[c_uid].update({'is_assembly': True})
                    logger.debug("Referred item is an Assembly")
                    # Location vector is carried by component
                    a_loc = shape_tool.GetLocation(c_label)
                    # store inverted location transform in label_dict for this assembly
                    self.assembly_loc_stack.append(a_loc)
                    self.assembly_entry_stack.append(ref_entry)
                    self.parent_uid_stack.append(c_uid)
                    r_comps = TDF_LabelSequence()  # Components of Assy
                    sub_children = False
                    is_assembly = shape_tool.GetComponents(
                        ref_label, r_comps, sub_children)
                    logger.debug("Assembly name: %s", ref_name)
                    logger.debug("Is Assembly? %s", is_assembly)
                    logger.debug("Number of components: %s", r_comps.Length())
                    if r_comps.Length():
                        logger.debug("")
                        logger.debug(
                            "Parsing components of label entry %s)", ref_entry)
                        self.parse_components(r_comps, shape_tool, color_tool)
            else:
                print(f"Oops! All components are *not* references {c_uid}")
        self.assembly_entry_stack.pop()
        self.assembly_loc_stack.pop()
        self.parent_uid_stack.pop()

def _load_step():
    """Allow user to select step file to load, create doc and app,

    transfer step data to doc, return step_file_name, doc, app"""

    prompt = 'Select STEP file to import'
    f_path, __ = QtWidgets.QFileDialog.getOpenFileName(
        None, prompt, './', "STEP files (*.stp *.STP *.step)")
    base = os.path.basename(f_path)  # f_name.ext
    step_file_name, ext = os.path.splitext(base)
    logger.debug("Load file name: %s", f_path)
    if not f_path:
        print("Load step cancelled")
        return

    # Create a new instance of DocModel for the step file
    doc, app = create_doc()

    # Create and prepare step reader
    step_reader = STEPCAFControl_Reader()
    step_reader.SetColorMode(True)
    step_reader.SetLayerMode(True)
    step_reader.SetNameMode(True)
    step_reader.SetMatMode(True)

    status = step_reader.ReadFile(f_path)
    if status == IFSelect_RetDone:
        logger.info("Transfer doc to STEPCAFControl_Reader")
        step_reader.Transfer(doc)
    return step_file_name, doc, app


def load_step_at_top(dm):
    """Get OCAF document from STEP file and assign it directly to dm.doc.

    This works as a surrogate for loading a CAD project that has previously
    been saved as a STEP file."""

    try:
        f_name, doc, app = _load_step()
    except TypeError as e:
        print("Load step cancelled")
        return
    logger.info("Transfer temp_doc to STEPCAFControl_Reader")
    dm.doc = doc
    dm.app = app
    dm.parse_doc()

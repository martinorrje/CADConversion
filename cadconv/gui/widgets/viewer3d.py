import logging

from OCC.Core.AIS import AIS_Shape, AIS_Trihedron
from OCC.Core.Quantity import (
    Quantity_Color,
    Quantity_NOC_RED,
    Quantity_NOC_GREEN,
    Quantity_NOC_BLUE,
    Quantity_TOC_RGB,
    Quantity_NOC_GRAY,
)

import OCC.Display.backend
used_backend = OCC.Display.backend.load_backend()
from OCC.Display import qtDisplay

from ...doc import DocModel

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class Viewer3D(qtDisplay.qtViewer3d):
    def __init__(self, parent):
        super().__init__(parent)
        LOG.warning("TODO: Implement the Viewer3D")
        self.hidden_parts = set()
        self.shapes = {}

    def redraw(self, dm: DocModel):
        """hide_list
        Erase & redraw all parts except those in hide_list.
        """
        context = self._display.Context
        #if not self.registered_callback:
        self._display.SetSelectionModeNeutral()
        context.SetAutoActivateSelection(True)

        context.RemoveAll(True)

        for uid in dm.parts.keys():
            self.draw_part(dm, uid)

        #for uid in self.joint_manager.joint_dict:
        #    if uid not in self.:
        #        self.draw_joint(uid)
        #if self.display_origin:
        #    self.display_datum_origin()

        context.UpdateCurrentViewer()

    def draw_part(self, dm: DocModel, uid: str):
        """Draw the part (shape) with uid."""
        context = self._display.Context
        part = dm.parts[uid]

        ais_shape = AIS_Shape(part.shape)
        self.shapes[uid] = {
            "ais_shape": ais_shape,
            "part": part,
        }

        context.SetColor(ais_shape, part.color, False)
        drawer = ais_shape.DynamicHilightAttributes()
        context.HilightWithColor(ais_shape, drawer, False)
        context.Display(ais_shape, False)

    def highlight_part(self, uid: str):
        LOG.debug(f"highligting {uid}")
        context = self._display.Context

        for _, shape in self.shapes.items():
            context.SetColor(shape["ais_shape"], shape["part"].color, False)

        shape = self.shapes.get(uid)
        if shape is not None:
            (ais_shape, part) = (shape["ais_shape"], shape["part"])
            # TODO: Figure out what to do...
            #(r, g, b) = part.color.Values(0)
            #r += (1.0 - r)*0.25
            #g += (1.0 - g)*0.25
            #b += (1.0 - b)*0.50
            (r, g, b) = (0.75, 0.75, 1.0)
            hl_color = Quantity_Color(r, g, b, Quantity_TOC_RGB)
            context.SetColor(ais_shape, hl_color, False)

        context.UpdateCurrentViewer()

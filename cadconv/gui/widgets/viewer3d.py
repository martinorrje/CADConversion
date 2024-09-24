import logging

from OCC.Core.AIS import AIS_Shape, AIS_Trihedron

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
        context.SetColor(ais_shape, part.color, False)
        drawer = ais_shape.DynamicHilightAttributes()
        context.HilightWithColor(ais_shape, drawer, False)
        context.Display(ais_shape, False)

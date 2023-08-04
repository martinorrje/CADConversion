import logging

from OCC.Core.AIS import AIS_Line, AIS_Trihedron
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
from OCC.Core.Geom import Geom_Line, Geom_Axis2Placement
from OCC.Core.GeomAbs import GeomAbs_Circle
from OCC.Core.Prs3d import Prs3d_DatumParts_XAxis, Prs3d_DatumParts_YAxis, Prs3d_DatumParts_ZAxis
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB, Quantity_NOC_RED, Quantity_NOC_GREEN, Quantity_NOC_BLUE
from OCC.Core.TopAbs import TopAbs_SHAPE, TopAbs_VERTEX, TopAbs_EDGE, TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import TopoDS_Vertex, TopoDS_Edge, TopoDS_Face, TopoDS_Shape
from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Ax1
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

from mainwindow import dm
from structures import Joint
from uiwidgets import MaterialDialog


class MaterialManager:
    def __init__(self, parent):
        self.parent = parent
        self.change_material_group = MaterialDialog(parent)
        self.change_material_group.hide()
        self.change_material_uids = []

    def change_material_window(self):
        """Change the density of a component"""
        self.change_material_uids = [uid for uid in self.parent.items_clicked_uid if uid in dm.label_dict]
        if self.change_material_uids:
            self.change_material_group.show()

    def finish_material_selection(self):
        """Update the densities of all selected components according to the specified mass or density"""
        if self.change_material_group.select_density.currentText() != 'Custom':
            for uid in self.change_material_uids:
                self.change_material_preselected_density(uid)
        elif self.change_material_group.input_mass_option.text() != '':
            for uid in self.change_material_uids:
                self.change_material_defined_mass(uid)
        elif self.change_material_group.input_density_option.text() != '':
            for uid in self.change_material_uids:
                self.change_material_defined_density(uid)
        self.change_material_group.reset()
        self.parent.canvas._display.Context.UpdateCurrentViewer()

    def change_material_preselected_density(self, uid):
        """The user chose a material from the QComboBox"""
        self._change_material(uid, density=
        self.change_material_group.MATERIALS[self.change_material_group.select_density.currentText()])

    def change_material_defined_density(self, uid):
        """The user specified a custom density"""
        self._change_material(uid, density=float(self.change_material_group.input_density_option.text()))

    def change_material_defined_mass(self, uid):
        """The user specified a custom mass"""
        if dm.label_dict[uid]["is_assembly"] is False:
            dm.part_dict[uid].mass = float(self.change_material_group.input_mass_option.text())
            self._update_color_and_redraw(uid)
        else:
            for child_uid in dm.parent_dict[uid]:
                self.change_material_defined_mass(child_uid)

    def _change_material(self, uid, density):
        if dm.label_dict[uid]["is_assembly"] is False:
            dm.part_dict[uid].density = density
            self._update_color_and_redraw(uid)
        else:
            for child_uid in dm.parent_dict[uid]:
                self._change_material(child_uid, density)

    def _update_color_and_redraw(self, uid):
        old_color = dm.part_dict[uid].color
        new_color = Quantity_Color(min(old_color.Red() + 0.1, 1.0), old_color.Green(),
                                   old_color.Blue(), Quantity_TOC_RGB)
        dm.part_dict[uid].color = new_color
        self.parent.redraw_shape(uid)


class JointManager:
    # TODO: Add so that you can select joints in the tree view and edit them
    def __init__(self, canvas, clear_callback, joint_selection_widget):
        self.canvas = canvas
        self.joint_selection_widget = joint_selection_widget
        self.clear_callback = clear_callback

        self.joint_dict = {}
        self.current_joint_uid = 0
        self.current_point_number = 0
        self.first_component = None
        self.second_component = None
        self.parent_uid = None
        self.child_uid = None
        self.joint_origin = None
        self.joint_axis = None
        self.joint_origin_trihedron = None
        self.ais_axis = None
        self.joint_type = None
        self.joint_friction = None
        self.editing_joint = False
        self.finished_joint = False

    def select_first_component(self, register_callback):
        """Select the first component for the current joint"""
        if self.current_point_number == 2:
            return
        self.current_point_number = 1
        self.canvas._display.SetSelectionModeNeutral()
        self.canvas._display.SetSelectionMode(TopAbs_SHAPE)
        self.first_component = None
        if self.second_component == None:
            self.joint_selection_widget.select_point2_button.setText('Select component 2')
        self.joint_selection_widget.select_point1_button.setText('Selecting component 1...')
        register_callback(self.joint_callback)

    def select_second_component(self, register_callback):
        """Select the second component for the current joint"""
        if self.current_point_number == 1:
            return
        self.current_point_number = 2
        self.canvas._display.SetSelectionModeNeutral()
        self.canvas._display.SetSelectionMode(TopAbs_SHAPE)
        self.second_component = None
        if self.first_component == None:
            self.joint_selection_widget.select_point1_button.setText('Select component 1')
        self.joint_selection_widget.select_point2_button.setText('Selecting component 2...')
        register_callback(self.joint_callback)

    def select_origin(self, register_callback):
        """Select the origin for the current joint"""
        if not self.first_component or not self.second_component:
            self.joint_selection_widget.select_both_components_popup.exec_()
            return
        if self.joint_origin_trihedron is not None:
            self.canvas._display.Context.Erase(self.joint_origin_trihedron, True)
        self.joint_selection_widget.select_origin_button.setText('Selecting joint origin...')
        self.canvas._display.SetSelectionMode(TopAbs_VERTEX)
        self.canvas._display.SetSelectionMode(TopAbs_EDGE)
        self.canvas._display.SetSelectionMode(TopAbs_FACE)
        register_callback(self.origin_callback)
        self.canvas.start_displaying_origin()

    def submit_axis(self):
        """Register the axis chosen by the user in the joint selection line edits"""
        if self.joint_origin is None:
            self.joint_selection_widget.select_origin_popup.exec_()
            return
        try:
            x_dir = float(self.joint_selection_widget.line_edit_x.text())
            y_dir = float(self.joint_selection_widget.line_edit_y.text())
            z_dir = float(self.joint_selection_widget.line_edit_z.text())
        except ValueError:
            logger.log(logging.ERROR, "All axis directions have not been inputted")
            return
        # If an axis was already submitted for this joint, remove it
        if self.ais_axis is not None:
            self.canvas._display.Context.Remove(self.ais_axis, False)
        self.joint_axis = [x_dir, y_dir, z_dir]
        origin = gp_Pnt(self.joint_origin[0], self.joint_origin[1], self.joint_origin[2])
        dir = gp_Dir(x_dir, y_dir, z_dir)
        axis = gp_Ax1(origin, dir)
        axis_line = Geom_Line(axis)
        self.ais_axis = AIS_Line(axis_line)
        self.canvas._display.Context.Display(self.ais_axis, True)

    def submit_friction(self):
        """Register the friction for the joint, specified in the friction line edit"""
        try:
            friction = float(self.joint_selection_widget.friction_selection.text())
        except ValueError:
            return
        self.joint_friction = friction

    def mark_joint_origin(self, origin, loc=None):
        """Place a trihedron at the location of the marked joint origin"""
        if loc is not None:
            origin = loc.Location()
        self.joint_selection_widget.select_origin_button.setText(
            f"Joint origin: ({round(origin.X(), 2)}, {round(origin.Y(), 2)}, {round(origin.Z(), 2)})")
        self.joint_origin = [origin.X(), origin.Y(), origin.Z()]
        self.display_joint_origin_trihedron(loc)

    def origin_callback(self, feature, *args):
        """Called after the user has selected a joint origin"""
        if len(feature) == 1 and isinstance(feature[0], TopoDS_Vertex):
            _vertex = BRep_Tool.Pnt(feature[0])
            self.mark_joint_origin(_vertex)
        elif len(feature) == 1 and isinstance(feature[0], TopoDS_Edge):
            # First check if the edge is a circular feature
            curve = BRepAdaptor_Curve(feature[0])  # Retrieve the curve from the edge
            if curve.GetType() == GeomAbs_Circle:  # Check if the curve represents a circle
                # The shape that is hovered over is a circular feature, retrieve its center
                circle_center = curve.Circle().Location()
                self.mark_joint_origin(circle_center)
            elif self.canvas.edge_snap is not None:
                self.mark_joint_origin(self.canvas.edge_snap)
        elif len(feature) == 1 and isinstance(feature[0],
                                              TopoDS_Face) and self.canvas.face_snap_orientation is not None:
            self.mark_joint_origin(None, self.canvas.face_snap_orientation)
        else:
            self.joint_selection_widget.select_origin_button.setText("Select origin")

        self.clear_callback()
        self.canvas.stop_displaying_origin()

    def display_joint_origin_trihedron(self, loc=None):
        """Place a trihedron at the location of the selected joint origin"""
        if self.joint_origin is None:
            return
        dir = gp_Dir(0, 0, 1)
        x_dir = gp_Dir(1, 0, 0)
        if loc is None:
            loc = Geom_Axis2Placement(gp_Pnt(self.joint_origin[0], self.joint_origin[1], self.joint_origin[2]), dir,
                                      x_dir)
        self.joint_origin_trihedron = AIS_Trihedron(loc)
        self.joint_origin_trihedron.SetDrawArrows(True)
        self.joint_origin_trihedron.SetSize(5)
        self.joint_origin_trihedron.SetDatumPartColor(Prs3d_DatumParts_XAxis, Quantity_Color(Quantity_NOC_RED))
        self.joint_origin_trihedron.SetDatumPartColor(Prs3d_DatumParts_YAxis, Quantity_Color(Quantity_NOC_GREEN))
        self.joint_origin_trihedron.SetDatumPartColor(Prs3d_DatumParts_ZAxis, Quantity_Color(Quantity_NOC_BLUE))
        self.canvas._display.Context.Display(self.joint_origin_trihedron, False)
        self.canvas._display.Context.Deactivate(self.joint_origin_trihedron)

    def create_joint(self, joint_view_root, tree_view, joint_selection_dock_widget):
        """Creates a joint and adds it to joint_dict. Called after the user presses the "create joint" button in the
        joint selection widget"""
        self.joint_type = self.joint_selection_widget.joint_type_selection.currentText()
        if self.first_component is None or self.second_component is None or \
                ((self.joint_type == 'Revolute' or self.joint_type == 'Prismatic') and self.joint_axis is None) or \
                self.joint_origin is None:
            self.joint_selection_widget.select_everything_popup.exec_()
            return
        if self.first_component == self.second_component:
            self.joint_selection_widget.same_components_popup.exec_()
            return

        item = QtWidgets.QTreeWidgetItem(joint_view_root, [f"{self.first_component} to {self.second_component}",
                                                           f"joint_{self.current_joint_uid}"])
        item.setFlags(item.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
        item.setCheckState(0, Qt.Checked)
        tree_view.expandItem(item)
        self.add_joint_to_dict()

        self.clear_joint_parameters()

        self.finished_joint = True

        joint_selection_dock_widget.hide()

    def joint_type_changed(self):
        """Called after the joint type has been changed, and updates the ability to select axis and friction according
        to whether the new joint type is "Fixed" or not."""
        joint_type = self.joint_selection_widget.joint_type_selection.currentIndex()
        if joint_type == 2:
            if self.ais_axis is not None:
                self.canvas._display.Context.Erase(self.ais_axis, True)
            if self.joint_origin_trihedron is not None:
                self.canvas._display.Context.Erase(self.ais_axis, True)
            self.joint_selection_widget.clear_axis_line_edits()
            self.joint_selection_widget.clear_friction_line_edit()
            self.joint_selection_widget.set_line_edits(False)
        elif joint_type == 0 or joint_type == 1:
            self.joint_selection_widget.set_line_edits(True)

    def add_joint_to_dict(self):
        self.joint_dict[f"joint_{self.current_joint_uid}"] = Joint(first_component=self.first_component,
                                                                   second_component=self.second_component,
                                                                   parent_uid=self.parent_uid,
                                                                   child_uid=self.child_uid,
                                                                   origin=self.joint_origin,
                                                                   axis=self.joint_axis,
                                                                   center_trihedron=self.joint_origin_trihedron,
                                                                   axis_line=self.ais_axis,
                                                                   joint_type=self.joint_type,
                                                                   joint_friction=self.joint_friction if
                                                                   self.joint_friction is not None else 0)
        self.current_joint_uid += 1

    def joint_callback(self, shape, *args):
        """Called when either the button to select either the first or the second component for the joint is pressed."""
        if len(shape) == 1 and isinstance(shape[0], TopoDS_Shape):
            if self.current_point_number == 1:
                self.parent_uid, self.first_component = self.get_component_name(shape[0])
                self.joint_selection_widget.select_point1_button.setText(f'{self.first_component} selected')
            elif self.current_point_number == 2:
                self.child_uid, self.second_component = self.get_component_name(shape[0])
                self.joint_selection_widget.select_point2_button.setText(f'{self.second_component} selected')
            self.clear_callback()
            self.current_point_number = 0

    def cancel_component_selection(self):
        """Called when the visibility of the joint selection widget is changed. This can happen when:
            * The user is finished editing the joint, in which case self.editing_joint is True and self.finished_joint
              is True.
            * The user cancelled editing a joint, in which case self.editing_joint is True and self.finished_joint is
              False.
            * The user pressed "Add joint" in the menu bar to create a new joint, in which case self.editing_joint is
              False (and self.finished_joint is also False).
        """
        self.canvas._display.SetSelectionModeNeutral()
        self.canvas._display.SetSelectionMode(TopAbs_SHAPE)

        if not self.editing_joint:
            self.editing_joint = True
            return

        self.first_component = None
        self.second_component = None
        self.joint_selection_widget.clear_widgets()

        if not self.finished_joint:
            context = self.canvas._display.Context
            if self.ais_axis is not None:
                context.Erase(self.ais_axis, False)
            if self.joint_origin_trihedron is not None:
                context.Erase(self.joint_origin_trihedron, False)
            self.clear_joint_parameters()
            context.UpdateCurrentViewer()

        self.editing_joint = False
        self.finished_joint = False

    def clear_joint_parameters(self):
        self.parent_uid = None
        self.child_uid = None
        self.joint_origin = None
        self.joint_axis = None
        self.joint_origin_trihedron = None
        self.ais_axis = None
        self.joint_type = None
        self.joint_friction = None

    def get_component_name(self, solid_shape):
        explorer = TopExp_Explorer()
        for uid, part in dm.part_dict.items():
            explorer.Init(part.shape, TopAbs_SHAPE)
            shape = explorer.Current()
            if shape.IsEqual(solid_shape):
                return uid, part.name
        return None, None

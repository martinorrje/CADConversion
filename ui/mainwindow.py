from PyQt5.QtCore import Qt
from PyQt5 import QtWidgets

from OCC.Core.AIS import AIS_Shape, AIS_Trihedron
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.GeomLProp import GeomLProp_SLProps
from OCC.Core.Prs3d import Prs3d_DatumParts_XAxis, Prs3d_DatumParts_YAxis, Prs3d_DatumParts_ZAxis
from OCC.Core.BRep import BRep_Tool, BRep_Builder
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCC.Core.Geom import Geom_Axis2Placement
from OCC.Core.GeomAbs import GeomAbs_Circle
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import topods_Edge, topods_Vertex, TopoDS_Compound, topods_Face
from OCC.Core.TopAbs import TopAbs_VERTEX, TopAbs_EDGE, TopAbs_FACE
from OCC.Core.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCC.Core.Quantity import Quantity_Color, Quantity_NOC_RED, Quantity_NOC_GREEN, Quantity_NOC_BLUE, \
    Quantity_TOC_RGB, Quantity_NOC_GRAY
from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Lin, gp_Trsf

from model.docmodel import DocModel

import OCC.Display.backend
import OCC.Display.OCCViewer

used_backend = OCC.Display.backend.load_backend()
dm = DocModel()

from model.structures import Part
from .mainwindow_managers import MaterialManager, JointManager
from .uiwidgets import TreeView, JointSelectionWidget

from OCC.Display import qtDisplay
from OCC import VERSION


print(f"OCC Version {VERSION}")


class SnappingLogic:
    def __init__(self, display):
        self._display = display

    def snap_to_circular_edge(self, curve):
        """Returns the center of the selected circle, and returns it as a gp_Pnt"""
        circle_center = curve.Circle().Location()
        x, y, z = circle_center.Coord()
        return gp_Pnt(x, y, z)

    def snap_to_edge(self, evt, shape):
        """Returns the location of the closest position on the edge represented by shape, when measured from the mouse
        pointer position. Creates a ray from the camera position to the mouse pointer in 3D space. Then calculates the
        point on the edge that is closest to this ray, and returns this point as a gp_Pnt"""
        x, y, z, vx, vy, vz = self._display.View.ConvertWithProj(evt.x(), evt.y())
        ray_start = gp_Pnt(x, y, z)
        ray_dir = gp_Dir(vx, vy, vz)
        ray_line = gp_Lin(ray_start, ray_dir)
        edge = topods_Edge(shape)
        ray_edge = BRepBuilderAPI_MakeEdge(ray_line).Edge()
        extrema = BRepExtrema_DistShapeShape(edge, ray_edge)
        extrema.Perform()
        edge_snap = None
        if extrema.IsDone() and extrema.NbSolution() > 0:
            x, y, z = extrema.PointOnShape1(1).Coord()
            edge_snap = gp_Pnt(x, y, z)
        return edge_snap

    def snap_to_vertex(self, shape):
        """Returns the center position of the vertex that is being hovered over, as a gp_Pnt"""
        vertex = topods_Vertex(shape)
        pnt = BRep_Tool().Pnt(vertex)
        return pnt

    def snap_to_face(self, evt, shape):
        """Returns a Geom_Axis2Placement object representing a right-handed system coordinate system with its
        z-axis pointing out from the face. First creates a ray from the camera position to the mouse position in 3D
        space, and calculates the position on the face that is closest to this ray using get_face_line_intersection
        method."""
        face = topods_Face(shape)
        x, y, z, vx, vy, vz = self._display.View.ConvertWithProj(evt.x(), evt.y())
        ray_start = gp_Pnt(x, y, z)
        ray_dir = gp_Dir(vx, vy, vz)
        ray_line = gp_Lin(ray_start, ray_dir)
        return self.get_face_line_intersection(face, ray_line)

    def get_face_line_intersection(self, face, line):
        """Returns a right-handed coordinate system with center point at the point at the face that is closest to the
        line, and with orientation defined by its z-axis normal to the face."""
        intsec = IntCurvesFace_ShapeIntersector()
        intsec.Load(face, 1e-7)  # Use a numerical tolerance value, adjust as needed
        intsec.Perform(line, 0.0, float("+inf"))
        if intsec.IsDone() and intsec.NbPnt() > 0:
            x, y, z = intsec.Pnt(1).Coord()
            u = intsec.UParameter(1)
            v = intsec.VParameter(1)
            surf = BRep_Tool.Surface(face)
            props = GeomLProp_SLProps(surf, u, v, 1, 0.0)  # 1 is the continuity level, 0.0 is the tolerance
            if props.IsNormalDefined():
                normal, normal_dir = self.get_face_surface_orientation(props, line.Direction())
                return Geom_Axis2Placement(gp_Pnt(x, y, z), normal, normal_dir)

    def get_face_surface_orientation(self, props, view_dir):
        """Retrieves the face's normal and tangent at this point, and returns these two vectors """
        normal = props.Normal()  # Get the normal in global coordinate system
        normal_dir = gp_Dir()
        dot_product = normal.Dot(view_dir)
        if dot_product > 0:
            normal.Reverse()
        if props.IsTangentUDefined():
            props.TangentU(normal_dir)  # Get the U tangential direction
        else:
            raise Exception("TangentU not defined")  # Handle this situation as needed
        return normal, normal_dir


class OriginViewer3d(qtDisplay.qtViewer3d):
    def __init__(self, parent=None):
        super(OriginViewer3d, self).__init__(parent)

        self.dir = gp_Dir(0, 0, 1)
        self.x_dir = gp_Dir(1, 0, 0)
        loc = Geom_Axis2Placement(gp_Pnt(0, 0, 0), self.dir, self.x_dir)

        self.edge_snap = None
        self.face_snap = None
        self.face_snap_orientation = None

        self.trihedron = AIS_Trihedron(loc)
        self.init_trihedron()

        self.snapper = SnappingLogic(self._display)

    def init_trihedron(self):
        """Function to specify attributes of the trihedron"""
        self.trihedron.SetDrawArrows(True)
        self.trihedron.SetSize(5)
        self.trihedron.SetDatumPartColor(Prs3d_DatumParts_XAxis, Quantity_Color(Quantity_NOC_RED))
        self.trihedron.SetDatumPartColor(Prs3d_DatumParts_YAxis, Quantity_Color(Quantity_NOC_GREEN))
        self.trihedron.SetDatumPartColor(Prs3d_DatumParts_ZAxis, Quantity_Color(Quantity_NOC_BLUE))

    def mouseMoveEvent(self, evt):
        """Overridden mouseMoveEvent method, that converts mouse position into world coordinates x,y,z and then
        checks if a shape is being hovered over. If a shape is being hovered over, and this shape is an edge, vertex
        or face, appropriate methods for retrieving snapping locations are called. A trihedron which follows the mouse
        are then placed at either the mouse position or at a retrieved snapping location."""

        super().mouseMoveEvent(evt)

        x, y, z = self._display.View.ConvertToGrid(evt.x(), evt.y())
        loc = Geom_Axis2Placement(gp_Pnt(x, y, z), self.dir, self.x_dir)

        self.edge_snap = None
        self.face_snap = None
        self.face_snap_orientation = None

        if self._display.Context.HasDetected():
            entity = self._display.Context.DetectedInteractive()
            if entity.IsKind("AIS_Shape"):
                shape = self._display.Context.DetectedShape()
                if shape.ShapeType() == TopAbs_EDGE:
                    curve = BRepAdaptor_Curve(shape)
                    if curve.GetType() == GeomAbs_Circle:
                        origin = self.snapper.snap_to_circular_edge(curve)
                        loc = Geom_Axis2Placement(origin, self.dir, self.x_dir)
                    else:
                        self.edge_snap = self.snapper.snap_to_edge(evt, shape)
                        loc = Geom_Axis2Placement(gp_Pnt(x, y, z), self.dir, self.x_dir)
                elif shape.ShapeType() == TopAbs_VERTEX:
                    origin = self.snapper.snap_to_vertex(shape)
                    loc = Geom_Axis2Placement(origin, self.dir, self.x_dir)
                elif shape.ShapeType() == TopAbs_FACE:
                    new_loc = self.snapper.snap_to_face(evt, shape)
                    if new_loc is not None:
                        loc = new_loc
                        self.face_snap_orientation = loc

        self.trihedron.SetComponent(loc)
        self._display.Context.Redisplay(self.trihedron, False)
        self._display.Context.UpdateCurrentViewer()

    def start_displaying_origin(self):
        """Start displaying the trihedron"""
        self._display.Context.Display(self.trihedron, False)
        self._display.Context.Deactivate(self.trihedron)

    def stop_displaying_origin(self):
        """Stop displaying the trihedron"""
        self._display.Context.Erase(self.trihedron, True)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, *args):
        super().__init__()
        self.canvas = OriginViewer3d(self)  # Base qt viewer for OCC viewer
        self.setContextMenuPolicy(Qt.CustomContextMenu)  # Custom menu when right-clicking GUI objects
        self.customContextMenuRequested.connect(self.context_menu)  # Set pop up menu to custom defined by context_menu
        self.pop_menu = QtWidgets.QMenu()
        title = f"CAD Conversion"
        self.setWindowTitle(title)
        self.resize(960, 720)
        self.setCentralWidget(self.canvas)

        # create_dock_widget initializes tree_view and tree_dock_widget that display the component tree view
        self.tree_view = None
        self.tree_dock_widget = None
        self.create_tree_dock_widget()

        self.menu_bar = self.menuBar()  # Top menu bar
        self._menus = {}
        self._menu_methods = {}
        self.center_screen()

        # Specify the tree view that display the component hierarchy of the step model
        self.joint_view_root, self.component_view_root = self.create_root_items()
        self.items_clicked_uid = set()  # The items in the tree view that have been clicked

        self.ais_shape_dict = {}

        self.registered_callback = None

        self.hide_list = set()  # List of items in the tree view that are hidden

        self.assembly_list = []  # List of assembly unique ids

        self.joint_manager = JointManager(self.canvas, self.clear_callback, None)

        self.create_joint_widget()

        self.joint_manager.joint_selection_widget = self.joint_selection_widget

        # Change of material
        self.material_manager = MaterialManager(self)

        self.combined_uid = 0

        self.create_datum_origin()
        self.origin_datum_item = self.create_origin_datum_item()
        self.tree_view.expandItem(self.origin_datum_item)
        self.display_origin = True
        self.origin_checked = True

    @property
    def joint_dict(self):
        return self.joint_manager.joint_dict

    @joint_dict.setter
    def joint_dict(self, value):
        self.joint_manager.joint_dict = value

    def select_first_component(self):
        self.joint_manager.select_first_component(self.register_callback)

    def select_second_component(self):
        self.joint_manager.select_second_component(self.register_callback)

    def select_origin(self):
        self.joint_manager.select_origin(self.register_callback)

    def submit_axis(self):
        self.joint_manager.submit_axis()

    def submit_friction(self):
        self.joint_manager.submit_friction()

    def create_joint(self):
        self.joint_manager.create_joint(self.joint_view_root, self.tree_view, self.joint_selection_dock_widget)

    def joint_type_changed(self):
        self.joint_manager.joint_type_changed()

    def display_joint_widget(self):
        self.joint_selection_dock_widget.show()

    def change_material_window(self):
        self.material_manager.change_material_window()

    def finish_material_selection(self):
        self.material_manager.finish_material_selection()

    def create_datum_origin(self):
        """Displays a datum trihedron at the origin"""
        dir = gp_Dir(0, 0, 1)
        x_dir = gp_Dir(1, 0, 0)
        loc = Geom_Axis2Placement(gp_Pnt(0, 0, 0), dir,
                                  x_dir)
        self.origin_trihedron = AIS_Trihedron(loc)
        self.origin_trihedron.SetDrawArrows(True)
        self.origin_trihedron.SetSize(5)
        self.origin_trihedron.SetDatumPartColor(Prs3d_DatumParts_XAxis, Quantity_Color(Quantity_NOC_RED))
        self.origin_trihedron.SetDatumPartColor(Prs3d_DatumParts_YAxis, Quantity_Color(Quantity_NOC_GREEN))
        self.origin_trihedron.SetDatumPartColor(Prs3d_DatumParts_ZAxis, Quantity_Color(Quantity_NOC_BLUE))
        self.canvas._display.Context.Display(self.origin_trihedron, True)

    def create_origin_datum_item(self):
        origin_datum_item = QtWidgets.QTreeWidgetItem(self.component_view_root, ["Datum origin", "_datum_origin"])
        origin_datum_item.setFlags(
            origin_datum_item.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
        origin_datum_item.setCheckState(0, Qt.Checked)
        return origin_datum_item

    def display_datum_origin(self):
        self.canvas._display.Context.Display(self.origin_trihedron, True)
        self.display_origin = True

    def remove_datum_origin(self):
        self.canvas._display.Context.Erase(self.origin_trihedron, True)
        self.display_origin = False

    def create_root_items(self):
        components_view_root = QtWidgets.QTreeWidgetItem(self.tree_view, ["Components"])
        self.tree_view.expandItem(components_view_root)
        self.tree_view.components_parent = components_view_root

        joint_view_root = QtWidgets.QTreeWidgetItem(self.tree_view, ["Joints"])
        self.tree_view.expandItem(joint_view_root)
        return joint_view_root, components_view_root

    def create_joint_widget(self):
        """Creates the joint selection widget as a JointSelectionWidget object, as well as the
        joint_selection_dock_widget as a QDockWidget object"""
        self.joint_selection_widget = JointSelectionWidget(self)
        self.joint_selection_dock_widget = QtWidgets.QDockWidget('New joint', self)
        self.joint_selection_dock_widget.setObjectName("joint_selection_widget")
        self.joint_selection_dock_widget.visibilityChanged.connect(self.joint_manager.cancel_component_selection)
        self.joint_selection_dock_widget.setWidget(self.joint_selection_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.joint_selection_dock_widget)

        # Initially hide the dock widget
        self.joint_selection_dock_widget.hide()

    def create_tree_dock_widget(self):
        """Creates the tree dock widget, which will contain a joint menu with the joint names, and a component menu
        with the component names"""
        self.tree_dock_widget = QtWidgets.QDockWidget("Assembly/Part Structure", self)
        self.tree_dock_widget.setObjectName("tree_dock_widget")
        self.tree_dock_widget.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
        )
        self.tree_view = TreeView()
        self.tree_view.itemClicked.connect(self.tree_view_item_clicked)
        self.tree_view.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked)
        self.tree_view.itemChanged.connect(self.on_item_changed)
        selection_model = self.tree_view.selectionModel()
        selection_model.selectionChanged.connect(self.tree_view_selection_changed)
        self.tree_dock_widget.setWidget(self.tree_view)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.tree_dock_widget)

    def on_item_changed(self, item, column):
        """ Gets called when an item in tree_view is changed (i.e. selected)
            `item` is the QTreeWidgetItem that was changed
            `column` is the column index of the changed cell"""
        new_name = item.text(column)
        uid = item.text(1)
        if uid in dm.label_dict:
            dm.label_dict[uid]["name"] = new_name
        if uid in dm.part_dict:
            dm.part_dict[uid].name = new_name

    def unchecked_to_list(self):
        """Return list of uid's of unchecked (part & wp) items in treeView."""
        dl = []
        self.origin_checked = True
        for item in self.tree_view.findItems("", Qt.MatchContains | Qt.MatchRecursive):
            if item.checkState(0) == Qt.Unchecked:
                uid = item.text(1)
                if (uid in dm.part_dict) or (uid in self.joint_manager.joint_dict):
                    dl.append(uid)
                elif uid == "_datum_origin":
                    self.origin_checked = False
        return dl

    def hidden_in_sync(self):
        """Check if the unchecked items in the tree view are
        synced with the hidden components that are not being drawn"""
        return set(self.unchecked_to_list()) == self.hide_list

    def selected_in_sync(self):
        """Check if the selected items in the tree view are synced with the components that are drawn with a blue shade,
        indicating that they are being selected"""
        return set([item.text(1) for item in self.tree_view.selectedItems()]) == self.items_clicked_uid

    def adjust_selected_items(self):
        """Adjust so that each component that is selected in the tree view is drawn with a blue shade on the display,
        and those that are not selected are drawn normally."""
        selected_set = set([item.text(1) for item in self.tree_view.selectedItems()])
        marked_set = self.items_clicked_uid
        newly_selected = selected_set - marked_set
        newly_unmarked = marked_set - selected_set
        for uid in newly_unmarked:
            if uid in dm.part_dict:
                if uid in self.hide_list:
                    self.erase_tree_object(uid)
                else:
                    self.redraw_shape(uid)  # Draw the shape
            elif uid in self.assembly_list:
                self.unselect_assembly(uid)
        for uid in newly_selected:
            if uid in dm.part_dict and uid not in self.hide_list:
                self.redraw_selected_shape(uid)
            elif uid in self.assembly_list:
                self.select_assembly(uid)

        self.items_clicked_uid = selected_set
        self.canvas._display.Context.UpdateCurrentViewer()

    def select_assembly(self, uid):
        """Recursively draws all subcomponents of an assembly with a blue shade, indicating that they are selected."""
        if uid not in dm.parent_dict:
            return
        for child_uid in dm.parent_dict[uid]:
            if child_uid in dm.part_dict:
                self.redraw_selected_shape(child_uid)
            elif child_uid in self.assembly_list:
                self.select_assembly(child_uid)

    def unselect_assembly(self, uid):
        """Recursively draws all subcomponents of an assembly normally, indicating that they are not selected."""
        if uid not in dm.parent_dict:
            return
        for child_uid in dm.parent_dict[uid]:
            if child_uid in dm.part_dict:
                if child_uid in self.hide_list:
                    self.erase_tree_object(child_uid)
                else:
                    self.redraw_shape(child_uid)  # Draw the shape
            elif child_uid in self.assembly_list:
                self.unselect_assembly(child_uid)

    def tree_view_selection_changed(self, item):
        """Called when the selection of tree view items changes"""
        self.adjust_selected_items()

    def tree_view_item_clicked(self, item):
        """Called when an item in the tree view is checked or unchecked, indicating it should be hidden or unhidden.
        First check if the datum origin should be displayed."""
        in_sync = self.hidden_in_sync()
        if self.display_origin is True and self.origin_checked is False:
            self.remove_datum_origin()
        elif self.display_origin is False and self.origin_checked is True:
            self.display_datum_origin()
        if not in_sync:
            self.adjust_draw_hide()

    def context_menu(self, q_point):
        self.menu = QtWidgets.QMenu()
        self.pop_menu.exec_(self.mapToGlobal(q_point))

    def center_screen(self):
        qr = self.frameGeometry()
        cp = QtWidgets.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def clear_tree(self):
        self.tree_view.clear()
        self.joint_view_root, self.component_view_root = self.create_root_items()
        self.origin_datum_item = self.create_origin_datum_item()

    def add_menu(self, menu_name):
        _menu = self.menu_bar.addMenu("&" + menu_name)
        self._menus[menu_name] = _menu
        return _menu

    def add_function_to_menu(self, menu_name, text, _callable):
        assert callable(_callable), "the function supplied is not callable"
        try:
            _action = QtWidgets.QAction(text, self)
            _action.setMenuRole(QtWidgets.QAction.NoRole)
            _action.triggered.connect(_callable)
            self._menus[menu_name].addAction(_action)
        except KeyError:
            raise ValueError("the menu item %s does not exist" % menu_name)

    def update_parentuid(self):
        """Updates the parent_uid entries in label_dict, after dm.parent_dict has been updated"""
        for uid, child_list in dm.parent_dict.items():
            for child_uid in child_list:
                if child_uid in dm.label_dict:
                    dm.label_dict[child_uid]["parent_uid"] = uid

    def build_tree(self):
        """Builds the tree view by specifying parents of each item using their corresponding "parent_uid" in
        dm.label_dict. For the joints there is no hierarchy among the items, so they are all simply added under the
        joint root item"""
        self.clear_tree()
        self.assembly_list = []
        parent_item_dict = {}
        if self.origin_checked:
            self.origin_datum_item.setCheckState(0, Qt.Checked)
        else:
            self.origin_datum_item.setCheckState(0, Qt.Unchecked)
        self.tree_view.expandItem(self.origin_datum_item)
        for uid, dict_, in dm.label_dict.items():
            # dict: {keys: 'entry', 'name', 'parent_uid', 'ref_entry'}
            name = dict_["name"]
            parent_uid = dict_["parent_uid"]
            if parent_uid not in parent_item_dict:
                parent_item = self.component_view_root
            else:
                parent_item = parent_item_dict[parent_uid]

            # create node in tree view
            item_name = [name, uid]
            item = QtWidgets.QTreeWidgetItem(parent_item, item_name)
            item.setFlags(item.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
            if uid in self.hide_list:
                item.setCheckState(0, Qt.Unchecked)
            else:
                item.setCheckState(0, Qt.Checked)
            self.tree_view.expandItem(item)
            parent_item_dict[uid] = item
            if dict_["is_assembly"]:
                self.assembly_list.append(uid)

        for uid, joint in self.joint_manager.joint_dict.items():
            first_component = joint.first_component
            second_component = joint.second_component
            item = QtWidgets.QTreeWidgetItem(self.joint_view_root,
                                             [f"{first_component} to {second_component}",
                                              uid])
            item.setFlags(item.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked)
            self.tree_view.expandItem(item)

    def adjust_draw_hide(self):
        """Erase from 3D display any item that gets unchecked, draw when checked."""
        unchecked = self.unchecked_to_list()
        unchecked_set = set(unchecked)
        newly_unchecked = unchecked_set - self.hide_list
        newly_checked = self.hide_list - unchecked_set
        for uid in newly_unchecked:
            self.erase_tree_object(uid)
        for uid in newly_checked:
            if uid in dm.part_dict:
                self.draw_shape(uid)  # Draw the shape
            elif uid in self.joint_manager.joint_dict:
                self.draw_joint(uid)
        self.hide_list = unchecked_set
        self.canvas._display.Context.UpdateCurrentViewer()

    def erase_tree_object(self, uid):
        """Erase the part (shape) with uid."""
        context = self.canvas._display.Context
        if uid in self.ais_shape_dict:
            ais_shape = self.ais_shape_dict[uid]
            context.Remove(ais_shape, False)
            context.Erase(ais_shape, False)
        elif uid in self.joint_manager.joint_dict:
            trihedron = self.joint_manager.joint_dict[uid].center_trihedron
            axis = self.joint_manager.joint_dict[uid].axis_line
            context.Erase(trihedron, False)
            context.Erase(axis, False)

    def remove_joint(self, uid):
        """Stops displaying the joint with uid"""
        context = self.canvas._display.Context
        if uid in self.joint_manager.joint_dict:
            trihedron = self.joint_manager.joint_dict[uid].center_trihedron
            axis = self.joint_manager.joint_dict[uid].axis_line
            context.Remove(trihedron, False)
            context.Remove(axis, False)

    def draw_joint(self, uid):
        """Draw the joint with uid"""
        trihedron = self.joint_manager.joint_dict[uid].center_trihedron
        axis = self.joint_manager.joint_dict[uid].axis_line
        context = self.canvas._display.Context
        context.Display(trihedron, False)
        context.Display(axis, False)

    def redraw_selected_shape(self, uid):
        """Draw the part (shape) that's selected, and with id given by uid."""
        context = self.canvas._display.Context
        if uid:
            part_data = dm.part_dict[uid]
            try:
                ais_shape = self.ais_shape_dict[uid]
                color = Quantity_Color(0.5, 0.5, 0.8,
                                       Quantity_TOC_RGB)
                transparency = 0.1
                context.Display(ais_shape, False)
                context.SetColor(ais_shape, color, False)
                context.SetTransparency(ais_shape, transparency, False)
                # Set shape transparency, a float from 0.0 to 1.0
                drawer = ais_shape.DynamicHilightAttributes()
                context.HilightWithColor(ais_shape, drawer, False)
            except AttributeError as e:
                print(e)

    def redraw_shape(self, uid):
        """Redraw the part (shape) with uid."""
        context = self.canvas._display.Context
        if uid:
            part_data = dm.part_dict[uid]
            color = part_data.color
            try:
                ais_shape = self.ais_shape_dict[uid]
                context.SetColor(ais_shape, color, False)
                context.SetTransparency(ais_shape, 0.0, False)
                drawer = ais_shape.DynamicHilightAttributes()
                context.HilightWithColor(ais_shape, drawer, False)
                context.Redisplay(ais_shape, False)
            except AttributeError as e:
                print(e)

    def draw_shape(self, uid):
        """Draw the part (shape) with uid."""
        context = self.canvas._display.Context
        if uid:
            part_data = dm.part_dict[uid]
            shape = part_data.shape
            color = part_data.color
            try:
                ais_shape = AIS_Shape(shape)
                self.ais_shape_dict[uid] = ais_shape
                context.SetColor(ais_shape, color, False)
                drawer = ais_shape.DynamicHilightAttributes()
                context.HilightWithColor(ais_shape, drawer, False)
                context.Display(ais_shape, False)
            except AttributeError as e:
                print(e)

    def redraw(self):
        """Erase & redraw all parts except those in hide_list."""
        context = self.canvas._display.Context
        if not self.registered_callback:
            self.canvas._display.SetSelectionModeNeutral()
            context.SetAutoActivateSelection(True)
        context.RemoveAll(True)
        for uid in dm.part_dict:
            if uid not in self.hide_list:
                self.draw_shape(uid)
        for uid in self.joint_manager.joint_dict:
            if uid not in self.hide_list:
                self.draw_joint(uid)
        if self.display_origin:
            self.display_datum_origin()
        context.UpdateCurrentViewer()

    def fit_all(self):
        """Fit all displayed parts to the screen"""
        self.canvas._display.FitAll()

    def register_callback(self, callback):
        current_callback = self.registered_callback
        if current_callback:
            self.clear_callback()
        self.canvas._display.register_select_callback(callback)
        self.registered_callback = callback

    def clear_callback(self):
        if self.registered_callback:
            self.canvas._display.unregister_callback(self.registered_callback)
            self.registered_callback = None
            self.canvas._display.SetSelectionModeNeutral()

    def merge_assembly_shapes(self, uid):
        """Combine an assembly so that all its subcomponents become one shape"""
        if uid in dm.part_dict:
            return dm.part_dict[uid].shape

        # Create an initial empty shape using TopoDS_Compound
        builder = BRep_Builder()
        compound_shape = TopoDS_Compound()
        builder.MakeCompound(compound_shape)

        if uid in dm.parent_dict:
            for child_uid in dm.parent_dict[uid]:
                child_shape = self.merge_assembly_shapes(child_uid)
                # Make sure the child_shape is valid before fusing
                if not child_shape.IsNull():
                    # Fuse the child_shape with the existing compound_shape
                    fused_shape = BRepAlgoAPI_Fuse(compound_shape, child_shape).Shape()
                    # Update the compound_shape with the fused result
                    compound_shape = fused_shape

        return compound_shape

    def get_component_depth(self, uid):
        """Retrieves the depth of component with uid. The root component has depth 0, the root's children have depth
        1 and so on."""
        depth = 0
        parent_uid = dm.label_dict[uid]["parent_uid"]
        while parent_uid is not None:
            depth += 1
            parent_uid = dm.label_dict[parent_uid]["parent_uid"]
        return depth

    def get_least_depth_shape(self, uid):
        """Retrieve the shape with the least depth, i.e. the topmost shape, from an assembly with uid"""
        topmost_child_uid = None
        topmost_parent_uid = None
        min_depth = float('inf')
        if dm.label_dict[uid]["is_assembly"]:
            for child_uid in dm.parent_dict[uid]:
                depth, topmost_child_uid_, topmost_parent_uid_ = self.get_least_depth_shape(child_uid)
                if depth < min_depth:
                    min_depth = depth
                    topmost_parent_uid = topmost_parent_uid_
                    topmost_child_uid = topmost_child_uid_
        else:
            parent_uid = dm.label_dict[uid]["parent_uid"]
            if parent_uid is not None:
                depth = self.get_component_depth(parent_uid)
                if depth < min_depth:
                    min_depth = depth
                    topmost_parent_uid = parent_uid
                    topmost_child_uid = uid
        return min_depth, topmost_child_uid, topmost_parent_uid

    def merge_components_shapes(self):
        """Combined all selected components into one shape"""
        combined_shape = None
        for uid in self.items_clicked_uid:
            if uid in dm.part_dict:
                shape = dm.part_dict[uid].shape
                if combined_shape is None:
                    combined_shape = shape
                else:
                    fusion = BRepAlgoAPI_Fuse(combined_shape, shape)
                    if fusion.HasErrors():
                        print("Error: Fusion operation failed.")
                        return
                    combined_shape = fusion.Shape()
            elif dm.label_dict[uid]["is_assembly"]:
                shape = self.merge_assembly_shapes(uid)
                if combined_shape is None:
                    combined_shape = shape
                else:
                    fusion = BRepAlgoAPI_Fuse(combined_shape, shape)
                    if fusion.HasErrors():
                        print("Error: Fusion operation failed.")
                        return
                    combined_shape = fusion.Shape()

        # Create new component
        new_component_uid = f"combined_component_{self.combined_uid}"
        new_component_name = f"Combined Component {self.combined_uid}"
        self.combined_uid += 1
        # {uid: {keys: 'shape', 'name', 'color', 'loc', 'mass', 'density'}}
        new_part = Part(shape=combined_shape,
                        name=new_component_name,
                        color=Quantity_Color(Quantity_NOC_GRAY),
                        loc=TopLoc_Location(gp_Trsf()))

        # dict: {keys: 'entry', 'name', 'parent_uid', 'ref_entry'}
        new_label_dict = {
            "entry": new_component_uid,  # You can generate a unique entry string if needed
            "name": new_component_name,  # The name we just defined
            "parent_uid": None,  # Assuming it has no parent, adjust as needed
            "ref_entry": None,  # Assuming it has no reference entry, adjust as needed
            "is_assembly": False,  # Assuming it's not an assembly, adjust as needed
        }

        # Find the topmost parent among the selected components
        topmost_parent_uid = None
        topmost_child_uid = None
        min_depth = float('inf')
        for uid in self.items_clicked_uid:
            min_depth_, topmost_child_uid_, topmost_parent_uid_ = self.get_least_depth_shape(uid)
            if min_depth_ < min_depth:
                topmost_parent_uid = topmost_parent_uid_
                topmost_child_uid = topmost_child_uid_
                min_depth = min_depth_

        # If a topmost parent was found, make that parent the new parent of the combined component
        if topmost_parent_uid is not None:
            new_label_dict["parent_uid"] = topmost_parent_uid
            new_part.color = dm.part_dict[topmost_child_uid].color
            new_part.loc = dm.part_dict[topmost_child_uid].loc

        # Update part dictionary
        dm.part_dict[new_component_uid] = new_part
        dm.label_dict[new_component_uid] = new_label_dict
        for uid in self.items_clicked_uid:
            self.erase_assembly(uid)

        # Redraw scene
        self.build_tree()
        self.draw_shape(new_component_uid)
        self.canvas._display.Context.UpdateCurrentViewer()

    def merge_shapes(self):
        """Merge shapes by combining all selected components into one shape"""
        if "_datum_origin" in self.items_clicked_uid:
            return
        if len(self.items_clicked_uid) > 1:
            self.merge_components_shapes()
        elif len(self.items_clicked_uid) == 1:
            assembly_uid = self.items_clicked_uid.pop()
            if not dm.label_dict[assembly_uid]["is_assembly"]:  # Can't combine a single shape
                return
            combined_shape = self.merge_assembly_shapes(assembly_uid)
            for child_uid in dm.parent_dict[assembly_uid]:
                self.erase_assembly(child_uid)
            new_component_name = dm.label_dict[assembly_uid]["name"]
            dm.part_dict[assembly_uid] = Part(shape=combined_shape,
                                              name=new_component_name,
                                              color=Quantity_Color(Quantity_NOC_GRAY),
                                              loc=TopLoc_Location(gp_Trsf()))
            dm.label_dict[assembly_uid]["is_assembly"] = False
            self.build_tree()
            self.draw_shape(assembly_uid)
            self.canvas._display.Context.UpdateCurrentViewer()

    def erase_assembly(self, uid):
        """Erase an assembly together with all of its subcomponents"""
        if uid in dm.label_dict:
            del dm.label_dict[uid]
        if uid in dm.part_dict:
            self.erase_tree_object(uid)
            del dm.part_dict[uid]
            return
        if uid in dm.parent_dict:
            for child_uid in dm.parent_dict[uid]:
                self.erase_assembly(child_uid)

    def update_parent_lists(self, uid):
        """For an erased component with uid, erase all dm.parent_dict entries of this uid"""
        if uid in dm.parent_dict:
            del dm.parent_dict[uid]
        for uid, child_list in dm.parent_dict.items():
            if uid in child_list:
                child_list.remove(uid)

    def delete_joints_belonging_to_component(self, uid):
        joints_to_delete = []
        for joint_uid, joint in self.joint_dict.items():
            if joint.parent_uid == uid or joint.child_uid == uid:
                joints_to_delete.append(joint_uid)
        for joint_uid in joints_to_delete:
            self.delete_joint(joint_uid)

    def delete_components_rec(self, uid):
        if uid in dm.part_dict:
            self.erase_tree_object(uid)
            del dm.part_dict[uid]
            del self.ais_shape_dict[uid]
            del dm.label_dict[uid]
            if uid in dm.parent_dict:
                del dm.parent_dict[uid]
            self.delete_joints_belonging_to_component(uid)
            return
        elif uid in dm.label_dict and dm.label_dict[uid]["is_assembly"]:
            for child_uid in dm.parent_dict[uid]:
                self.delete_components_rec(child_uid)
            del dm.label_dict[uid]
            del dm.parent_dict[uid]

    def delete_components(self):
        for uid in self.items_clicked_uid:
            if uid in dm.label_dict and dm.label_dict[uid]["parent_uid"] is not None and uid in \
                    dm.parent_dict[dm.label_dict[uid]["parent_uid"]]:
                dm.parent_dict[dm.label_dict[uid]["parent_uid"]].remove(uid)
            self.delete_components_rec(uid)
            self.update_parent_lists(uid)
        self.build_tree()
        self.canvas._display.Context.UpdateCurrentViewer()

    def delete_joint(self, uid):
        for i in range(self.joint_view_root.childCount()):
            child = self.joint_view_root.child(i)
            if child.text(1) == uid:
                self.joint_view_root.takeChild(i)
                break
        self.remove_joint(uid)
        del self.joint_manager.joint_dict[uid]

    def delete_selected_joints(self):
        """Delete all joints that have been selected in the tree view"""
        for uid in self.items_clicked_uid:
            # Delete from joint dictionary
            if uid in self.joint_manager.joint_dict:
                self.delete_joint(uid)
        self.canvas._display.Context.UpdateCurrentViewer()

    def update_parent_after_move_top(self, uid):
        for _, child_list in dm.parent_dict.items():
            if uid in child_list:
                child_list.remove(uid)

    def move_to_top(self):
        for uid in self.items_clicked_uid:
            if uid in dm.label_dict:
                self.update_parent_after_move_top(uid)
                dm.label_dict[uid]["parent_uid"] = dm.root_uid
                dm.parent_dict[dm.root_uid].append(uid)
        self.build_tree()

    def find_root(self):
        """Find the root of the assembly, after having loaded it in again. The root has parent None"""
        for uid in dm.label_dict:
            if dm.label_dict[uid]["parent_uid"] is None:
                dm.root_uid = uid
                return

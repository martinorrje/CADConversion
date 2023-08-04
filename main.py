import sys
from mainwindow import MainWindow, dm
from conversion import LinearGraphConverter
from generate_graph import create_graph
from serializer import Serializer

import docmodel

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

lgc = LinearGraphConverter()
serializer = Serializer()


def open_doc():
    result = serializer.load_model()
    if result is None:
        return
    win.joint_dict, dm.part_dict, dm.label_dict, dm.parent_dict = result
    win.find_root()
    win.update_parentuid()
    win.build_tree()
    win.redraw()
    win.fit_all()


def save_doc():
    serializer.save_model(win.joint_dict, dm.part_dict, dm.label_dict, dm.parent_dict)


def add_joint():
    win.display_joint_widget()


def load_step_at_top():
    """Load STEP file and assign it to self.doc
        This effectively allows step to be a surrogate for file save/load."""
    dm.part_dict = {}
    dm.label_dict = {}
    dm.parent_dict = {}
    win.joint_dict = {}
    win.ais_shape_dict = {}
    docmodel.load_step_at_top(dm)
    win.build_tree()
    win.redraw()
    win.fit_all()


def merge_shapes():
    win.merge_shapes()


def delete_components():
    win.delete_components()


def delete_joint():
    win.delete_joint()


def move_to_top():
    win.move_to_top()


def export_linear_graph():
    directory_path = lgc.get_graph_folder()
    if not directory_path:
        return
    lgc.convert_to_graph(dm.part_dict, win.joint_dict)
    lgc.convert_to_json(directory_path)
    create_graph(directory_path + '/data.json', 'translation_graph')
    create_graph(directory_path + '/data.json', 'rotation_graph')


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    menu = win.menuBar()
    file_menu = win.add_menu("File")
    win.add_function_to_menu("File", "Open File", open_doc)
    win.add_function_to_menu("File", "Save file", save_doc)
    file_menu.addSeparator()
    win.add_function_to_menu("File", "Load STEP", load_step_at_top)

    # Pop up menu when selecting component
    win.tree_view.component_pop_menu.addAction("Change material", win.change_material_window)
    win.tree_view.component_pop_menu.addAction("Combine components", merge_shapes)
    win.tree_view.component_pop_menu.addAction("Delete components", delete_components)
    win.tree_view.component_pop_menu.addAction("Move to top", move_to_top)

    win.tree_view.joint_pop_menu.addAction("Delete joint", delete_joint)

    win.show()
    win.canvas.InitDriver()
    display = win.canvas._display

    joint_menu = win.add_menu("Joints")
    win.add_function_to_menu("Joints", "Add joint", add_joint)

    convert_menu = win.add_menu("Export")
    win.add_function_to_menu("Export", "Export linear graph", export_linear_graph)


    win.setFocus()
    # If this line is uncommented the user has to deselect and then select window again to access the menu bar
    # win.raise_()
    sys.exit(app.exec_())

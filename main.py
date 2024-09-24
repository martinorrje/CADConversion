import os
import sys
from ui.mainwindow import MainWindow, dm
from model.conversion import LinearGraphConverter, create_graph
from model.serializer import Serializer
from model.modelupdate import Watcher

from model import docmodel

from PyQt5.QtWidgets import QApplication

lgc = LinearGraphConverter()
serializer = Serializer()
watcher = None


def open_doc():
    global watcher
    result = serializer.load_model()
    if result is None:
        return
    win.tree_view.clearSelection()
    win.joint_dict, dm.part_dict, dm.label_dict, dm.parent_dict, f_path = result

    if os.path.exists(f_path):
        win.file_to_watch = f_path

        new_dm = docmodel.DocModel()
        docmodel.load_step_at_top_fpath(new_dm, f_path)

        if not docmodel.same_doc_model(dm, new_dm):
            result = win.show_update_model_popup()

        if watcher is None:
            watcher = Watcher(f_path, win)
        else:
            watcher.stop()
            watcher.watch_new_file(f_path)
        watcher.run()

    win.build_tree()
    win.redraw()

    win.find_root()
    win.update_parentuid()

    win.fit_all()


def save_doc():
    serializer.save_model(win.joint_dict, dm.part_dict, dm.label_dict, dm.parent_dict, win.file_to_watch)


def add_joint():
    win.display_joint_widget()


def load_step_at_top():
    """Load STEP file and assign it to self.doc
        This effectively allows step to be a surrogate for file save/load."""
    global watcher
    global step_file_loaded

    win.tree_view.clearSelection()

    f_path = docmodel.load_step_at_top(dm)

    if f_path:
        win.joint_dict = {}
        win.hide_list = set()

        if watcher is None:
            watcher = Watcher(f_path, win)
        else:
            watcher.stop()
            watcher.watch_new_file(f_path)
        win.file_to_watch = f_path
        watcher.run()
        win.build_tree()
        win.redraw()
        win.fit_all()


def merge_shapes():
    win.merge_shapes()


def delete_components():
    win.delete_components()


def delete_joint():
    win.delete_selected_joints()


def move_to_top():
    win.move_to_top()


def update_model():
    win.load_saved_modified_step()


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

    edit_menu = win.add_menu("Model")
    win.add_function_to_menu("Model", "Update model", update_model)

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
    sys.exit(app.exec_())

import json
import logging
import sys

import PyQt5.QtCore
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction,
    QMenu,
    QMessageBox,
    QDockWidget,
    QTreeWidget,
    QTreeWidgetItem,
)

from ...doc import DocModel

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class ExplorerDock(QDockWidget):
    def __init__(self, parent, canvas, name="Assembly and Joints"):
        super().__init__(name, parent)
        self.canvas = canvas

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetClosable)

        self.tree = ExplorerTreeView(self, canvas)
        self.setWidget(self.tree)


    def construct(self, dm: DocModel):
        self.tree.construct(dm)


class ExplorerTreeView(QTreeWidget):
    def __init__(self, parent, canvas):
        super().__init__(parent)
        self.canvas = canvas

        self.header().setHidden(True)

        self.assembly_root = QTreeWidgetItem(self, ["Assembly"])
        self.joint_root = QTreeWidgetItem(self, ["Joints"])

        self.assembly = {}

        #self.setSelectionMode(self.ExtendedSelection)  # Multiple items can be selected at the same time
        #self.setContextMenuPolicy(Qt.CustomContextMenu)  # Custom context menu when right-clicking items
        #self.customContextMenuRequested.connect(
        #    self.context_menu)  # Specify context menu shown when right-clicking items
        #self.component_pop_menu = QMenu(self)  # Create QMenu object used as context menu
        #self.joint_pop_menu = QMenu(self)
        #self.components_parent = None

        # Custom signal handlers for selecting items
        self.itemClicked.connect(self.on_select)

    def construct(self, dm: DocModel):
        self.construct_assembly(dm, dm.part_root_uid)

    def construct_assembly(self, dm: DocModel, uid):
        lbl = dm.labels[uid]
        if lbl.parent_uid is None:
            parent_item = self.assembly_root
        else:
            parent_item = self.assembly[lbl.parent_uid]

        item = QTreeWidgetItem(parent_item, [lbl.name])
        self.assembly[uid] = item

        for child_uid in dm.uid_children(uid):
            self.construct_assembly(dm, uid=child_uid)

    def on_select(self, item, *args):
        selected_assembly = None
        for uid, a_item in self.assembly.items():
            if a_item == item:
                selected_assembly = uid
                break

        LOG.debug(f"{item} {selected_assembly}")
        self.canvas.highlight_part(selected_assembly)


    # OLD BELOW, FIGURE OUT WHAT IT DOES
    def _initialize_context_menus(self):
        self.component_pop_menu = self._create_component_menu()
        self.joint_pop_menu = self._create_joint_menu()

    def _create_component_menu(self):
        menu = QMenu(self)
        # Maybe add actions for the component menu here, instead of in main
        return menu

    def _create_joint_menu(self):
        menu = QtWidgets.QMenu(self)
        # Maybe add actions for the component menu here, instead of in main
        return menu

    def is_component(self, item):
        """Checks if the parent the furthest up for this item is the component root. If so, the item is a component."""
        parent = item.parent()
        if parent:
            if parent == self.components_parent:
                return True
            else:
                return self.is_component(parent)
        return False

    def context_menu(self, q_point):
        item = self.itemAt(q_point)
        if not item or item.text(1) == "_datum_origin":
            return
        if self.is_component(item):
            self.component_pop_menu.exec_(self.mapToGlobal(q_point))
        elif item is not self.components_parent:
            self.joint_pop_menu.exec_(self.mapToGlobal(q_point))

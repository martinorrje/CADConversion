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
    def __init__(self, parent, name="Assembly/Part Structure"):
        super().__init__(name, parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetClosable)

        self.tree = ExplorerTreeView(self)
        self.setWidget(self.tree)


class ExplorerTreeView(QTreeWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.header().setHidden(True)

        self.part_root = QTreeWidgetItem(self, ["Parts"])
        self.joint_root = QTreeWidgetItem(self, ["Joints"])

        test_part = QTreeWidgetItem(self.part_root, ["Test Part"])

        #self.setSelectionMode(self.ExtendedSelection)  # Multiple items can be selected at the same time
        #self.setContextMenuPolicy(Qt.CustomContextMenu)  # Custom context menu when right-clicking items
        #self.customContextMenuRequested.connect(
        #    self.context_menu)  # Specify context menu shown when right-clicking items
        #self.component_pop_menu = QMenu(self)  # Create QMenu object used as context menu
        #self.joint_pop_menu = QMenu(self)
        #self.components_parent = None

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

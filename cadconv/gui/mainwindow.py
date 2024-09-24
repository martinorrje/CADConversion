import json
import logging
import sys
import traceback

import PyQt5.QtCore
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QAction,
    QMenu,
    QFileDialog,
    QMessageBox,
)

from . import widgets
from ..doc import DocModel

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


def run(argv=["cadconv"]):
    app = QApplication(argv)
    win = MainWindow(app)
    win.show()
    sys.exit(app.exec_())


def catchall(*args, **kwargs):
    print("args:  ", args)
    print("kwargs:", kwargs)


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.name = "cad2real Annotator"
        self.setWindowTitle(self.name)
        self.resize(960, 720)

        LOG.debug("Setting up state variables...")
        self.dm = None

        LOG.debug("Setup the 3D canvas...")
        self.canvas = widgets.Viewer3D(self)
        self.setCentralWidget(self.canvas)

        LOG.debug("Letup the left dock...")
        self.explorer_dock = widgets.ExplorerDock(self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.explorer_dock)

        LOG.debug("Setup the top bar menu...")
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction("Open File").triggered.connect(self.open_file)
        file_menu.addAction("Save File").triggered.connect(self.save_file)
        file_menu.addSeparator()
        file_menu.addAction("Load STEP").triggered.connect(self.load_step)
        file_menu.addSeparator()
        file_menu.addAction("Quit").triggered.connect(lambda arg: self.app.exit())
        model_menu = menubar.addMenu("&Edit")
        model_menu.addAction("Add Joint").triggered.connect(catchall)
        model_menu = menubar.addMenu("&View")
        model_menu.addAction("Show Structure Dock").triggered.connect(lambda arg: self.explorer_dock.show())
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("About").triggered.connect(self.about)

        #self.setContextMenuPolicy(Qt.CustomContextMenu)  # Custom menu when right-clicking GUI objects
        #self.customContextMenuRequested.connect(self.context_menu)  # Set pop up menu to custom defined by context_menu
        #self.pop_menu = QtWidgets.QMenu()

        #self.addDockWidget

    def open_file(self, arg):
        LOG.debug("Load a DocModel")
        try:
            dst = QFileDialog.getOpenFileName(self)

            LOG.debug(f"Selection: {repr(dst)}")
            (filename, _) = dst
            if len(filename) == 0:
                return

            with open(filename, "r") as f:
                blob = json.load(f)
            self.dm = DocModel.load(blob)
            self.canvas.redraw(self.dm)

            LOG.info(f"Loaded DocModel from {filename}")
        except Exception as e:
            LOG.error(traceback.format_exc())
            QMessageBox.warning(self, "Error Loading DocModel", str(e))

    def save_file(self, arg):
        LOG.debug("Save the DocModel")
        if self.dm is None:
            QMessageBox.warning(self, "Error Saving DocModel", "Nothing to save.")
            return

        try:
            dst = QFileDialog.getSaveFileName(self)

            LOG.debug(f"Selection: {repr(dst)}")
            (filename, _) = dst
            if len(filename) == 0:
                return

            blob = self.dm.dump()
            with open(filename, "w+") as f:
                json.dump(blob, f, indent=4)
            LOG.info(f"Saved file to {filename}")
        except Exception as e:
            LOG.error(traceback.format_exc())
            QMessageBox.warning(self, "Error Saving DocModel", str(e))

    def load_step(self, arg):
        LOG.debug("Open file dialog and load a STEP file from selected file.")
        try:
            ret = QFileDialog.getOpenFileName(self)

            LOG.debug(f"Selection: {repr(ret)}")
            (filename, _) = ret
            if len(filename) == 0:
                return

            LOG.debug(f"Creating new DocModel")
            self.dm = DocModel()
            self.dm.load_step(filename)
            self.dm.parse()
            self.canvas.redraw(self.dm)
        except Exception as e:
            self.dm = None
            LOG.error(traceback.format_exc())
            QMessageBox.warning(self, "Error Loading Step FILE", str(e))

    def about(self, arg):
        LOG.debug("Show \"about\" dialog window.")
        import OCC
        QMessageBox.about(self, f"About {self.name}", (
            "This is the annotation tool used for the cad2real methodology."
            "\n\n"
            f"Python OCC Version: {OCC.VERSION}\n"
            f"PyQt Version: {PyQt5.QtCore.qVersion()}\n"
            "\n"
            f"Python Version: {sys.version}"
        ))

    def context_menu(self, q_point):
        LOG.warning("Is this needed?")
        self.menu = QtWidgets.QMenu()
        self.pop_menu.exec_(self.mapToGlobal(q_point))

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette


class TreeView(QtWidgets.QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.header().setHidden(True)
        self.setSelectionMode(self.ExtendedSelection)  # Multiple items can be selected at the same time
        self.setContextMenuPolicy(Qt.CustomContextMenu)  # Custom context menu when right-clicking items
        self.customContextMenuRequested.connect(
            self.context_menu)  # Specify context menu shown when right-clicking items
        self.component_pop_menu = QtWidgets.QMenu(self)  # Create QMenu object used as context menu
        self.joint_pop_menu = QtWidgets.QMenu(self)
        self.components_parent = None

    def _initialize_context_menus(self):
        self.component_pop_menu = self._create_component_menu()
        self.joint_pop_menu = self._create_joint_menu()

    def _create_component_menu(self):
        menu = QtWidgets.QMenu(self)
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
        else:
            self.joint_pop_menu.exec_(self.mapToGlobal(q_point))


class JointSelectionWidget(QtWidgets.QWidget):
    def __init__(self, win, parent=None):
        super().__init__(parent)
        self.win = win

        # Creating buttons
        self.select_point1_button = self._create_button('Select component 1', self.win.select_first_component)
        self.select_point2_button = self._create_button('Select component 2', self.win.select_second_component)
        self.select_origin_button = self._create_button('Select joint origin', self.win.select_origin)
        self.create_joint_button = self._create_button('Create joint', self.win.create_joint)
        self.submit_axis_button = self._create_button("Submit axis", self.win.submit_axis)
        self.submit_friction_button = self._create_button("Submit joint friction", self.win.submit_friction)

        # Line edits for x, y, z input
        self.line_edit_x = self._create_line_edit("X")
        self.line_edit_y = self._create_line_edit("Y")
        self.line_edit_z = self._create_line_edit("Z")

        # Popup messages
        self.select_both_components_popup = self._create_popup("Select both components for joint")
        self.select_everything_popup = self._create_popup("Select everything before creating joint")
        self.same_components_popup = self._create_popup("Can't select the same components for joint")
        self.select_origin_popup = self._create_popup("Select joint origin before axis")

        # Combo box for joint type selection
        self.joint_type_selection = self._create_combo_box(['Revolute', 'Prismatic', 'Fixed'],
                                                           self.win.joint_type_changed)

        # Friction selection
        self.friction_selection = self._create_line_edit("Friction (default=0)")

        self._setup_layout()

    def hide_layout(self):
        self.hide()

    def clear_widgets(self):
        self.select_point1_button.setText('Select component 1')
        self.select_point2_button.setText('Select component 2')
        self.select_origin_button.setText('Select joint origin')
        self.joint_type_selection.setCurrentText('Revolute')
        self.line_edit_x.clear()
        self.line_edit_x.setPlaceholderText("X")
        self.line_edit_y.clear()
        self.line_edit_y.setPlaceholderText("Y")
        self.line_edit_z.clear()
        self.line_edit_z.setPlaceholderText("Z")
        self.friction_selection.clear()
        self.friction_selection.setPlaceholderText("Friction (default=0)")

    def clear_axis_line_edits(self):
        self.line_edit_x.clear()
        self.line_edit_x.setPlaceholderText("X")
        self.line_edit_y.clear()
        self.line_edit_y.setPlaceholderText("Y")
        self.line_edit_z.clear()
        self.line_edit_z.setPlaceholderText("Z")

    def clear_friction_line_edit(self):
        self.friction_selection.clear()
        self.friction_selection.setPlaceholderText("Friction (default=0)")

    def set_line_edits(self, val):
        self.line_edit_x.setEnabled(val)
        self.line_edit_x.clearFocus()
        self.line_edit_y.setEnabled(val)
        self.line_edit_y.clearFocus()
        self.line_edit_z.setEnabled(val)
        self.line_edit_z.clearFocus()
        self.friction_selection.setEnabled(val)
        self.friction_selection.clearFocus()
        self.submit_axis_button.setEnabled(val)
        self.submit_friction_button.setEnabled(val)

    def _create_button(self, text, callback):
        button = QtWidgets.QPushButton(text, self)
        button.clicked.connect(callback)
        return button

    def _create_line_edit(self, placeholder_text):
        line_edit = QtWidgets.QLineEdit(self)
        line_edit.setPlaceholderText(placeholder_text)
        return line_edit

    def _create_popup(self, text):
        popup = QtWidgets.QMessageBox(self)
        popup.setText(text)
        return popup

    def _create_combo_box(self, items, callback):
        combo_box = QtWidgets.QComboBox(self)
        for item in items:
            combo_box.addItem(item)
        combo_box.currentIndexChanged.connect(callback)
        return combo_box

    def _setup_layout(self):
        layout = QtWidgets.QVBoxLayout()
        for widget in [
            self.select_point1_button,
            self.select_point2_button,
            self.select_origin_button,
            self.joint_type_selection,
            self.select_both_components_popup,
            self.select_everything_popup,
            self.select_origin_popup,
            self.same_components_popup,
            self.line_edit_x,
            self.line_edit_y,
            self.line_edit_z,
            self.submit_axis_button,
            self.friction_selection,
            self.submit_friction_button
        ]:
            layout.addWidget(widget)

        small_spacer = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        layout.addItem(small_spacer)
        layout.addWidget(self.create_joint_button)
        spacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        layout.addItem(spacer)

        self.setLayout(layout)


class MaterialDialog(QtWidgets.QGroupBox):
    MATERIALS = {
        'Aluminum': 0.00271,
        'Steel': 0.00775,
        'ASA': 0.001,
        'ABS': 0.001,
        'TPU': 0.00121
    }

    def __init__(self, parent=None):
        super(MaterialDialog, self).__init__(parent)

        self.select_density_label = None
        self.select_density = None
        self.input_mass_option = None
        self.input_density_option = None
        self.or_label1 = None
        self.or_label2 = None
        self.finish_button = None
        self.cancel_button = None

        self.init_finish_cancel_buttons()
        self.init_material_selection()
        self.init_density_input()
        self.init_mass_input()
        self.init_layout(layout_size=parent.size() * 0.5)

    def init_finish_cancel_buttons(self):
        """Initialize the finish and cancel buttons as QPushButtons located in the lower right corner of the
        material dialog window"""
        self.finish_button = QtWidgets.QPushButton('Finish')
        self.finish_button.clicked.connect(self.parent().finish_material_selection)
        self.cancel_button = QtWidgets.QPushButton('Cancel')
        self.cancel_button.clicked.connect(self.reset)

    def init_material_selection(self):
        """Initialize the material selection QComboBox, where the user can select a material from a predefined list
        of materials, with their densities defined in the MATERIALS dictionary"""
        self.select_density_label = QtWidgets.QLabel("Select density", self)
        self.select_density = QtWidgets.QComboBox(self)
        self.select_density.addItem("Custom")
        for material in self.MATERIALS:
            self.select_density.addItem(material)
        self.select_density.currentIndexChanged.connect(self.density_qbox_changed)
        self.or_label1 = QtWidgets.QLabel("or", self)

    def init_density_input(self):
        """Initialize the density selection QLineEdit, allowing the user to define a custom density for the selected
        components. Each selected object will get this density."""
        self.input_density_option = QtWidgets.QLineEdit(self)
        self.input_density_option.setPlaceholderText("Input custom density")
        self.input_density_option.setFocusPolicy(Qt.ClickFocus)
        self.input_density_option.textChanged.connect(self.density_changed)
        self.or_label2 = QtWidgets.QLabel("or", self)

    def init_mass_input(self):
        """Initialize the mass selection QLineEdit, allowing the user to define a custom mass for the selected objects.
        Each selected object will get this mass."""
        self.input_mass_option = QtWidgets.QLineEdit(self)
        self.input_mass_option.setPlaceholderText("Input custom mass")
        self.input_mass_option.setFocusPolicy(Qt.ClickFocus)
        self.input_mass_option.textChanged.connect(self.mass_changed)

    def init_layout(self, layout_size):
        """Initialize a QVBoxLayout with all the specified widgets, and adjust the size of the layout to be consistent
        with the size of the parent window"""
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.finish_button)

        spacer = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(self.select_density_label)
        layout.addWidget(self.select_density)
        layout.addWidget(self.or_label1)
        layout.addWidget(self.input_density_option)
        layout.addWidget(self.or_label2)
        layout.addWidget(self.input_mass_option)

        layout.addItem(spacer)
        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.resize(layout_size)
        self.move(self.parent().geometry().center() / 2 - self.geometry().center() / 2)
        color = self.palette().color(QPalette.Background)
        self.setStyleSheet(
            "QGroupBox { background-color: rgba(%i, %i, %i, 255); }" % (color.red(), color.green(), color.blue()))

    def reset(self):
        """Reset the material dialog, for example after finishing or cancelling the selection"""
        self.hide()
        self.select_density.setCurrentIndex(0)

        self.input_density_option.clear()
        self.input_density_option.setPlaceholderText("Input custom density")

        self.input_mass_option.clear()
        self.input_mass_option.setPlaceholderText("Input custom mass")

    def density_qbox_changed(self):
        """If the selected material in the density QCombobox has changed, then update the density and mass
        QLineEdits according to whether the selected material is "Custom" or not."""
        if self.select_density.currentIndex() == 0:
            self.input_density_option.setEnabled(True)
            self.input_mass_option.setEnabled(True)
        else:
            self.input_density_option.setEnabled(False)
            self.input_mass_option.setEnabled(False)

    def density_changed(self):
        """If the density QLineEdit has gotten additional input, disable the density selection QComboBox and the mass
        selection QLineEdit. If the density QLineEdit has been cleared, enable them instead."""
        if self.input_density_option.text() == "":
            self.input_mass_option.setEnabled(True)
            self.select_density.setEnabled(True)
        else:
            self.input_mass_option.setEnabled(False)
            self.select_density.setEnabled(False)

    def mass_changed(self):
        """If the mass QLineEdit has gotten additional input, disable the density selection QComboBox and the density
            selection QLineEdit. If the mass QLineEdit has been cleared, enable them instead."""
        if self.input_mass_option.text() == "":
            self.input_density_option.setEnabled(True)
            self.select_density.setEnabled(True)
        else:
            self.input_density_option.setEnabled(False)
            self.select_density.setEnabled(False)

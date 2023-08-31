import os

from OCC.Core import BRepTools
from OCC.Core.AIS import AIS_Trihedron, AIS_Line
from OCC.Core.BRep import BRep_Builder
from OCC.Core.Geom import Geom_Axis2Placement, Geom_Line
from OCC.Core.Quantity import Quantity_Color
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.Quantity import Quantity_TOC_RGB, Quantity_NOC_RED, Quantity_NOC_GREEN, Quantity_NOC_BLUE
from OCC.Core.Prs3d import Prs3d_DatumParts_XAxis, Prs3d_DatumParts_YAxis, Prs3d_DatumParts_ZAxis

import json
import base64

from OCC.Core.gp import gp_Trsf, gp_Pnt, gp_Dir, gp_Ax1
from PyQt5 import QtWidgets

from .structures import Joint, Part


class Serializer:
    def __init__(self):
        self.f_name = None

    def serialize_joint(self, joint):
        component = joint.center_trihedron.Component()
        x_dir = component.XDirection()
        z_dir = component.Direction()
        joint_xdir = [x_dir.X(), x_dir.Y(), x_dir.Z()]
        joint_zdir = [z_dir.X(), z_dir.Y(), z_dir.Z()]
        return {
            "first_component": joint.first_component,
            "second_component": joint.second_component,
            "name": joint.name,
            "parent_uid": joint.parent_uid,
            "child_uid": joint.child_uid,
            "origin": joint.origin,
            "axis": joint.axis if joint.axis else None,
            "joint_type": joint.joint_type,
            "joint_friction": joint.joint_friction,
            "joint_xdir": joint_xdir,
            "joint_zdir": joint_zdir
        }

    def serialize_part(self, part_info):
        # Write shape to a temporary file
        temp_shape_file = "temp_shape.brep"
        BRepTools.breptools_Write(part_info.shape, temp_shape_file)

        # Read the temporary file and encode it as Base64
        with open(temp_shape_file, "rb") as file:
            shape_data_base64 = base64.b64encode(file.read()).decode()

        # Delete the temporary file
        os.remove(temp_shape_file)

        # Get the location transformation
        loc_trsf = part_info.loc.Transformation()

        # Extract the matrix components
        loc_matrix = [loc_trsf.Value(row + 1, col + 1) for row in range(3) for col in range(4)]

        return {
            "shape_data_base64": shape_data_base64,
            "name": part_info.name,
            "color": (part_info.color.Red(), part_info.color.Green(), part_info.color.Blue()),
            "loc": loc_matrix,
            "mass": part_info.mass,
            "density": part_info.density,
        }

    def deserialize_joint(self, joint_data):
        x_dir = joint_data["joint_xdir"]
        x_dir = gp_Dir(x_dir[0], x_dir[1], x_dir[2])

        z_dir = joint_data["joint_zdir"]
        z_dir = gp_Dir(z_dir[0], z_dir[1], z_dir[2])

        joint_dir = joint_data["axis"]
        joint_origin = joint_data["origin"]
        origin_point = gp_Pnt(joint_origin[0], joint_origin[1], joint_origin[2])

        if joint_dir is not None:
            direction = gp_Dir(joint_dir[0], joint_dir[1], joint_dir[2])

        loc = Geom_Axis2Placement(origin_point, z_dir, x_dir)
        joint_trihedron = AIS_Trihedron(loc)
        joint_trihedron.SetDrawArrows(True)
        joint_trihedron.SetSize(5)
        joint_trihedron.SetDatumPartColor(Prs3d_DatumParts_XAxis, Quantity_Color(Quantity_NOC_RED))
        joint_trihedron.SetDatumPartColor(Prs3d_DatumParts_YAxis, Quantity_Color(Quantity_NOC_GREEN))
        joint_trihedron.SetDatumPartColor(Prs3d_DatumParts_ZAxis, Quantity_Color(Quantity_NOC_BLUE))

        if joint_dir is not None:
            joint_axis_line = AIS_Line(Geom_Line(gp_Ax1(origin_point, direction)))
        else:
            joint_axis_line = None

        return Joint(
            first_component=joint_data["first_component"],
            second_component=joint_data["second_component"],
            parent_uid=joint_data["parent_uid"],
            child_uid=joint_data["child_uid"],
            origin=joint_data["origin"],
            axis=joint_data["axis"],
            joint_type=joint_data["joint_type"],
            joint_friction=joint_data["joint_friction"],
            center_trihedron=joint_trihedron,
            axis_line=joint_axis_line
        )

    def deserialize_part(self, part_data):
        # Decode the Base64 string and write it to a temporary file
        shape_data_base64 = part_data['shape_data_base64']
        temp_shape_file = "temp_shape.brep"
        with open(temp_shape_file, "wb") as file:
            file.write(base64.b64decode(shape_data_base64))

        # Read the shape from the temporary file
        shape = TopoDS_Shape()
        BRepTools.breptools_Read(shape, temp_shape_file, BRep_Builder())

        # Delete the temporary file
        os.remove(temp_shape_file)

        # Extract the RGB values
        red, green, blue = part_data["color"]

        # Create the color object
        color = Quantity_Color(red, green, blue, Quantity_TOC_RGB)

        # Create a transformation object from the matrix elements
        loc_trsf = gp_Trsf()
        matrix_elements = part_data["loc"]

        # Set the transformation matrix values
        loc_trsf.SetValues(
            matrix_elements[0], matrix_elements[1], matrix_elements[2], matrix_elements[3],
            matrix_elements[4], matrix_elements[5], matrix_elements[6], matrix_elements[7],
            matrix_elements[8], matrix_elements[9], matrix_elements[10], matrix_elements[11]
        )

        # Create a location object from the transformation
        loc = TopLoc_Location(loc_trsf)

        return Part(
            shape=shape,
            name=part_data["name"],
            color=color,
            loc=loc,
            mass=part_data["mass"],
            density=part_data["density"]
        )

    def load_model(self):
        f_name = self.prompt_open_file()
        if not f_name:
            return

        with open(f_name, "r") as file:
            loaded_data = json.load(file)

        joint_dict = {uid: self.deserialize_joint(joint_data) for uid, joint_data in loaded_data["joints"].items()}
        part_dict = {uid: self.deserialize_part(part_data) for uid, part_data in loaded_data["parts"].items()}
        label_dict = loaded_data["labels"]
        parent_dict = loaded_data["parents"]
        f_path = loaded_data["file_path"]

        return joint_dict, part_dict, label_dict, parent_dict, f_path

    def save_model(self, joint_dict, part_dict, label_dict, parent_dict, f_path):
        if self.f_name is None:
            self.f_name = self.prompt_save_file()
            if self.f_name is None:                 # Select folder cancelled
                return

        serialized_joints = {uid: self.serialize_joint(joint) for uid, joint in joint_dict.items()}
        serialized_parts = {uid: self.serialize_part(part_info) for uid, part_info in part_dict.items()}

        saved_data = {
            "joints": serialized_joints,
            "parts": serialized_parts,
            "labels": label_dict,
            "parents": parent_dict,
            "file_path": f_path
        }

        with open(self.f_name, "w") as file:
            json.dump(saved_data, file)

    def prompt_save_file(self):
        prompt = 'Specify name for saved file.'
        fname, selected_filter = QtWidgets.QFileDialog.getSaveFileName(None, prompt, './', "JSON files;;")

        if not fname:
            print("Save step cancelled.")
            return
        if not fname.endswith('.json'):
            fname += '.json'

        return fname

    def prompt_open_file(self):
        prompt = 'Select file to load'
        f_path, __ = QtWidgets.QFileDialog.getOpenFileName(
            None, prompt, './', "JSON files (*.json)")
        return f_path

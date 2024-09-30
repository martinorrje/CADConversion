import graphviz
import json
import logging

from PyQt5 import QtWidgets

from .structures import JointProperty, PartProperty

import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
import numpy as np
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.gp import gp_Trsf, gp_Pnt, gp_Dir
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop_VolumeProperties

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # set to DEBUG | INFO | ERROR


class ConversionClass:
    def __init__(self, part_dict, joint_dict):
        self.part_properties = {}      # Keyed by uid
        self.joint_properties = {}     # Keyed by uid
        self.uid_to_body_name = {}     # Mapping from uid to body_name
        self.uid_to_joint_name = {}    # Mapping from uid to joint_name
        self.get_properties(part_dict, joint_dict)

    def get_properties(self, part_dict, joint_dict):
        # Process parts
        for uid, part in part_dict.items():
            body_name = f"{part.name.replace(':', '_').replace(' ', '_')}_{uid}"
            self.part_properties[uid] = PartProperty(
                name=body_name,  # Processed name
                shape=part.shape,
                loc=part.loc,
                mass=part.mass,
                density=part.density
            )
            self.uid_to_body_name[uid] = body_name  # Map uid to body_name

        # Process joints
        for uid, joint in joint_dict.items():
            parent_uid = joint.parent_uid
            child_uid = joint.child_uid
            parent_name = self.uid_to_body_name[parent_uid]
            child_name = self.uid_to_body_name[child_uid]
            joint_name = joint.name.replace(':', '_').replace(' ', '_')
            self.joint_properties[uid] = JointProperty(
                name=joint_name,  # Processed name
                parent_uid=parent_uid,
                child_uid=child_uid,
                parent=parent_name,
                child=child_name,
                origin=joint.origin,
                axis=joint.axis,
                joint_type=joint.joint_type,
                joint_friction=joint.joint_friction
            )
            self.uid_to_joint_name[uid] = joint_name  # Map uid to joint_name

        self.get_inertial_properties()
        self.print_inertias()

    def get_inertial_properties(self):
        for uid, part in self.part_properties.items():
            shape = part.shape

            # Apply the inverse of part.loc to compute inertial properties in the body's local frame
            if part.loc and not part.loc.IsIdentity():
                trsf_inv = part.loc.Inverted().Transformation()
                shape = BRepBuilderAPI_Transform(shape, trsf_inv).Shape()

            properties = GProp_GProps()
            brepgprop_VolumeProperties(shape, properties)
            inertia_tensor = properties.MatrixOfInertia()
            com = properties.CentreOfMass()

            if part.mass is None:
                if part.density is not None:
                    mass = properties.Mass() * part.density
                else:
                    mass = properties.Mass()
                    part.density = 1
            else:
                mass = part.mass
                part.density = mass / properties.Mass()

            part.center_of_mass = [com.X(), com.Y(), com.Z()]
            part.mass = mass
            part.inertia = [[part.density * inertia_tensor.Value(i, j) for j in range(1, 4)] for i in range(1, 4)]

    def print_inertias(self):
        for uid, part in self.part_properties.items():
            print(f"{part.name} inertia:")
            for i in range(3):
                for j in range(3):
                    print(f'{round(part.inertia[i][j], 10)} ', end="")
                print()
            print(f"Mass: {part.mass} g")  # Change here if density units are changed
            print(f"Density: {part.density} g/mm^3")
            print(f"Center of mass: {part.center_of_mass}")
            print()
        print()


class MJCFGenerator(ConversionClass):
    def __init__(self, part_dict, joint_dict, output_dir='mjcf_output'):
        super().__init__(part_dict, joint_dict)
        self.output_dir = output_dir
        self.model = ET.Element('mujoco', attrib={'model': 'ImportedModel'})
        self.asset = ET.SubElement(self.model, 'asset')
        self.part_id_map = {}  # Keyed by uid
        self.processed_parts = set()
        self.mesh_paths = {}   # Keyed by uid
        self.create_worldbody()

        os.makedirs(self.output_dir, exist_ok=True)

    def add_default_light(self):
        # Add a default light source to the worldbody
        light_attrib = {
            'name': 'main_light',
            'pos': '0 0 2',
            'dir': '0 0 -1',
            'diffuse': '1 1 1',
            'specular': '0 0 0',
            'attenuation': '1 0 0',
            'cutoff': '100',
            'exponent': '0',
            'ambient': '0.1 0.1 0.1',
        }
        ET.SubElement(self.worldbody, 'light', attrib=light_attrib)

    def add_ground_plane(self):
        # Add a ground plane to the worldbody
        plane_attrib = {
            'name': 'ground',
            'type': 'plane',
            'pos': '0 0 0',
            'size': '10 10 0.1',
            'rgba': '0.8 0.9 0.8 1',
            'condim': '3',
            'material': 'ground_material'
        }
        ET.SubElement(self.worldbody, 'geom', attrib=plane_attrib)

        # Add a material for the ground plane in the asset
        material_attrib = {
            'name': 'ground_material',
            'rgba': '0.8 0.9 0.8 1',
            'specular': '0.1',
            'shininess': '0.1',
            'reflectance': '0'
        }
        ET.SubElement(self.asset, 'material', attrib=material_attrib)

    def create_worldbody(self):
        self.worldbody = ET.SubElement(self.model, 'worldbody')
        self.add_default_light()
        self.add_ground_plane()

    def generate(self, output_file='model.xml'):
        self.process_assets()

        root_uids = self.find_root_uids()

        logger.debug("Root parts: ")
        for uid in root_uids:
            logger.debug(self.part_properties[uid].name)

        for root_uid in root_uids:
            self.build_body(root_uid, parent_uid=None)

        self.add_joints()

        output_path = os.path.join(self.output_dir, output_file)
        self.write_xml(output_path)
        print(f'MJCF model written to {output_path}')

    def process_assets(self):
        for uid, part in self.part_properties.items():
            part_name = part.name
            stl_file = os.path.join(self.output_dir, f'{part_name}.stl')

            self.export_shape_to_stl(part.shape, stl_file, part.loc)

            self.mesh_paths[uid] = stl_file

            mesh_attrib = {
                'name': part_name,
                'file': os.path.basename(stl_file)
            }
            ET.SubElement(self.asset, 'mesh', attrib=mesh_attrib)

    def export_shape_to_stl(self, shape, stl_file, part_loc):
        if shape.IsNull():
            raise ValueError('Invalid shape provided for STL export.')

        # Apply the inverse of part_loc to transform the shape into the body's local frame
        if part_loc and not part_loc.IsIdentity():
            trsf_inv = part_loc.Inverted().Transformation()
            shape = BRepBuilderAPI_Transform(shape, trsf_inv).Shape()

        scale_trsf = gp_Trsf()
        scale_trsf.SetScale(gp_Pnt(0, 0, 0), 0.001)  # Scale from mm to meters

        # Apply scaling
        transformed_shape = BRepBuilderAPI_Transform(shape, scale_trsf).Shape()

        # Mesh and export the transformed shape
        mesh = BRepMesh_IncrementalMesh(transformed_shape, 0.0005)
        mesh.Perform()

        stl_writer = StlAPI_Writer()
        stl_writer.SetASCIIMode(False)
        stl_writer.Write(transformed_shape, stl_file)

    def find_root_uids(self):
        child_uids = set(joint.child_uid for joint in self.joint_properties.values())
        root_uids = [uid for uid in self.part_properties if uid not in child_uids]
        return root_uids

    def build_body(self, part_uid, parent_uid=None):
        part = self.part_properties[part_uid]

        # Get the absolute transformation of the current part
        part_trsf = part.loc.Transformation() if part.loc else gp_Trsf()
        part_pos, part_quat = self.trsf_to_pos_quat(part_trsf)
        part_pos = np.array(part_pos) * 0.001  # Convert mm to meters

        if parent_uid is None:
            # Root body, position and orientation are absolute
            rel_pos = part_pos
            rel_quat = part_quat
            parent_body = self.worldbody
        else:
            # Get the parent's absolute transformation
            parent_part = self.part_properties[parent_uid]
            parent_trsf = parent_part.loc.Transformation() if parent_part.loc else gp_Trsf()
            parent_pos, parent_quat = self.trsf_to_pos_quat(parent_trsf)
            parent_pos = np.array(parent_pos) * 0.001  # Convert mm to meters

            # Compute the difference in positions
            delta_pos = part_pos - parent_pos

            # Rotate the delta position into the parent body's frame
            parent_quat_inv = self.quaternion_inverse(parent_quat)
            rel_pos = self.rotate_vector_by_quaternion(delta_pos, parent_quat_inv)

            # Compute the relative orientation
            rel_quat = self.multiply_quaternions(parent_quat_inv, part_quat)

            parent_body = self.part_id_map[parent_uid]

        body_name = part.name

        body_attrib = {
            'name': body_name,
            'pos': ' '.join(map(str, rel_pos)),
            'quat': ' '.join(map(str, rel_quat))
        }

        body = ET.SubElement(parent_body, 'body', attrib=body_attrib)

        self.part_id_map[part_uid] = body

        self.add_inertial(body, part)

        self.add_geom(body, part)

        self.processed_parts.add(part_uid)

        # Recursively build child bodies
        child_joints = [joint for joint in self.joint_properties.values() if joint.parent_uid == part_uid]
        for joint in child_joints:
            child_uid = joint.child_uid
            if child_uid in self.part_properties:
                self.build_body(child_uid, parent_uid=part_uid)
            else:
                print(f'Warning: Child part with uid {child_uid} not found for parent with uid {part_uid}')

    def quaternion_inverse(self, quat):
        w, x, y, z = quat
        return np.array([w, -x, -y, -z]) / np.dot(quat, quat)

    def add_inertial(self, body, part):
        mass = part.mass * 0.001  # grams to kg

        inertia_tensor = np.array(part.inertia) * 1e-9  # g·mm² to kg·m²

        inertia_vector = [
            inertia_tensor[0][0],  # ixx
            inertia_tensor[1][1],  # iyy
            inertia_tensor[2][2],  # izz
            inertia_tensor[0][1],  # ixy
            inertia_tensor[0][2],  # ixz
            inertia_tensor[1][2]   # iyz
        ]

        com = np.array(part.center_of_mass) * 0.001  # mm to meters

        inertial_attrib = {
            'mass': f'{mass}',
            'pos': ' '.join(map(str, com)),
            'fullinertia': ' '.join(map(str, inertia_vector))
        }
        ET.SubElement(body, 'inertial', attrib=inertial_attrib)

    def add_geom(self, body, part):
        part_name = part.name

        geom_attrib = {
            'type': 'mesh',
            'mesh': part_name,
            'rgba': '0.8 0.6 0.4 1',  # Placeholder color
            'contype': '1',
            'conaffinity': '1'
        }
        ET.SubElement(body, 'geom', attrib=geom_attrib)

    def add_joints(self):
        for joint in self.joint_properties.values():
            if joint.joint_type != 'Fixed':
                self.add_joint(joint)

    def trsf_to_pos_quat(self, trsf):
        # Extract translation
        translation = trsf.TranslationPart()
        pos = np.array([translation.X(), translation.Y(), translation.Z()])

        # Extract rotation as a quaternion
        rotation_quat = trsf.GetRotation()

        # Get the quaternion components
        w = rotation_quat.W()
        x = rotation_quat.X()
        y = rotation_quat.Y()
        z = rotation_quat.Z()

        quat = np.array([w, x, y, z])

        # Normalize the quaternion
        quat = quat / np.linalg.norm(quat)

        return pos, quat

    def compute_relative_transform(self, parent_pos, parent_quat, child_pos, child_quat):
        # Compute the inverse (conjugate) of the parent's rotation quaternion
        parent_quat_inv = np.array([parent_quat[0], -parent_quat[1], -parent_quat[2], -parent_quat[3]])

        # Compute the relative orientation
        rel_quat = self.multiply_quaternions(parent_quat_inv, child_quat)
        rel_quat = rel_quat / np.linalg.norm(rel_quat)  # Normalize

        # Compute relative position
        delta_pos = child_pos - parent_pos
        rel_pos = self.rotate_vector_by_quaternion(delta_pos, parent_quat_inv)

        return rel_pos, rel_quat

    def rotate_vector_by_quaternion(self, vector, quat):
        # Quaternion-vector multiplication q * v * q^{-1}
        q = quat
        q_inv = self.quaternion_inverse(quat)

        v_quat = np.concatenate([[0], vector])
        rotated_v = self.multiply_quaternions(self.multiply_quaternions(q, v_quat), q_inv)
        return rotated_v[1:]  # Return the vector part

    def multiply_quaternions(self, q1, q2):
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return np.array([
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        ])

    def add_joint(self, joint):
        child_body = self.part_id_map.get(joint.child_uid)
        parent_body = self.part_id_map.get(joint.parent_uid)

        if child_body is None or parent_body is None:
            print(
                f"Warning: Child body with uid {joint.child_uid} or parent body with uid {joint.parent_uid} not found for joint {joint.name}")
            return

        # Get the parent's absolute transformation
        child_part = self.part_properties[joint.child_uid]
        child_trsf = child_part.loc.Transformation() if child_part.loc else gp_Trsf()
        child_pos, child_quat = self.trsf_to_pos_quat(child_trsf)
        child_pos = np.array(child_pos) * 0.001  # Convert mm to meters

        # Joint origin is given in global coordinates
        joint_origin = np.array(joint.origin) * 0.001  # Convert mm to meters

        # Compute joint position relative to parent body's frame
        delta_pos = joint_origin - child_pos
        child_quat_inv = self.quaternion_inverse(child_quat)
        rel_pos = self.rotate_vector_by_quaternion(delta_pos, child_quat_inv)

        joint_attrib = {
            'name': joint.name,
            'type': self.get_mjcf_joint_type(joint.joint_type),
            'pos': ' '.join(map(str, rel_pos))
        }

        if joint_attrib['type'] != 'fixed':
            if joint.axis is not None:
                # Joint axis in global coordinates
                axis_global = np.array(joint.axis)
                # Rotate the axis into the parent body's frame
                rel_axis = self.rotate_vector_by_quaternion(axis_global, child_quat_inv)
                rel_axis = rel_axis / np.linalg.norm(rel_axis)
                joint_attrib['axis'] = ' '.join(map(str, rel_axis))
            else:
                print(f"Warning: No axis provided for joint {joint.name}. Defaulting to [0, 0, 1]")
                joint_attrib['axis'] = '0 0 1'

        # Add the joint to the child body
        ET.SubElement(child_body, 'joint', attrib=joint_attrib)

    def get_mjcf_joint_type(self, joint_type):
        if joint_type == 'Revolute':
            return 'hinge'
        elif joint_type == 'Prismatic':
            return 'slide'
        elif joint_type == 'Fixed':
            return 'fixed'
        else:
            raise ValueError(f"Unsupported joint type: {joint_type}")

    def write_xml(self, output_file):
        rough_string = ET.tostring(self.model, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ")

        with open(output_file, 'w') as f:
            f.write(pretty_xml)

    def get_mjcf_folder(self):
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        directory = QtWidgets.QFileDialog.getExistingDirectory(None, "Select Directory")
        if not directory:
            print("Convert to MJCF cancelled")
            return
        return directory


link_endpoint_count = {}


class LinearGraphConverter(ConversionClass):
    def __init__(self, part_dict, joint_dict):
        super().__init__(part_dict, joint_dict)
        self.translation_index = 0
        self.rotation_index = 0

    def get_graph_folder(self):
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        directory = QtWidgets.QFileDialog.getExistingDirectory(None, "Select Directory")
        if not directory:
            print("Convert to graph cancelled")
            return
        return directory

    def convert_to_json(self, directory):
        if directory:
            file_name = directory + '/data.json'

            # Prepare json
            self.prepare_json(file_name)

            # Convert each part to a link
            for _, part_property in self.part_properties.items():
                self.parse_link(file_name, part_property)

            # Convert each joint to a joint
            for _, joint_property in self.joint_properties.items():
                self.parse_joint(file_name, joint_property)

    def prepare_json(self, json_file):
        initial_data = {
            'links': [],
            'joints': [],
            'rotation_graph': {'edges': [], 'vertices': []},
            'translation_graph': {'edges': [], 'vertices': []}
        }
        with open(json_file, 'w') as file:
            json.dump(initial_data, file)

    def parse_link(self, json_file, part_property):
        link_data = {
            'link_name': part_property.name.replace(':', '_'),
            'link_origin': part_property.center_of_mass,
            'link_mass': part_property.mass,
            'link_inertia': part_property.inertia
        }

        with open(json_file, 'r') as file:
            existing_data = json.load(file)

        existing_data['links'].append(link_data)

        rotation_edge = {
            'from': 'base_link',
            'to': link_data['link_name'],
            'type': 'center_of_mass_edge',
            'label': f'm_{self.rotation_index}'
        }

        rotation_vertex = {
            'name': link_data['link_name']
        }

        translation_edge = {
            'from': 'base_link',
            'to': link_data['link_name'],
            'type': 'center_of_mass_edge',
            'label': f'm_{self.translation_index}'
        }
        translation_vertex = rotation_vertex.copy()

        self.translation_index += 1
        self.rotation_index += 1

        existing_data['rotation_graph']['edges'].append(rotation_edge)
        existing_data['rotation_graph']['vertices'].append(rotation_vertex)
        existing_data['translation_graph']['edges'].append(translation_edge)
        existing_data['translation_graph']['vertices'].append(translation_vertex)

        # Write the updated data back to the file
        with open(json_file, 'w') as file:
            json.dump(existing_data, file, indent=4)

    def parse_joint(self, json_file, joint_property):
        joint_parent = joint_property.parent.replace(':', '_')
        joint_child = joint_property.child.replace(':', '_')

        # Don't include friction if it's a fixed joint
        if joint_property.joint_type == 'Fixed':
            joint_data = {
                'name': joint_property.name.replace(':', '_'),
                'type': joint_property.joint_type,
                'origin': joint_property.origin,
                'parent': joint_parent,
                'child': joint_child,
                'axis': joint_property.axis,
            }
        else:
            joint_data = {
                'name': joint_property.name.replace(':', '_'),
                'type': joint_property.joint_type,
                'origin': joint_property.origin,
                'parent': joint_parent,
                'child': joint_child,
                'axis': joint_property.axis,
                'friction': joint_property.joint_friction
            }

        if joint_parent not in link_endpoint_count:
            link_endpoint_count[joint_parent] = 0  # Initialize the count for this parent if it doesn't exist
        if joint_child not in link_endpoint_count:
            link_endpoint_count[joint_child] = 0
        link_endpoint_count[joint_parent] += 1  # Increment the count for this parent
        link_endpoint_count[joint_child] += 1

        if joint_parent != 'base_link':
            parent_end_point = {
                'name': f'{joint_parent}_end_point_{link_endpoint_count[joint_parent]}'
            }
            translation_edge_1 = {
                'from': f'{joint_parent}_end_point_{link_endpoint_count[joint_parent]}',
                'to': f'{joint_child}_end_point_{link_endpoint_count[joint_child]}',
                'type': 'joint_edge',
                'label': f'h_{self.translation_index}'
            }

            translation_edge_2 = {
                'from': joint_parent,
                'to': f'{joint_parent}_end_point_{link_endpoint_count[joint_parent]}',
                'type': 'body_fixed_vector',
                'label': f'r_{self.translation_index + 1}'
            }

            self.translation_index += 2
        else:
            translation_edge_0 = {  # Only for base_link
                'from': 'base_link',
                'to': f'{joint_child}_end_point_{link_endpoint_count[joint_child]}',
                'label': f'h_{self.translation_index}'
            }

            self.translation_index += 1

        child_end_point = {
            'name': f'{joint_child}_end_point_{link_endpoint_count[joint_child]}'
        }

        translation_edge_3 = {
            'from': joint_child,
            'to': f'{joint_child}_end_point_{link_endpoint_count[joint_child]}',
            'type': 'body_fixed_vector',
            'label': f'r_{self.translation_index}'
        }

        rotation_edge = {
            'from': joint_parent,
            'to': joint_child,
            'type': 'joint_edge',
            'label': f'h_{self.rotation_index}'
        }

        self.translation_index += 1
        self.rotation_index += 1

        with open(json_file, 'r') as file:
            existing_data = json.load(file)

        existing_data['rotation_graph']['edges'].append(rotation_edge)

        if joint_parent != 'base_link':
            existing_data['translation_graph']['edges'].append(translation_edge_1)
            existing_data['translation_graph']['vertices'].append(parent_end_point)
            existing_data['translation_graph']['edges'].append(translation_edge_2)
        else:
            existing_data['translation_graph']['edges'].append(translation_edge_0)          # For base_link

        existing_data['translation_graph']['edges'].append(translation_edge_3)
        existing_data['translation_graph']['vertices'].append(child_end_point)

        existing_data['joints'].append(joint_data)

        with open(json_file, 'w') as file:
            json.dump(existing_data, file, indent=4)


def create_graph(json_file, graph_type):
    with open(json_file, 'r') as file:
        data = json.load(file)

    # Create a new directed graph
    graph = graphviz.Digraph(format='png')

    # Add the vertices (nodes)
    for vertex in data[graph_type]['vertices']:
        graph.node(vertex['name'])

    # Add the edges
    for edge in data[graph_type]['edges']:
        graph.edge(edge['from'], edge['to'], label=edge['label'])

    # Save the graph to a file
    graph.render(filename=f'{graph_type}', directory=os.path.dirname(json_file) + '/', cleanup=True)
import os

import graphviz
from OCC.Core.BRepGProp import brepgprop_VolumeProperties
from OCC.Core.GProp import GProp_GProps

import json

from PyQt5 import QtWidgets

from .structures import JointProperty, PartProperty

link_endpoint_count = {}


class LinearGraphConverter:
    def __init__(self):
        self.part_properties = {}
        self.joint_properties = {}
        self.translation_index = 0
        self.rotation_index = 0

    def convert_to_graph(self, part_dict, joint_dict):
        self.part_properties = {}
        self.joint_properties = {}
        self.translation_index = 0
        self.rotation_index = 0
        for uid, part in part_dict.items():
            self.part_properties[uid] = PartProperty(name=part.name, shape=part.shape, mass=part.mass,
                                                     density=part.density)
        for uid, joint in joint_dict.items():
            self.joint_properties[uid] = JointProperty(name=joint.name, parent=part_dict[joint.parent_uid].name,
                                                       child=part_dict[joint.child_uid].name, origin=joint.origin,
                                                       axis=joint.axis, joint_type=joint.joint_type,
                                                       joint_friction=joint.joint_friction)
        self.get_inertial_properties()
        self.print_inertias()

    def get_inertial_properties(self):
        for uid in self.part_properties:
            properties = GProp_GProps()
            brepgprop_VolumeProperties(self.part_properties[uid].shape, properties)
            inertia_tensor = properties.MatrixOfInertia()
            com = properties.CentreOfMass()

            if self.part_properties[uid].mass is None:
                if self.part_properties[uid].density is not None:
                    mass = properties.Mass() * self.part_properties[uid].density
                    print(f"{self.part_properties[uid].name}: {mass}")
                else:
                    mass = properties.Mass()
                    # If neither mass nor density is specified, assume density of 1
                    self.part_properties[uid].density = 1
            else:
                mass = self.part_properties[uid].mass
                self.part_properties[uid].density = mass / properties.Mass()

            self.part_properties[uid].center_of_mass = [com.X(), com.Y(), com.Z()]
            self.part_properties[uid].mass = mass
            # If densities are in kg/mm3, multiply be 1000 to get the inertia values in units of g*mm^2
            # Right now densities are in g/mm3, so no need for it.
            self.part_properties[uid].inertia = [[self.part_properties[uid].density * inertia_tensor.Value(i, j) for j in range(1, 4)] for i in range(1, 4)]

    def print_inertias(self):
        for uid in self.part_properties:
            print(f"{self.part_properties[uid].name} inertia: ")
            for i in range(3):
                for j in range(3):
                    print(f'{round(self.part_properties[uid].inertia[i][j], 10)} ', end="")
                print()
            print(f"Mass: {self.part_properties[uid].mass} g")              # Change here if density units are changed
            print(f"Density: {self.part_properties[uid].density} g/mm3")
            print(f"Center of mass: {self.part_properties[uid].center_of_mass}")
            print()
        print()

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
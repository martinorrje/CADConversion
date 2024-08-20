import re
import logging
import os
import pathlib
import shutil
from dataclasses import dataclass
import xml.etree.ElementTree as ET

from OCC.Core.StlAPI import StlAPI_Writer
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Trsf

logger = logging.getLogger(__name__)


@dataclass
class LabelEntry:
    ENTRY: str
    NAME: str
    PARENT_UID: str


class MujConverter:

    @staticmethod
    def rel_trf(trf1: gp_Trsf, trf2: gp_Trsf) -> gp_Trsf:
        v12 = gp_Vec(
            gp_Pnt(trf1.TranslationPart()), gp_Pnt(trf2.TranslationPart())
        )
        q12 = trf1.GetRotation()
        q12.Invert()
        q2 = trf2.GetRotation()
        q12.Multiply(q2)
        trf12 = gp_Trsf()
        trf12.SetTranslation(v12)
        trf12rot = gp_Trsf()
        trf12rot.SetRotation(q12)
        trf12.Multiply(trf12rot)
        return trf12

    @staticmethod
    def trf_to_pos(trf: gp_Trsf):
        tr = trf.TranslationPart()
        return [tr.X(), tr.Y(), tr.Z()]

    @staticmethod
    def trf_to_axisangle(trf: gp_Trsf):
        v = gp_Vec()
        a = trf.GetRotation().GetVectorAndAngle(v)
        return [v.X(), v.Y(), v.Z(), a]

    @staticmethod
    def trf_to_quat(trf: gp_Trsf):
        q = trf.GetRotation()
        return [q.W(), q.X(), q.Y(), q.Z()]

    @staticmethod
    def loc_to_pos(loc: TopLoc_Location):
        return MujConverter.trf_to_pos(loc.Transformation())

    def __init__(
        self, joints, parts, labels, parents, output_dir, *args, pos_scale_factor=0.01
    ) -> None:
        self._JOINTS = joints
        self._PARTS = parts

        self.output_dir = pathlib.Path(output_dir)

        # Use a more convenient representation for labels entries
        labels = {
            k: LabelEntry(
                ENTRY=v["entry"],
                NAME=v["name"],
                PARENT_UID=v["parent_uid"],
            )
            for k, v in labels.items()
        }

        self._LABELS = labels
        self._PARENTS = parents

        # Find root assembly
        root_assemblys = list(
            filter(lambda x: x[1].PARENT_UID is None, self.LABELS.items())
        )
        if len(root_assemblys) != 1:
            logger.error(
                f"The number of roots assemblys, {root_assemblys}, are not exacly one"
            )
            return
        self._ROOT_ASSEMBLY = root_assemblys[0]

        self._POS_SCALE_FACTOR = pos_scale_factor
        self._MAT_PLANE_NAME = "MatPlane"
        self._TEX_PLANE_NAME = "texplane"

    @property
    def JOINTS(self):
        return self._JOINTS

    @property
    def PARTS(self):
        return self._PARTS

    @property
    def LABELS(self):
        return self._LABELS

    @property
    def PARENTS(self):
        return self._PARENTS

    @property
    def ROOT_ASSEMPLY(self):
        return self._ROOT_ASSEMBLY

    @property
    def POS_SCALE_FACTOR(self):
        return self._POS_SCALE_FACTOR

    @property
    def MAT_PLANE_NAME(self):
        return self._MAT_PLANE_NAME

    @property
    def TEX_PLANE_NAME(self):
        return self._TEX_PLANE_NAME

    def convert(
        self,
        base_link_name_pattern=r"base",
        options={"gravity": "0 0 -9.81"},
    ):
        # Begin by clearing directory for us to be able to use it
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir)

        # Find base links
        base_links = list(
            filter(
                lambda x: re.match(base_link_name_pattern, x[1].NAME),
                self.LABELS.items(),
            )
        )
        if len(base_links) == 0:
            logger.error(f"Found no base links")
            return

        # Construct graph in the form of a successor list
        successors = self._create_successor_list()

        mu_model = ET.Element(
            "mujoco", attrib={"model": self.ROOT_ASSEMPLY[1].NAME}
        )
        ET.SubElement(mu_model, "option", attrib=options)
        assets = ET.SubElement(mu_model, "asset")

        # Add floor assets
        ET.SubElement(
            assets,
            "texture",
            attrib={
                "name": self.TEX_PLANE_NAME,
                "builtin": "checker",
                "height": "100",
                "rgb1": "0 0 0",
                "rgb2": "0.8 0.8 0.8",
                "type": "2d",
                "width": "100",
            },
        )
        ET.SubElement(
            assets,
            "material",
            attrib={
                "name": self.MAT_PLANE_NAME,
                "reflectance": "0.5",
                "shininess": "1",
                "specular": "1",
                "texrepeat": "300 300",
                "texture": self.TEX_PLANE_NAME,
            },
        )

        # Attach world body to model
        world = ET.SubElement(mu_model, "worldbody")

        # Add actuator element
        actuator = ET.SubElement(mu_model, "actuator")

        self.assets = assets
        self.world = world
        self.actuator = actuator

        # Add light
        ET.SubElement(
            world,
            "light",
            attrib={
                "cutoff": "100",
                "diffuse": "1 1 1",
                "dir": "0 0 -1.3",
                "directional": "true",
                "exponent": "1",
                "pos": "40 40 40",
                "specular": "0.1 0.1 0.1",
            },
        )

        # Add a plane to the world
        ET.SubElement(
            world,
            "geom",
            attrib={
                "name": "floor",
                "material": self.MAT_PLANE_NAME,
                "type": "plane",
                "size": "40 40 40",
                "rgba": "0.8 0.9 0.8 1",
                "pos": "0 0 -1",
                "conaffinity": "0",
            },
        )

        for base_link_id, _ in base_links:
            base_link = self.PARTS[base_link_id]
            pos = MujConverter.trf_to_pos(base_link.loc.Transformation())
            quat = MujConverter.trf_to_quat(base_link.loc.Transformation())
            # === START DEBUGGING ===
            logger.debug(f"base link position (absolute): {pos}")
            logger.debug(f"base link orientation (absolute): {quat}")
            # === END DEBUGGING ===
            base_link_body = self._add_body(world, base_link, pos, quat)
            ET.SubElement(base_link_body, "freejoint")
            self._add_geom(base_link_body, base_link)

            # Construct tree with base_link as root.
            visited_links = set()
            visited_joints = set()
            visited_links.add(base_link_id)
            queue = [(base_link_body, base_link_id, base_link)]

            while len(queue) > 0:
                parent_body, parent_id, parent = queue.pop(0)
                if parent_id in successors:
                    for joint_id, child_id in successors[parent_id]:
                        joint = self.JOINTS[joint_id]
                        child = self.PARTS[child_id]

                        # We construct a kinematic tree and deal with cut-joints
                        # later.
                        if child_id not in visited_links:
                            child_trf = child.loc.Transformation()

                            # === START DEBUGGING ===
                            logger.debug(
                                f"{child.name} position (absolute): {MujConverter.trf_to_pos(child_trf)}"
                            )
                            logger.debug(
                                f"{child.name} orientation (absolute): {MujConverter.trf_to_quat(child_trf)}"
                            )
                            # === END DEBUGGING ===

                            # Compute body position and orientation relative to
                            # parent.
                            trf = MujConverter.rel_trf(
                                parent.loc.Transformation(),
                                child_trf,
                            )
                            pos = MujConverter.trf_to_pos(trf)
                            quat = MujConverter.trf_to_quat(trf)

                            # If it is a fixed joint we add the child geometry
                            # to the parent.
                            if joint.joint_type == "Fixed":
                                self._add_geom(parent_body, child, pos, quat)

                                # The parent body remains the parent body
                                queue.append((parent_body, child_id, child))

                            # Otherwise we add the joint and the geometry to the
                            # child body
                            else:
                                # Add to parent body.
                                child_body = self._add_body(
                                    parent_body, child, pos, quat
                                )

                                # Compute joint origin in child frame of reference
                                joint_origin = gp_Pnt(
                                    joint.origin[0],
                                    joint.origin[1],
                                    joint.origin[2],
                                ).Transformed(child_trf.Inverted())

                                # Compute joint axis in child frame of reference
                                joint_axis = (
                                    child_trf.Inverted()
                                    .GetRotation()
                                    .Multiply(
                                        gp_Vec(
                                            joint.axis[0],
                                            joint.axis[1],
                                            joint.axis[2],
                                        )
                                    )
                                )

                                joint_elem = self._add_joint(
                                    actuator,
                                    child_body,
                                    joint,
                                    pos=[
                                        joint_origin.X(),
                                        joint_origin.Y(),
                                        joint_origin.Z(),
                                    ],
                                    axis=[
                                        joint_axis.X(),
                                        joint_axis.Y(),
                                        joint_axis.Z(),
                                    ],
                                )
                                if joint_elem is None:
                                    return

                                # Add part geometry
                                self._add_geom(child_body, child)

                                # The child body is the next parent body
                                queue.append((child_body, child_id, child))

                            # Update iteration state.
                            visited_links.add(child_id)
                            visited_joints.add(joint_id)

            # We currently do not support cut-joints.
            if self._has_cut_joints(visited_joints):
                return

        ET.indent(mu_model)

        with open(self.output_dir / "model.xml", "w+") as f:
            f.write(ET.tostring(mu_model, encoding="unicode"))

    def _create_successor_list(self):
        successors = {}
        for joint_label, joint in self.JOINTS.items():
            if joint.parent_uid not in successors:
                successors[joint.parent_uid] = set()
            if joint.child_uid not in successors:
                successors[joint.child_uid] = set()
            successors[joint.parent_uid].add((joint_label, joint.child_uid))
            successors[joint.child_uid].add((joint_label, joint.parent_uid))
        return successors

    def _scale_pos(self, pos):
        return list(map(lambda p: self.POS_SCALE_FACTOR * p, pos))

    def _add_mesh(self, name, shape):
        # Converts mesh from internal representation to STL
        chrange = lambda a, b: set(chr(i) for i in range(ord(a), (ord(b)+1)))
        valid_chars = chrange('a', 'z') | chrange('A', 'Z')
        filename = name
        for c in name:
            if (not c.isalnum()) and (c not in ["_", "-"]):
                filename = filename.replace(c, "_")

        filename = filename + ".stl"
        filepath = self.output_dir / filename

        w = StlAPI_Writer()
        w.SetASCIIMode(False)
        w.Write(shape, str(filepath))
        ET.SubElement(
            self.assets,
            "mesh",
            attrib={
                "name": name,
                #"scale": "0.001 0.001 0.001",
                "file": str(filename),
            }
        )

    def _add_body(self, parent, part, pos, quat):
        pos = self._scale_pos(pos)
        return ET.SubElement(
            parent,
            "body",
            attrib={
                "name": part.name,
                "pos": f"{pos[0]} {pos[1]} {pos[2]}",
                "quat": f"{quat[0]} {quat[1]} {quat[2]} {quat[3]}",
            },
        )

    def _add_joint(self, actuator, body, joint, pos, axis):
        pos = self._scale_pos(pos)
        if joint.joint_type == "Revolute":
            joint_elem = ET.SubElement(
                body,
                "joint",
                attrib={
                    "name": joint.name,
                    "pos": f"{pos[0]} {pos[1]} {pos[2]}",
                    "axis": f"{axis[0]} {axis[1]} {axis[2]}",
                },
            )
            ET.SubElement(
                actuator,
                "position",
                attrib={"name": joint.name, "joint": joint.name},
            )
            return joint_elem
        else:
            logger.error(f"Unsupported joint type, {joint.joint_type}, for joint, {joint.name}")
            return

    def _add_geom(self, body, part, pos=None, quat=None):
        #geom = ET.SubElement(
        #    body,
        #    "geom",
        #    attrib={"type": "box", "size": "0.02 0.02 0.02"},
        #)
        self._add_mesh(part.name, part.shape)
        geom = ET.SubElement(body, "geom", attrib={
                "type": "mesh",
                "name": f"{part.name}__{part.name}",
                "mesh": part.name,
                "group": "0",
                "friction": "0.2 0.005 0.0001",
                "euler": "0 -0 0",
            },
        )
        if part.mass is not None:
            geom.set("mass", str(part.mass))
        if part.density is not None:
            geom.set("density", str(part.density))
        if pos is not None:
            pos = self._scale_pos(pos)
            geom.set("pos", f"{pos[0]} {pos[1]} {pos[2]}")
        if quat is not None:
            geom.set("quat", f"{quat[0]} {quat[1]} {quat[2]} {quat[3]}")
        return geom

    def _has_cut_joints(self, visited_joints):
        cut_joints = list(
            filter(lambda j: j[0] not in visited_joints, self.JOINTS.items())
        )
        if len(cut_joints) > 0:
            logger.error(
                f"Found the cut-joints, {list(map(lambda j: j[1].name ,cut_joints))}, when constructing the kinematic tree. Cut-joints are not yet supported."
            )
            return True
        return False

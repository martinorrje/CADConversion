from dataclasses import dataclass
import typing


@dataclass
class Joint:
    first_component: "typing.Any"
    second_component: "typing.Any"
    name: str
    parent_uid: str
    child_uid: str
    origin: "typing.Any"
    axis: "typing.Any"
    center_trihedron: "typing.Any"
    axis_line: "typing.Any"
    joint_type: "typing.Any"
    joint_friction: "typing.Any"
    item: "typing.Any"

    def __init__(
        self,
        first_component,
        second_component,
        parent_uid,
        child_uid,
        origin,
        axis,
        center_trihedron,
        axis_line,
        joint_type,
        joint_friction,
        item=None,
    ):
        self.first_component = first_component
        self.second_component = second_component
        self.name = f"{first_component} to {second_component}"
        self.parent_uid = parent_uid
        self.child_uid = child_uid
        self.origin = origin
        self.axis = axis
        self.center_trihedron = center_trihedron
        self.axis_line = axis_line
        self.joint_type = joint_type
        self.joint_friction = joint_friction
        self.item = item


@dataclass
class Part:
    shape: "typing.Any"
    name: str
    color: "typing.Any"
    loc: "typing.Any"
    mass: "typing.Any" = None
    density: "typing.Any" = None


class JointProperty:
    def __init__(
        self, name, parent, child, origin, axis, joint_type, joint_friction
    ):
        self.name = name
        self.parent = parent
        self.child = child
        self.origin = origin
        self.axis = axis
        self.joint_type = joint_type
        self.joint_friction = joint_friction


class PartProperty:
    def __init__(
        self,
        name,
        shape,
        center_of_mass=None,
        inertia=None,
        mass=None,
        density=None,
    ):
        self.name = name
        self.shape = shape
        self.center_of_mass = center_of_mass
        self.inertia = inertia
        self.mass = mass
        self.density = density

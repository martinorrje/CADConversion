from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from OCC.Core.AIS import AIS_Trihedron, AIS_Line
from OCC.Core.Quantity import Quantity_Color
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import TopoDS_Shape

from .serialization import Serializable


@dataclass
class Joint(Serializable):
    first_component: str
    second_component: str
    parent_uid: str
    child_uid: str
    origin: List[float]
    axis: List[float]
    center_trihedron: AIS_Trihedron
    axis_line: AIS_Line
    joint_type: str
    joint_friction: float
    item: Optional["PyQt5.QtWidgets.QTreeWidgetItem"] = None

    @property
    def name(self):
        return f"{self.first_component} to {self.second_component}"


@dataclass
class Part(Serializable):
    shape: TopoDS_Shape
    name: str
    color: Quantity_Color
    loc: TopLoc_Location
    mass: Optional[float] = None
    density: Optional[float] = None


@dataclass
class JointProperty:
    name: str
    parent: str
    child: str
    origin: List[float]
    axis: List[float]
    joint_type: str
    joint_friction: float


@dataclass
class PartProperty:
    name: str
    shape: TopoDS_Shape
    center_of_mass: Optional[Any] = None
    inertia: Optional[Any] = None
    mass: Optional[float] = None
    density: Optional[float] = None


# TODO: Refactor other files to use serializable structures instead of keeping track of dicts

@dataclass
class Label(Serializable):
    entry: str
    name: str
    parent_uid: Optional[str]
    ref_entry: Optional[str]
    is_assembly: bool


@dataclass
class Model(Serializable):
    step_file: str
    parents: Dict[str, List[str]]
    labels: Dict[str, Label]
    joints: Dict[str, Joint]
    parts: Dict[str, Part]

from dataclasses import dataclass
from typing import Optional, List

from OCC.Core.AIS import AIS_Trihedron, AIS_Line

from .utils import Serializable


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

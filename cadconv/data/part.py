from dataclasses import dataclass
from typing import Optional

from OCC.Core.Quantity import Quantity_Color
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import TopoDS_Shape

from .utils import Serializable


@dataclass
class Part(Serializable):
    shape: TopoDS_Shape
    name: str
    color: Quantity_Color
    loc: TopLoc_Location
    mass: Optional[float] = None
    density: Optional[float] = None

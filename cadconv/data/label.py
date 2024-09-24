from dataclasses import dataclass
from typing import Optional

from OCC.Core.TopLoc import TopLoc_Location

from .utils import Serializable


@dataclass
class Label(Serializable):
    entry: str
    name: str
    loc: TopLoc_Location
    parent_uid: Optional[str] = None
    ref_entry: Optional[str] = None
    is_assembly: bool = False
    is_simple_shape: bool = False

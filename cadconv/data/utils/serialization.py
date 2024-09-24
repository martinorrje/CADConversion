"""
Serialization/deserialization of custom types.
"""

import base64
import inspect
import tempfile

from marshmallow import Schema, fields
from marshmallow.fields import Field, Nested, ValidationError
from typing import get_origin, get_args, Union

from OCC.Core import BRepTools
from OCC.Core.AIS import AIS_Trihedron, AIS_Line
from OCC.Core.BRep import BRep_Builder
from OCC.Core.Geom import Geom_Axis2Placement, Geom_Line
from OCC.Core.Quantity import Quantity_Color
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.Quantity import Quantity_TOC_RGB, Quantity_NOC_RED, Quantity_NOC_GREEN, Quantity_NOC_BLUE
from OCC.Core.Prs3d import Prs3d_DatumParts_XAxis, Prs3d_DatumParts_YAxis, Prs3d_DatumParts_ZAxis
from OCC.Core.gp import gp_Trsf, gp_Pnt, gp_Dir, gp_Ax1


class Field_AIS_Trihedron(Field):
    def _serialize(self, value, attr, obj, **kwargs):
        #assert isinstance(value, AIS_Trihedron)
        component = value.Component()
        origin = component.Location()
        z_dir = component.Direction()
        x_dir = component.XDirection()
        return {
            "origin": [float(origin.X()), float(origin.Y()), float(origin.Z())],
            "z_dir": [float(z_dir.X()), float(z_dir.Y()), float(z_dir.Z())],
            "x_dir": [float(x_dir.X()), float(x_dir.Y()), float(x_dir.Z())],
        }

    def _deserialize(self, value, attr, data, **kwargs):
        origin = gp_Pnt(value["origin"][0], value["origin"][1], value["origin"][2])
        z_dir = gp_Dir(value["z_dir"][0], value["z_dir"][1], value["z_dir"][2])
        x_dir = gp_Dir(value["x_dir"][0], value["x_dir"][1], value["x_dir"][2])

        loc = Geom_Axis2Placement(origin, z_dir, x_dir)
        joint_trihedron = AIS_Trihedron(loc)
        joint_trihedron.SetDrawArrows(True)
        joint_trihedron.SetSize(5)
        joint_trihedron.SetDatumPartColor(Prs3d_DatumParts_XAxis, Quantity_Color(Quantity_NOC_RED))
        joint_trihedron.SetDatumPartColor(Prs3d_DatumParts_YAxis, Quantity_Color(Quantity_NOC_GREEN))
        joint_trihedron.SetDatumPartColor(Prs3d_DatumParts_ZAxis, Quantity_Color(Quantity_NOC_BLUE))
        return joint_trihedron


class Field_AIS_Line(Field):
    def _serialize(self, value, attr, obj, **kwargs):
        #assert isinstance(value, AIS_Line)
        ax1 = value.Line().Position()
        loc = ax1.Location()
        dir = ax1.Direction()
        return {
            "loc": [float(loc.X()), float(loc.Y()), float(loc.Z())],
            "dir": [float(dir.X()), float(dir.Y()), float(dir.Z())],
        }

    def _deserialize(self, value, attr, data, **kwargs):
        loc = gp_Pnt(value["loc"][0], value["loc"][1], value["loc"][2])
        dir = gp_Dir(value["dir"][0], value["dir"][1], value["dir"][2])
        ax1 = gp_Ax1(loc, dir)
        return AIS_Line(Geom_Line(ax1))


class Field_TopoDS_Shape(Field):
    def _serialize(self, value, attr, obj, **kwargs):
        #assert isinstance(value, TopoDS_Shape)
        with tempfile.NamedTemporaryFile(suffix=".brep") as tf:
            BRepTools.breptools_Write(value, tf.name)
            tf.file.seek(0)
            shape_base64 = base64.b64encode(tf.file.read()).decode("utf-8")

        return shape_base64

    def _deserialize(self, value, attr, data, **kwargs):
        shape = TopoDS_Shape()
        with tempfile.NamedTemporaryFile(suffix=".brep") as tf:
            tf.file.write(base64.b64decode(value))
            tf.file.flush()
            tf.file.seek(0)
            BRepTools.breptools_Read(shape, tf.name, BRep_Builder())

        return shape


class Field_Quantity_Color(Field):
    def _serialize(self, value, attr, obj, **kwargs):
        #assert isinstance(value, Quantity_Color)
        return [float(value.Red()), float(value.Green()), float(value.Blue())]

    def _deserialize(self, value, attr, data, **kwargs):
        red, green, blue = value
        return Quantity_Color(red, green, blue, Quantity_TOC_RGB)


class Field_TopLoc_Location(Field):
    def _serialize(self, value, attr, obj, **kwargs):
        #assert isinstance(value, TopLoc_Location)
        loc_trsf = value.Transformation()
        loc_matrix = [loc_trsf.Value(row + 1, col + 1) for row in range(3) for col in range(4)]
        return loc_matrix

    def _deserialize(self, value, attr, data, **kwargs):
        if len(value) != 12:
            raise ValidationError("The TopLoc matrix should have exactly 12 elements")

        loc_trsf = gp_Trsf()
        loc_trsf.SetValues(*value)
        return TopLoc_Location(loc_trsf)


TYPE_MAPPING = Schema.TYPE_MAPPING | {
    AIS_Trihedron:   Field_AIS_Trihedron,
    AIS_Line:        Field_AIS_Line,
    TopoDS_Shape:    Field_TopoDS_Shape,
    Quantity_Color:  Field_Quantity_Color,
    TopLoc_Location: Field_TopLoc_Location,
}


def typemap(t, required=True):
    if get_origin(t) == Union: # Assuming Union always is an Optional here...
        return typemap(get_args(t)[0], required=False)
    elif get_origin(t) == list:
        rt = typemap(get_args(t)[0])
        if rt is not None:
            return fields.List(rt, required=required, allow_none=bool(not required))
        else:
            return None
    elif get_origin(t) == dict:
        kt = typemap(get_args(t)[0])
        vt = typemap(get_args(t)[1])
        if (kt is not None) and (vt is not None):
            return fields.Dict(keys=kt, values=vt, required=required, allow_none=bool(not required))
        else:
            return None
    elif inspect.isclass(t) and issubclass(t, Serializable):
        return NestedSerializable(t, t.schema(), required=required, allow_none=bool(not required))
    elif isinstance(t, Serializable):
        return NestedSerializable(type(t), t.schema(), required=required, allow_none=bool(not required))
    else:
        rt = TYPE_MAPPING.get(t)
        if rt is not None:
            return rt(required=required, allow_none=bool(not required))
        else:
            return None


class Serializable:
    """Base functions for serializable dataclasses."""
    @classmethod
    def schema(obj, required=True):
        tyflds = {
            fld.name: typemap(fld.type)
            for fld in obj.__dataclass_fields__.values()
            if typemap(fld.type) is not None
        }
        return Schema.from_dict(tyflds, name=f"{obj.__name__}Schema")()

    def dump(self):
        return self.schema().dump(self)

    @classmethod
    def load(obj, blob):
        filter_blob = {k: v for k, v in blob.items() if v is not None}
        instance = obj(**obj.schema().load(filter_blob))
        instance.on_load()
        return instance

    def on_load(self):
        """Overridable function on things to do if this is loaded."""
        pass


class NestedSerializable(Nested):
    def __init__(self, cls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__cls = cls

    def _deserialize(self, value, attr, data, **kwargs):
        blob = super()._deserialize(value, attr, data, **kwargs)
        return self.__cls(**blob)

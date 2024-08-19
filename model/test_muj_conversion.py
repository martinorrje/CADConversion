import math
import unittest

from .muj_conversion import MujConverter

from OCC.Core.gp import gp_Pnt, gp_Vec, gp_Quaternion, gp_Trsf


class TestMujConverter(unittest.TestCase):

    def assertListAlmostEqual(self, list1, list2):
        self.assertEqual(len(list1), len(list2))
        for a, b in zip(list1, list2):
            self.assertAlmostEqual(a, b)

    def test_rel_trf_translation(self):
        trf1 = gp_Trsf()
        trf1.SetTranslation(gp_Vec(gp_Pnt(0, 0, 0), gp_Pnt(1, 3, 5)))
        trf2 = gp_Trsf()
        trf2.SetTranslation(gp_Vec(gp_Pnt(0, 0, 0), gp_Pnt(4, 5, 6)))
        trf12 = MujConverter.rel_trf(trf1, trf2)
        self.assertEqual(MujConverter.trf_to_pos(trf12), [3, 2, 1])

    def test_rel_trf_rotation(self):
        trf1 = gp_Trsf()
        trf1.SetRotation(gp_Quaternion(gp_Vec(1, 0, 0), math.pi / 4))
        trf2 = gp_Trsf()
        trf2.SetRotation(gp_Quaternion(gp_Vec(-1, 0, 0), math.pi / 4))
        trf12 = MujConverter.rel_trf(trf1, trf2)
        self.assertListAlmostEqual(
            MujConverter.trf_to_axisangle(trf12), [-1, 0, 0, math.pi / 2]
        )


if __name__ == "__main__":
    unittest.main()

import copy
import unittest

from qld_hydrographic_metadata import layer_contract


class MetadataTests(unittest.TestCase):
    def test_production_layers_must_match_name_geometry_query_and_oid(self):
        root = {
            "layers": [
                {"id": 62, "name": "Watercourse lines"},
                {"id": 63, "name": "Waterbody areas"},
            ]
        }

        def record(i, n, g):
            return {
                "id": i,
                "name": n,
                "geometryType": g,
                "capabilities": "Map,Query",
                "fields": [{"name": "objectid", "type": "esriFieldTypeOID"}],
            }

        line = record(62, "Watercourse lines", "esriGeometryPolyline")
        area = record(63, "Waterbody areas", "esriGeometryPolygon")
        self.assertTrue(layer_contract(root, line, area))
        for key, value in [
            ("name", "Watercourse_areas_Buffer"),
            ("geometryType", "esriGeometryPolyline"),
            ("capabilities", "Map"),
            ("fields", []),
        ]:
            bad = copy.deepcopy(area)
            bad[key] = value
            with self.assertRaises(ValueError):
                layer_contract(root, line, bad)
        root["layers"][1]["name"] = "UAT area"
        with self.assertRaises(ValueError):
            layer_contract(root, line, area)


if __name__ == "__main__":
    unittest.main()

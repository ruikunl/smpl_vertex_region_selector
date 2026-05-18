import json
import tempfile
import unittest
from pathlib import Path

from smpl_vertex_region_selector.region_io import (
    empty_region_map,
    load_region_file,
    normalize_region_map,
    validate_region_map,
    write_region_csv,
    write_region_map,
)
from smpl_vertex_region_selector.schema import VERTEX_COUNT


class RegionIOTest(unittest.TestCase):
    def test_normalize_region_map_sorts_and_deduplicates(self):
        payload = empty_region_map()
        payload["regions"]["abdomen_front"] = [5, 2, 5, 1]
        normalized = normalize_region_map(payload)
        self.assertEqual(normalized["regions"]["abdomen_front"], [1, 2, 5])

    def test_normalize_rejects_out_of_range_vertex_id(self):
        payload = empty_region_map()
        payload["regions"]["abdomen_front"] = [VERTEX_COUNT]
        with self.assertRaises(ValueError):
            normalize_region_map(payload)

    def test_validate_reports_duplicate_warning_for_raw_payload(self):
        payload = empty_region_map()
        payload["regions"]["abdomen_front"] = [7, 7]
        issues = validate_region_map(payload)
        self.assertTrue(any(issue.level == "warning" for issue in issues))

    def test_json_and_csv_round_trip(self):
        payload = empty_region_map(status="confirmed")
        payload["regions"]["lower_back"] = [10, 11]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_path = root / "region_map.json"
            csv_path = root / "region_map.csv"
            write_region_map(json_path, payload)
            write_region_csv(csv_path, payload)
            from_json = load_region_file(json_path)
            from_csv = load_region_file(csv_path)
            self.assertEqual(from_json["regions"]["lower_back"], [10, 11])
            self.assertEqual(from_csv["regions"]["lower_back"], [10, 11])
            self.assertEqual(json.loads(json_path.read_text())["mesh_name"], "smpl_27554")


if __name__ == "__main__":
    unittest.main()

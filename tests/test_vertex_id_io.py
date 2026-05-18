import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from smpl_vertex_region_selector.selection.vertex_id_io import (
    ids_from_pixel_points,
    load_cse_vertex_map,
    load_mask_or_points,
    load_vertex_ids,
    parse_vertex_id_text,
)


class VertexIdIoTest(unittest.TestCase):
    def test_parse_vertex_id_text_supports_ranges(self):
        self.assertEqual(parse_vertex_id_text("12, 55, 100-103 55"), [12, 55, 100, 101, 102, 103])

    def test_load_vertex_ids_from_txt_csv_and_region_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            txt = root / "ids.txt"
            txt.write_text("1\n3, 5-6\n", encoding="utf-8")
            self.assertEqual(load_vertex_ids(txt), [1, 3, 5, 6])

            csv_path = root / "ids.csv"
            csv_path.write_text("region,vertex_id\nabdomen,7\nabdomen,9\n", encoding="utf-8")
            self.assertEqual(load_vertex_ids(csv_path), [7, 9])

            json_path = root / "region_map.json"
            json_path.write_text(
                json.dumps(
                    {
                        "mesh_name": "smpl_27554",
                        "vertex_count": 27554,
                        "regions": {"abdomen_front": [11, 12], "lower_back": [20]},
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(load_vertex_ids(json_path), [11, 12, 20])

    def test_load_cse_vertex_map_supports_expected_npz_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            array = np.asarray([[-1, 1], [2, 3]], dtype=np.int32)
            vertex_id_npz = root / "vertex_id.npz"
            np.savez(vertex_id_npz, vertex_id=array)
            loaded = load_cse_vertex_map(vertex_id_npz)
            self.assertEqual(loaded.key, "vertex_id")
            self.assertEqual(loaded.valid_pixel_count, 3)
            self.assertEqual(loaded.unique_vertex_count, 3)

            vertex_map_npz = root / "vertex_map.npz"
            np.savez(vertex_map_npz, vertex_map=array)
            self.assertEqual(load_cse_vertex_map(vertex_map_npz).key, "vertex_map")

    def test_mask_and_points_map_to_cse_vertex_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vertex_map = np.asarray([[-1, 1, 1], [2, 3, -1], [2, 4, 5]], dtype=np.int32)
            self.assertEqual(ids_from_pixel_points(vertex_map, [(1, 0), (0, 1), (2, 0)]), [1, 2])

            mask_path = root / "mask.png"
            mask = np.zeros((3, 3), dtype=np.uint8)
            mask[0, 1] = 255
            mask[2, 2] = 255
            Image.fromarray(mask).save(mask_path)
            self.assertEqual(load_mask_or_points(mask_path, vertex_map), [1, 5])

            points_path = root / "points.csv"
            points_path.write_text("x,y\n1,1\n2,2\n", encoding="utf-8")
            self.assertEqual(load_mask_or_points(points_path, vertex_map), [3, 5])


if __name__ == "__main__":
    unittest.main()

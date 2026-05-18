import csv
import tempfile
import unittest
from pathlib import Path

from smpl_vertex_region_selector.geometry.vertex_table import load_vertex_table


class VertexTableTest(unittest.TestCase):
    def write_csv(self, path: Path, rows):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["vertex_id", "atlas_u_norm", "atlas_v_norm", "mds0_norm", "mds1_norm", "mds2_norm"],
            )
            writer.writeheader()
            writer.writerows(rows)

    def test_load_vertex_table_uses_mds_by_default_and_sorts_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vertices.csv"
            self.write_csv(
                path,
                [
                    {"vertex_id": 2, "atlas_u_norm": 0.2, "atlas_v_norm": 0.2, "mds0_norm": 1, "mds1_norm": 0, "mds2_norm": 0},
                    {"vertex_id": 0, "atlas_u_norm": 0.1, "atlas_v_norm": 0.1, "mds0_norm": 0, "mds1_norm": 0, "mds2_norm": 0},
                    {"vertex_id": 1, "atlas_u_norm": 0.3, "atlas_v_norm": 0.3, "mds0_norm": 0.5, "mds1_norm": 1, "mds2_norm": 0.5},
                ],
            )
            table = load_vertex_table(path, strict=False)
            self.assertEqual(table.vertex_ids.tolist(), [0, 1, 2])
            self.assertEqual(table.coordinate_mode, "mds")
            self.assertEqual(table.points.shape, (3, 3))

    def test_requested_missing_mode_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vertices.csv"
            with path.open("w", encoding="utf-8") as handle:
                handle.write("vertex_id\n0\n")
            with self.assertRaises(ValueError):
                load_vertex_table(path, mode="mds", strict=False)


if __name__ == "__main__":
    unittest.main()

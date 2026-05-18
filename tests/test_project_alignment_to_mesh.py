import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

from smpl_vertex_region_selector.project_alignment_to_mesh import project_alignment_to_mesh
from smpl_vertex_region_selector.schema import VERTEX_COUNT


class ProjectAlignmentToMeshTest(unittest.TestCase):
    def test_projects_full_vertex_id_set_to_user_mesh(self):
        if importlib.util.find_spec("open3d") is None or importlib.util.find_spec("trimesh") is None:
            self.skipTest("open3d/trimesh unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vertex_id = np.arange(VERTEX_COUNT, dtype=np.int32)
            theta = np.linspace(0.0, np.pi * 2.0, VERTEX_COUNT, endpoint=False, dtype=np.float32)
            y = np.linspace(-1.0, 1.0, VERTEX_COUNT, dtype=np.float32)
            radius = np.sqrt(np.maximum(0.0, 1.0 - y * y))
            source_points = np.stack([0.3 * radius * np.cos(theta), y, 0.12 * radius * np.sin(theta)], axis=1).astype(np.float32)
            source = root / "source.npz"
            np.savez_compressed(source, vertex_id=vertex_id, surface_points=source_points)

            mesh = root / "target.obj"
            mesh.write_text(
                "\n".join(
                    [
                        "v -1 -1 -1",
                        "v 1 -1 -1",
                        "v 1 1 -1",
                        "v -1 1 -1",
                        "v -1 -1 1",
                        "v 1 -1 1",
                        "v 1 1 1",
                        "v -1 1 1",
                        "f 1 2 3",
                        "f 1 3 4",
                        "f 5 7 6",
                        "f 5 8 7",
                        "f 1 5 6",
                        "f 1 6 2",
                        "f 2 6 7",
                        "f 2 7 3",
                        "f 3 7 8",
                        "f 3 8 4",
                        "f 4 8 5",
                        "f 4 5 1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            out = root / "projected"
            report = project_alignment_to_mesh(source, str(mesh), out, raw_dir=root / "raw", image_size=64)

            self.assertEqual(report["status"], "demo_reference_smpl_id_projected")
            self.assertEqual(report["vertex_count"], VERTEX_COUNT)
            self.assertTrue((out / "surface_proxy.obj").exists())
            self.assertTrue((out / "smpl_27554_to_surface_map.npz").exists())
            mapping = np.load(out / "smpl_27554_to_surface_map.npz")
            self.assertEqual(mapping["vertex_id"].shape, (VERTEX_COUNT,))
            self.assertEqual(mapping["surface_points"].shape, (VERTEX_COUNT, 3))
            id_map = np.load(out / "tri_views" / "front.vertex_id_map.npz")["vertex_id_map"]
            valid = id_map[id_map >= 0]
            self.assertGreater(valid.size, 0)
            self.assertLess(int(valid.max()), VERTEX_COUNT)


if __name__ == "__main__":
    unittest.main()

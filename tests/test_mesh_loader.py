import tempfile
import unittest
from pathlib import Path

from smpl_vertex_region_selector.geometry.mesh_loader import ALIGNED_MESH, POINT_CLOUD_ONLY, VISUAL_REFERENCE, load_mesh_asset
from smpl_vertex_region_selector.schema import VERTEX_COUNT


class MeshLoaderTest(unittest.TestCase):
    def test_none_means_point_cloud_only(self):
        asset = load_mesh_asset(None)
        self.assertEqual(asset.status, POINT_CLOUD_ONLY)

    def test_small_obj_is_visual_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiny.obj"
            path.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
            asset = load_mesh_asset(path)
            self.assertEqual(asset.status, VISUAL_REFERENCE)
            self.assertEqual(asset.vertex_count, 3)

    def test_27554_vertex_obj_is_aligned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aligned.obj"
            with path.open("w", encoding="utf-8") as handle:
                for idx in range(VERTEX_COUNT):
                    handle.write(f"v {idx} 0 0\n")
            asset = load_mesh_asset(path)
            self.assertEqual(asset.status, ALIGNED_MESH)
            self.assertEqual(asset.vertex_count, VERTEX_COUNT)


if __name__ == "__main__":
    unittest.main()

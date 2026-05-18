import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from smpl_vertex_region_selector.alignment.assets import load_alignment_assets
from smpl_vertex_region_selector.schema import VERTEX_COUNT

ROOT = Path(__file__).resolve().parents[1]


class DemoAssetsTest(unittest.TestCase):
    def test_public_demo_assets_are_bundled_and_alignment_compatible(self):
        public = ROOT / "assets" / "demo_reference" / "public"
        required = [
            "alignment_report.json",
            "surface_proxy.obj",
            "smpl_27554_surface_points.obj",
            "smpl_27554_to_surface_map.npz",
            "tri_view_manifest.json",
            "vertex_template_points.csv",
        ]
        for name in required:
            self.assertTrue((public / name).exists(), f"missing public demo asset {name}")

        report = json.loads((public / "alignment_report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "makehuman_cc0_smpl_projected_demo")
        self.assertEqual(report.get("asset_class"), "makehuman_cc0_projected_demo")
        self.assertIn("MakeHuman", report.get("license", ""))
        self.assertIn("no SMPL model", report.get("license", ""))
        self.assertIn("DensePose raw asset", report.get("license", ""))
        self.assertIn("private dataset image", report.get("license", ""))
        self.assertEqual(report.get("target_mesh"), "MakeHuman female_generic proxy mesh (CC0-1.0)")

        vertex_csv = public / "vertex_template_points.csv"
        with vertex_csv.open("r", encoding="utf-8") as handle:
            header = handle.readline().strip().split(",")
            self.assertIn("vertex_id", header)
            ids = [int(line.split(",", 1)[0]) for line in handle if line.strip()]
        self.assertEqual(len(ids), VERTEX_COUNT)
        self.assertEqual(ids[0], 0)
        self.assertEqual(ids[-1], VERTEX_COUNT - 1)
        self.assertEqual(len(set(ids)), VERTEX_COUNT)

        assets = load_alignment_assets(public)
        self.assertEqual(assets.status, "makehuman_cc0_smpl_projected_demo")
        self.assertEqual(assets.vertex_ids.shape, (VERTEX_COUNT,))
        self.assertEqual(assets.surface_points.shape, (VERTEX_COUNT, 3))
        self.assertGreater(sum(1 for line in (public / "surface_proxy.obj").read_text(encoding="utf-8").splitlines() if line.startswith("v ")), 10000)
        for view in ("front", "back", "left", "right"):
            self.assertIn(view, assets.tri_views)
            tri = assets.tri_views[view]
            self.assertTrue(tri.image_path.exists())
            self.assertTrue(tri.vertex_id_map_path.exists())
            valid = tri.vertex_id_map[tri.vertex_id_map >= 0]
            self.assertGreater(valid.size, 0)
            self.assertGreaterEqual(int(valid.min()), 0)
            self.assertLess(int(valid.max()), VERTEX_COUNT)

    def test_public_demo_assets_load_outside_repo_cwd(self):
        public = ROOT / "assets" / "demo_reference" / "public"
        if not public.exists():
            self.skipTest("public demo assets are not present")
        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                assets = load_alignment_assets(public)
                self.assertEqual(assets.status, "makehuman_cc0_smpl_projected_demo")
                self.assertIn("front", assets.tri_views)
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()

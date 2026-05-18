import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from smpl_vertex_region_selector.selection.vertex_id_io import load_cse_vertex_map


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CSEExamplesTest(unittest.TestCase):
    def test_bundled_examples_are_complete_and_loadable(self):
        manifest_path = ROOT / "examples" / "cse" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        images = manifest.get("images", [])

        self.assertEqual(manifest.get("sample_set"), "examples")
        self.assertEqual(len(images), 6)
        self.assertEqual(manifest.get("image_root"), "smpl_vertex_region_selector/examples/images")

        for item in images:
            image_path = ROOT.parent / item["path"]
            stem = Path(item["file_name"]).stem
            vertex_map_path = ROOT / "examples" / "cse" / "vertex_maps" / f"{stem}.vertex_map.npz"
            overlay_path = ROOT / "examples" / "cse" / "overlays" / f"{stem}.cse_vertex_overlay.jpg"
            mask_path = ROOT / "examples" / "cse" / "masks" / f"{stem}.foreground.png"

            self.assertTrue(image_path.exists(), f"missing example image {image_path}")
            self.assertTrue(vertex_map_path.exists(), f"missing vertex map {vertex_map_path}")
            self.assertTrue(overlay_path.exists(), f"missing CSE overlay {overlay_path}")
            self.assertTrue(mask_path.exists(), f"missing CSE mask {mask_path}")

            cse_map = load_cse_vertex_map(vertex_map_path)
            self.assertEqual(cse_map.key, "vertex_id")
            self.assertEqual(cse_map.shape, (512, 512))
            self.assertGreater(cse_map.valid_pixel_count, 0)
            self.assertGreater(cse_map.unique_vertex_count, 0)

        self.assertTrue((ROOT / "examples" / "cse" / "cse_contact_sheet.jpg").exists())
        self.assertTrue((ROOT / "examples" / "cse" / "example_cse_summary.json").exists())

    def test_manifest_generation_is_surface_pipeline_compatible(self):
        manifest_tool = load_script("make_examples_manifest.py")
        with tempfile.TemporaryDirectory() as tmp:
            workspace_root = Path(tmp) / "workspace"
            image_dir = workspace_root / "smpl_vertex_region_selector" / "examples" / "images"
            output = workspace_root / "smpl_vertex_region_selector" / "examples" / "cse" / "manifest.json"
            image_dir.mkdir(parents=True)
            Image.new("RGB", (8, 6), (120, 140, 160)).save(image_dir / "case_001_full.png")

            manifest = manifest_tool.write_manifest(
                image_dir=image_dir,
                output=output,
                workspace_root=workspace_root,
            )

            self.assertTrue(output.exists())
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), manifest)
            self.assertEqual(manifest["sample_set"], "examples")
            self.assertEqual(manifest["image_root"], "smpl_vertex_region_selector/examples/images")
            self.assertEqual(
                manifest["images"],
                [
                    {
                        "file_name": "case_001_full.png",
                        "path": "smpl_vertex_region_selector/examples/images/case_001_full.png",
                        "category": "example_full_body",
                    }
                ],
            )

    def test_collect_cse_examples_copies_lightweight_outputs(self):
        collect_tool = load_script("collect_cse_examples.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run"
            (run_dir / "cse" / "vertex_maps").mkdir(parents=True)
            (run_dir / "cse" / "overlays").mkdir(parents=True)
            (run_dir / "cse" / "masks").mkdir(parents=True)
            vertex_map = np.full((6, 8), -1, dtype=np.int32)
            vertex_map[1:4, 2:5] = 101
            np.savez_compressed(run_dir / "cse" / "vertex_maps" / "case_001.vertex_map.npz", vertex_id=vertex_map)
            Image.new("RGB", (8, 6), (120, 140, 160)).save(run_dir / "cse" / "overlays" / "case_001.cse_vertex_overlay.jpg")
            Image.new("L", (8, 6), 255).save(run_dir / "cse" / "masks" / "case_001.foreground.png")
            (run_dir / "summary.json").write_text('{"count": 1}\n', encoding="utf-8")

            out_dir = root / "examples" / "cse"
            summary = collect_tool.collect(run_dir=run_dir, output_dir=out_dir, force=True)

            self.assertEqual(len(summary["vertex_maps"]), 1)
            self.assertEqual(summary["source_run_name"], "run")
            self.assertTrue((out_dir / "vertex_maps" / "case_001.vertex_map.npz").exists())
            self.assertTrue((out_dir / "overlays" / "case_001.cse_vertex_overlay.jpg").exists())
            self.assertTrue((out_dir / "masks" / "case_001.foreground.png").exists())
            self.assertTrue((out_dir / "summary.json").exists())
            self.assertFalse((out_dir / "manifest.json").exists())
            loaded = load_cse_vertex_map(out_dir / "vertex_maps" / "case_001.vertex_map.npz")
            self.assertEqual(loaded.valid_pixel_count, 9)


if __name__ == "__main__":
    unittest.main()

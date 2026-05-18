import csv
import pickle
import tempfile
import unittest
from pathlib import Path

import numpy as np

from smpl_vertex_region_selector.alignment.builder import build_alignment_assets
from smpl_vertex_region_selector.schema import VERTEX_COUNT


class AlignmentBuilderTest(unittest.TestCase):
    def write_vertex_csv(self, path: Path):
        with path.open("w", encoding="utf-8", newline="") as handle:
            fieldnames = ["vertex_id", "atlas_u_norm", "atlas_v_norm", "mds0_norm", "mds1_norm", "mds2_norm"]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for idx in range(VERTEX_COUNT):
                u = ((idx % 100) / 99.0) * 0.24
                v = 0.84 + (((idx // 100) % 100) / 99.0) * 0.15
                writer.writerow(
                    {
                        "vertex_id": idx,
                        "atlas_u_norm": u,
                        "atlas_v_norm": v,
                        "mds0_norm": u,
                        "mds1_norm": v,
                        "mds2_norm": 0.5,
                    }
                )

    def write_fake_assets(self, root: Path):
        try:
            from scipy.io import savemat
        except Exception as exc:
            self.skipTest(f"scipy unavailable: {exc}")
        smpl = root / "assets" / "raw" / "smpl"
        smpl.mkdir(parents=True)
        smpl_path = smpl / "fake_smpl.pkl"
        with smpl_path.open("wb") as handle:
            pickle.dump(
                {
                    "v_template": np.asarray(
                        [[-1, 0, 0], [1, 0, 0], [1, 2, 0], [-1, 2, 0]], dtype=np.float32
                    ),
                    "f": np.asarray([[0, 1, 2], [0, 2, 3]], dtype=np.int32),
                },
                handle,
            )
        uv_path = root / "assets" / "raw" / "densepose" / "UV_Processed.mat"
        uv_path.parent.mkdir(parents=True)
        savemat(
            uv_path,
            {
                "All_vertices": np.asarray([[1], [2], [3], [4]], dtype=np.int32),
                "All_Faces": np.asarray([[1, 2, 3], [1, 3, 4]], dtype=np.int32),
                "All_U_norm": np.asarray([[0], [1], [1], [0]], dtype=np.float32),
                "All_V_norm": np.asarray([[0], [0], [1], [1]], dtype=np.float32),
                "All_FaceIndices": np.asarray([[1], [1]], dtype=np.int32),
            },
        )
        return smpl_path, uv_path

    def test_missing_smpl_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vertex_csv = root / "vertex_template_points.csv"
            self.write_vertex_csv(vertex_csv)
            report = build_alignment_assets(
                vertex_csv=vertex_csv,
                output_dir=root / "out",
                raw_root=root / "assets" / "raw",
                download_densepose_uv=False,
                download_smpl_subdiv=False,
                image_size=32,
            )
            self.assertEqual(report["status"], "missing_smpl")
            self.assertTrue((root / "out" / "alignment_report.json").exists())

    def test_fake_assets_build_surface_proxy_and_tri_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vertex_csv = root / "vertex_template_points.csv"
            self.write_vertex_csv(vertex_csv)
            smpl_path, uv_path = self.write_fake_assets(root)
            out = root / "out"
            report = build_alignment_assets(
                vertex_csv=vertex_csv,
                output_dir=out,
                raw_root=root / "assets" / "raw",
                smpl_model=smpl_path,
                densepose_uv=uv_path,
                download_densepose_uv=False,
                download_smpl_subdiv=False,
                image_size=64,
            )
            self.assertEqual(report["status"], "surface_proxy_aligned")
            mapping = np.load(out / "smpl_27554_to_surface_map.npz")
            self.assertEqual(mapping["surface_points"].shape, (VERTEX_COUNT, 3))
            self.assertTrue((out / "surface_proxy.obj").exists())
            self.assertTrue((out / "tri_views" / "front.vertex_id_map.npz").exists())

    def test_smpl_subdiv_transform_builds_complete_surface_without_smpl_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                from scipy.io import savemat
            except Exception as exc:
                self.skipTest(f"scipy unavailable: {exc}")
            root = Path(tmp)
            vertex_csv = root / "vertex_template_points.csv"
            self.write_vertex_csv(vertex_csv)
            raw = root / "assets" / "raw" / "densepose"
            raw.mkdir(parents=True)
            n = VERTEX_COUNT
            vertices = np.zeros((3, n), dtype=np.float32)
            vertices[0] = np.linspace(-1, 1, n)
            vertices[1] = np.linspace(-0.5, 0.5, n)
            vertices[2] = np.linspace(-0.1, 0.1, n)
            faces = np.asarray([[1, 2, 3], [3, 4, 5], [5, 6, 7]], dtype=np.uint16).T
            savemat(
                raw / "SMPL_subdiv.mat",
                {
                    "vertex": vertices,
                    "faces": faces,
                    "Part_ID_subdiv": np.ones((n, 1), dtype=np.uint8),
                    "U_subdiv": np.linspace(0, 1, n, dtype=np.float32).reshape(-1, 1),
                    "V_subdiv": np.linspace(1, 0, n, dtype=np.float32).reshape(-1, 1),
                },
            )
            savemat(raw / "SMPL_SUBDIV_TRANSFORM.mat", {"index": np.arange(1, n + 1, dtype=np.uint16).reshape(-1, 1)})
            out = root / "out"
            report = build_alignment_assets(
                vertex_csv=vertex_csv,
                output_dir=out,
                raw_root=root / "assets" / "raw",
                download_densepose_uv=False,
                download_smpl_subdiv=False,
                image_size=64,
            )
            self.assertEqual(report["alignment_source"], "densepose_smpl_subdiv_transform")
            self.assertEqual(report["fallback_ratio"], 0.0)
            mapping = np.load(out / "smpl_27554_to_surface_map.npz")
            self.assertEqual(mapping["surface_points"].shape, (VERTEX_COUNT, 3))
            self.assertTrue((out / "surface_proxy.obj").exists())


if __name__ == "__main__":
    unittest.main()

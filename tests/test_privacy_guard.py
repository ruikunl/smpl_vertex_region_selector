import subprocess
import unittest
from pathlib import Path


class PrivacyGuardTest(unittest.TestCase):
    def test_open_source_files_do_not_reference_private_dataset_paths(self):
        root = Path(__file__).resolve().parents[1]
        forbidden = [
            "local_result_backup" + "_razer_maso",
            "surface_body_preannotation" + "_pilot",
            "../data" + "/images",
            "/data" + "/images",
            "~/" + "Downloads",
            "basicmodel_" + "neutral_lbs_10_207_0_v1.1.0.pkl",
            "basicmodel_" + "m_lbs_10_207_0_v1.1.0.pkl",
            "basicmodel_" + "f_lbs_10_207_0_v1.1.0.pkl",
            "Blen" + "der",
            "blen" + "der_region_picker",
            "import " + "bpy",
        ]
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.name == "test_privacy_guard.py":
                continue
            if any(part in {".venv", "outputs", "raw", "processed", "public_examples", "generated", "__pycache__"} for part in path.parts):
                continue
            if path.suffix.lower() not in {".py", ".md", ".toml", ".txt", ".json", ".sh"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in forbidden:
                self.assertNotIn(token, text, f"{token!r} leaked in {path}")

    def test_gitignore_asset_policy(self):
        root = Path(__file__).resolve().parents[1]

        def ignored(path: str) -> bool:
            result = subprocess.run(
                ["git", "check-ignore", "-q", path],
                cwd=root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode == 128:
                self.skipTest("git check-ignore is unavailable outside a git worktree")
            return result.returncode == 0

        for path in [
            "assets/raw/smpl/smpl_neutral.pkl",
            "assets/processed/alignment/surface_proxy.obj",
            "assets/demo_reference/generated/surface_proxy.obj",
            "assets/raw/body.glb",
            "assets/raw/body.gltf",
        ]:
            self.assertTrue(ignored(path), f"{path} should stay ignored")

        for path in [
            "assets/demo_reference/public/surface_proxy.obj",
            "assets/demo_reference/public/smpl_27554_to_surface_map.npz",
            "assets/demo_reference/public/tri_views/front.png",
            "assets/demo_reference/public/tri_views/front.vertex_id_map.npz",
        ]:
            self.assertFalse(ignored(path), f"{path} should be allowed")


if __name__ == "__main__":
    unittest.main()

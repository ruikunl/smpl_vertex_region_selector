import tempfile
import unittest
import zipfile
from pathlib import Path

from smpl_vertex_region_selector.install_local_assets import install_smpl_models, install_smpl_uv, write_license_report


class InstallLocalAssetsTest(unittest.TestCase):
    def make_zip(self, path: Path, files: dict[str, bytes]) -> None:
        with zipfile.ZipFile(path, "w") as archive:
            for name, payload in files.items():
                archive.writestr(name, payload)

    def test_extracts_smpl_and_uv_to_ignored_raw_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            smpl_zip = root / "smpl.zip"
            uv_zip = root / "uv.zip"
            self.make_zip(
                smpl_zip,
                {
                    "pkg/smpl/models/demo_neutral_model.pkl": b"neutral",
                    "pkg/smpl/models/demo_m_model.pkl": b"male",
                    "pkg/smpl/models/demo_f_model.pkl": b"female",
                },
            )
            self.make_zip(
                uv_zip,
                {
                    "smpl_uv.obj": b"v 0 0 0\n",
                    "smpl_uv_20200910.png": b"png",
                },
            )
            raw_root = root / "assets" / "raw"
            installed = []
            installed.extend(install_smpl_models(smpl_zip, raw_root, ["neutral", "male", "female"]))
            installed.extend(install_smpl_uv(uv_zip, raw_root))
            report = write_license_report(raw_root, installed, {"smpl_zip": str(smpl_zip), "uv_zip": str(uv_zip)})

            self.assertTrue((raw_root / "smpl" / "smpl_neutral.pkl").exists())
            self.assertTrue((raw_root / "smpl" / "smpl_male.pkl").exists())
            self.assertTrue((raw_root / "smpl" / "smpl_female.pkl").exists())
            self.assertTrue((raw_root / "smpl_uv" / "smpl_uv.obj").exists())
            self.assertTrue((raw_root / "smpl_uv" / "smpl_uv_20200910.png").exists())
            self.assertTrue(report.exists())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import argparse
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


LOCAL_LICENSE_WARNING = (
    "SMPL assets are installed for local validation only. Do not commit or "
    "redistribute official SMPL model files, derived alignment outputs, or "
    "other licensed assets unless you have checked the upstream license."
)


@dataclass(frozen=True)
class InstalledAsset:
    kind: str
    source_member: str
    output_path: Path
    bytes_written: int


def _default_downloads_path(filename: str) -> Path:
    return Path.home() / "Downloads" / filename


def _infer_gender(member_name: str) -> str | None:
    lowered = member_name.lower()
    if not lowered.endswith(".pkl") or "/smpl/models/" not in lowered:
        return None
    stem = Path(lowered).stem
    if "neutral" in stem:
        return "neutral"
    if "_f_" in stem or "female" in stem:
        return "female"
    if "_m_" in stem or "male" in stem:
        return "male"
    return None


def _select_smpl_members(zip_path: Path, genders: Iterable[str]) -> dict[str, zipfile.ZipInfo]:
    requested = set(genders)
    selected: dict[str, zipfile.ZipInfo] = {}
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            gender = _infer_gender(info.filename)
            if gender and gender in requested and gender not in selected:
                selected[gender] = info
    missing = sorted(requested - set(selected))
    if missing:
        raise FileNotFoundError(f"Could not find SMPL model(s) for: {', '.join(missing)} in {zip_path}")
    return selected


def _copy_member(
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    output_path: Path,
    overwrite: bool,
    kind: str,
) -> InstalledAsset:
    if output_path.exists() and not overwrite:
        return InstalledAsset(kind, member.filename, output_path, output_path.stat().st_size)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(member) as src, output_path.open("wb") as dst:
        written = 0
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)
            written += len(chunk)
    return InstalledAsset(kind, member.filename, output_path, written)


def install_smpl_models(zip_path: Path, raw_root: Path, genders: Iterable[str], overwrite: bool = False) -> list[InstalledAsset]:
    if not zip_path.exists():
        raise FileNotFoundError(f"SMPL zip not found: {zip_path}")
    selected = _select_smpl_members(zip_path, genders)
    installed: list[InstalledAsset] = []
    with zipfile.ZipFile(zip_path) as archive:
        for gender, member in sorted(selected.items()):
            output = raw_root / "smpl" / f"smpl_{gender}.pkl"
            installed.append(_copy_member(archive, member, output, overwrite, f"smpl_{gender}"))
    return installed


def install_smpl_uv(zip_path: Path, raw_root: Path, overwrite: bool = False) -> list[InstalledAsset]:
    if not zip_path.exists():
        raise FileNotFoundError(f"SMPL UV zip not found: {zip_path}")
    wanted = {"smpl_uv.obj", "smpl_uv_20200910.png"}
    installed: list[InstalledAsset] = []
    with zipfile.ZipFile(zip_path) as archive:
        members = {Path(info.filename).name: info for info in archive.infolist() if not info.is_dir()}
        missing = sorted(wanted - set(members))
        if missing:
            raise FileNotFoundError(f"Could not find {', '.join(missing)} in {zip_path}")
        for name in sorted(wanted):
            output = raw_root / "smpl_uv" / name
            installed.append(_copy_member(archive, members[name], output, overwrite, "smpl_uv"))
    return installed


def write_license_report(raw_root: Path, installed: list[InstalledAsset], sources: dict[str, str]) -> Path:
    report_path = raw_root / "asset_license_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "local_validation_assets_installed",
        "warning": LOCAL_LICENSE_WARNING,
        "sources": sources,
        "installed": [
            {
                "kind": asset.kind,
                "source_member": asset.source_member,
                "output_path": str(asset.output_path),
                "bytes_written": asset.bytes_written,
            }
            for asset in installed
        ],
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install local-only SMPL validation assets into ignored assets/raw directories.")
    parser.add_argument("--smpl-zip", type=Path, default=_default_downloads_path("SMPL_python_v.1.1.0.zip"))
    parser.add_argument("--uv-zip", type=Path, default=_default_downloads_path("smpl_uv_20200910.zip"))
    parser.add_argument("--raw-root", type=Path, default=Path("assets/raw"))
    parser.add_argument(
        "--gender",
        choices=["all", "neutral", "male", "female"],
        default="all",
        help="Which SMPL model(s) to extract. Default extracts neutral, male, and female.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing ignored local files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    genders = ["female", "male", "neutral"] if args.gender == "all" else [args.gender]
    installed: list[InstalledAsset] = []
    installed.extend(install_smpl_models(args.smpl_zip.expanduser(), args.raw_root, genders, args.overwrite))
    installed.extend(install_smpl_uv(args.uv_zip.expanduser(), args.raw_root, args.overwrite))
    report_path = write_license_report(
        args.raw_root,
        installed,
        {"smpl_zip": str(args.smpl_zip.expanduser()), "uv_zip": str(args.uv_zip.expanduser())},
    )
    print(LOCAL_LICENSE_WARNING)
    for asset in installed:
        print(f"installed: {asset.output_path} ({asset.bytes_written} bytes)")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

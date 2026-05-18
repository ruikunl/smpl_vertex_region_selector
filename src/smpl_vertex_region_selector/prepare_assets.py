from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Optional

from .schema import VERTEX_COUNT


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def discover_vertex_csv(start: Path) -> Optional[Path]:
    candidates = [
        start / "assets" / "processed" / "vertex_template_points.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def inspect_vertex_csv(path: Path, allow_partial: bool = False) -> dict[str, object]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "vertex_id" not in reader.fieldnames:
            raise ValueError(f"{path} must contain a vertex_id column")
        ids: list[int] = []
        for row in reader:
            ids.append(int(row["vertex_id"]))
    unique = sorted(set(ids))
    if not allow_partial:
        if len(unique) != VERTEX_COUNT:
            raise ValueError(f"{path} has {len(unique)} unique vertex ids, expected {VERTEX_COUNT}")
        if unique[0] != 0 or unique[-1] != VERTEX_COUNT - 1:
            raise ValueError(f"{path} vertex ids must cover 0..{VERTEX_COUNT - 1}")
    return {
        "path": str(path),
        "rows": len(ids),
        "unique_vertex_ids": len(unique),
        "min_vertex_id": unique[0] if unique else None,
        "max_vertex_id": unique[-1] if unique else None,
        "columns": reader.fieldnames,
    }


def write_npz(csv_path: Path, npz_path: Path) -> None:
    import numpy as np

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    vertex_ids = np.asarray([int(row["vertex_id"]) for row in rows], dtype=np.int32)
    arrays: dict[str, object] = {"vertex_id": vertex_ids}
    for key in rows[0].keys():
        if key == "vertex_id":
            continue
        try:
            arrays[key] = np.asarray([float(row[key]) for row in rows], dtype=np.float32)
        except ValueError:
            continue
    npz_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(npz_path, **arrays)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare local smpl_27554 selector assets.")
    parser.add_argument("--source-csv", type=Path, help="Path to a full vertex_template_points.csv file.")
    parser.add_argument("--project-root", type=Path, default=default_project_root())
    parser.add_argument("--allow-partial", action="store_true", help="Allow a partial CSV for demos/tests.")
    parser.add_argument("--no-npz", action="store_true", help="Skip compressed NPZ export.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = args.project_root.resolve()
    source = args.source_csv.resolve() if args.source_csv else discover_vertex_csv(project_root)
    if not source:
        raise SystemExit(
            "No vertex_template_points.csv found. Pass --source-csv or place one under assets/processed/."
        )
    summary = inspect_vertex_csv(source, allow_partial=args.allow_partial)
    processed = project_root / "assets" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    target = processed / "vertex_template_points.csv"
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)
    summary["copied_to"] = str(target)
    if not args.no_npz:
        npz_path = processed / "vertex_template_points.npz"
        write_npz(target, npz_path)
        summary["npz"] = str(npz_path)
    summary_path = processed / "asset_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

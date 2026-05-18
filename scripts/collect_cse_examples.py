#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def copy_matching(run_dir: Path, output_dir: Path, subdir: str, pattern: str, force: bool) -> list[str]:
    source_dir = run_dir / "cse" / subdir
    target_dir = output_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    if not source_dir.exists():
        return copied
    for source in sorted(source_dir.glob(pattern)):
        target = target_dir / source.name
        if target.exists() and not force:
            copied.append(target.name)
            continue
        shutil.copy2(source, target)
        copied.append(target.name)
    return copied


def validate_vertex_maps(output_dir: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted((output_dir / "vertex_maps").glob("*.vertex_map.npz")):
        with np.load(path) as payload:
            key = "vertex_id" if "vertex_id" in payload.files else "vertex_map" if "vertex_map" in payload.files else payload.files[0]
            arr = np.asarray(payload[key])
        if arr.ndim != 2:
            raise ValueError(f"{path} must contain a 2D vertex map, got {arr.shape}")
        valid = arr[arr >= 0]
        if valid.size and int(valid.max()) >= 27554:
            raise ValueError(f"{path} contains vertex id {int(valid.max())}, expected < 27554")
        records.append(
            {
                "file": path.name,
                "key": key,
                "shape": list(arr.shape),
                "valid_pixels": int(valid.size),
                "unique_vertices": int(np.unique(valid).size) if valid.size else 0,
            }
        )
    return records


def sanitize_json_paths(value, run_dir: Path):
    if isinstance(value, str):
        return value.replace(run_dir.as_posix(), f"source_run/{run_dir.name}")
    if isinstance(value, list):
        return [sanitize_json_paths(item, run_dir) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_json_paths(item, run_dir) for key, item in value.items()}
    return value


def copy_json_sanitized(source: Path, target: Path, run_dir: Path) -> None:
    with source.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    payload = sanitize_json_paths(payload, run_dir)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def collect(run_dir: Path, output_dir: Path, force: bool = False) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    copied = {
        "vertex_maps": copy_matching(run_dir, output_dir, "vertex_maps", "*.vertex_map.npz", force),
        "overlays": copy_matching(run_dir, output_dir, "overlays", "*.cse_vertex_overlay.jpg", force),
        "masks": copy_matching(run_dir, output_dir, "masks", "*.foreground.png", force),
    }
    extra_files = {
        "summary.json": "summary.json",
        "manifest.json": "run_manifest.json",
        "cse_contact_sheet.jpg": "cse_contact_sheet.jpg",
    }
    for source_name, target_name in extra_files.items():
        source = run_dir / source_name
        if source.exists():
            target = output_dir / target_name
            if force or not target.exists():
                if source.suffix == ".json":
                    copy_json_sanitized(source, target, run_dir)
                else:
                    shutil.copy2(source, target)
    records = validate_vertex_maps(output_dir)
    summary = {
        "source_run_name": run_dir.name,
        "output_dir": output_dir.as_posix(),
        "copied": copied,
        "vertex_maps": records,
        "raw_cse_pt_copied": False,
    }
    with (output_dir / "example_cse_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect lightweight CSE example outputs from a surface_body_preannotation run.")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=repo_root() / "examples" / "cse")
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = collect(args.run_dir, args.output_dir, force=args.force)
    print(
        f"Collected {len(summary['vertex_maps'])} vertex map(s), "
        f"{len(summary['copied']['overlays'])} overlay(s), "
        f"{len(summary['copied']['masks'])} mask(s) into {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

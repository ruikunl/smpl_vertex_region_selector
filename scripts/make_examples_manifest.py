#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_IMAGE_DIR = Path("examples/images")
DEFAULT_OUTPUT = Path("examples/cse/manifest.json")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def workspace_relative(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def example_category(path: Path) -> str:
    name = path.stem.lower()
    if "half" in name:
        return "example_half_body"
    if "full" in name:
        return "example_full_body"
    return "example"


def build_manifest(image_dir: Path, workspace_root: Path) -> dict:
    image_dir = image_dir.resolve()
    images = []
    seen_stems: set[str] = set()
    for path in sorted(image_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if path.stem in seen_stems:
            raise ValueError(f"duplicate example image stem: {path.stem}")
        seen_stems.add(path.stem)
        images.append(
            {
                "file_name": path.name,
                "path": workspace_relative(path, workspace_root),
                "category": example_category(path),
            }
        )
    return {
        "sample_set": "examples",
        "created_at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "image_root": workspace_relative(image_dir, workspace_root),
        "images": images,
        "notes": [
            "Generated for smpl_vertex_region_selector examples.",
            "This manifest is compatible with algorithm/tasks/surface_body_preannotation/main.py run --manifest.",
        ],
    }


def write_manifest(image_dir: Path, output: Path, workspace_root: Path) -> dict:
    manifest = build_manifest(image_dir=image_dir, workspace_root=workspace_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a CSE pipeline manifest for examples/images.")
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workspace-root", type=Path, default=repo_root().parent)
    parser.add_argument("--require-items", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    image_dir = args.image_dir if args.image_dir.is_absolute() else repo_root() / args.image_dir
    output = args.output if args.output.is_absolute() else repo_root() / args.output
    manifest = write_manifest(image_dir=image_dir, output=output, workspace_root=args.workspace_root)
    if args.require_items and not manifest["images"]:
        raise SystemExit(f"No example images found under {image_dir}")
    print(f"Wrote {len(manifest['images'])} image(s) to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

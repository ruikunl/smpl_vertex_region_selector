from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from .region_io import load_region_file, normalize_region_map, validate_region_map
from .schema import REGION_COLORS


def clean_vertex_map_stem(path: Path) -> str:
    name = path.name
    for suffix in (".vertex_map.npz", ".npz"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def read_vertex_map(path: Path) -> np.ndarray:
    payload = np.load(path)
    key = "vertex_map" if "vertex_map" in payload.files else payload.files[0]
    arr = np.asarray(payload[key])
    if arr.ndim != 2:
        raise ValueError(f"{path} must contain a 2D vertex map, got {arr.shape}")
    return arr.astype(np.int32, copy=False)


def find_background(stem: str, image_dirs: list[Path], size: tuple[int, int]) -> Image.Image:
    names = [
        f"{stem}.png",
        f"{stem}.jpg",
        f"{stem}.jpeg",
        f"{stem}.cse_vertex_overlay.jpg",
        f"{stem}.cse_vertex_overlay.png",
    ]
    for image_dir in image_dirs:
        for name in names:
            candidate = image_dir / name
            if candidate.exists():
                return Image.open(candidate).convert("RGB").resize(size)
    return Image.new("RGB", size, (32, 32, 32))


def render_overlay(
    vertex_map: np.ndarray,
    region_map: dict,
    background: Image.Image,
    alpha: int = 145,
) -> tuple[Image.Image, dict[str, int]]:
    out = np.asarray(background.convert("RGB"), dtype=np.float32).copy()
    blend = alpha / 255.0
    areas: dict[str, int] = {}
    for region, ids in region_map["regions"].items():
        ids_np = np.asarray(ids, dtype=np.int32)
        if ids_np.size == 0:
            areas[region] = 0
            continue
        mask = np.isin(vertex_map, ids_np)
        areas[region] = int(mask.sum())
        if not mask.any():
            continue
        color = REGION_COLORS.get(region, (255, 255, 255))
        color_arr = np.asarray(color, dtype=np.float32)
        out[mask] = out[mask] * (1.0 - blend) + color_arr * blend
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)), areas


def make_contact_sheet(images: list[Path], output: Path, thumb_width: int = 280) -> None:
    if not images:
        return
    thumbs: list[Image.Image] = []
    for path in images:
        im = Image.open(path).convert("RGB")
        ratio = thumb_width / max(1, im.width)
        thumbs.append(im.resize((thumb_width, max(1, int(im.height * ratio)))))
    cols = min(4, len(thumbs))
    rows = (len(thumbs) + cols - 1) // cols
    cell_h = max(im.height for im in thumbs)
    sheet = Image.new("RGB", (cols * thumb_width, rows * cell_h), (245, 245, 245))
    for idx, im in enumerate(thumbs):
        x = (idx % cols) * thumb_width
        y = (idx // cols) * cell_h
        sheet.paste(im, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render region overlays from DensePose CSE vertex_map.npz files.")
    parser.add_argument("--region-map", type=Path, required=True, help="region_map.json or region_map.csv.")
    parser.add_argument("--vertex-map-dir", type=Path, help="Directory containing *.vertex_map.npz files.")
    parser.add_argument("--vertex-map", type=Path, action="append", default=[], help="Single vertex map path; repeatable.")
    parser.add_argument("--image-dir", type=Path, action="append", default=[], help="Optional original/CSE overlay image directory.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/region_preview"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--write-summary", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    region_map = normalize_region_map(load_region_file(args.region_map))
    issues = validate_region_map(region_map)
    errors = [issue.message for issue in issues if issue.level == "error"]
    if errors:
        raise SystemExit("\n".join(errors))

    paths = list(args.vertex_map)
    if args.vertex_map_dir:
        paths.extend(sorted(args.vertex_map_dir.glob("*.npz")))
    if args.limit > 0:
        paths = paths[: args.limit]
    if not paths:
        raise SystemExit("No vertex maps provided.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    summary: dict[str, object] = {"region_map": str(args.region_map), "items": []}
    for path in paths:
        vertex_map = read_vertex_map(path)
        stem = clean_vertex_map_stem(path)
        size = (vertex_map.shape[1], vertex_map.shape[0])
        background = find_background(stem, args.image_dir, size)
        overlay, areas = render_overlay(vertex_map, region_map, background)
        out_path = args.output_dir / f"{stem}.regions_overlay.jpg"
        overlay.save(out_path, quality=92)
        rendered.append(out_path)
        summary["items"].append({"vertex_map": str(path), "overlay": str(out_path), "areas": areas})
    make_contact_sheet(rendered, args.output_dir / "contact_sheet.jpg")
    if args.write_summary:
        with (args.output_dir / "summary.json").open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    print(f"Rendered {len(rendered)} overlays to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

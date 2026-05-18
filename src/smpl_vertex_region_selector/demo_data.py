from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import numpy as np

from .region_io import empty_region_map, write_region_csv, write_region_map


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create tiny demo data for selector smoke tests.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/demo"))
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    payload = empty_region_map(status="demo")
    payload["regions"]["abdomen_front"] = [10, 11, 12, 13]
    payload["regions"]["lower_back"] = [20, 21, 22, 23]
    payload["region_sources"]["abdomen_front"] = "demo"
    payload["region_sources"]["lower_back"] = "demo"
    json_path = args.output_dir / "region_map.demo.json"
    csv_path = args.output_dir / "region_map.demo.csv"
    write_region_map(json_path, payload)
    write_region_csv(csv_path, payload)

    vertex_map = np.full((80, 120), -1, dtype=np.int32)
    vertex_map[20:50, 35:70] = 10
    vertex_map[50:65, 40:75] = 12
    vertex_map[15:45, 75:100] = 20
    np.savez_compressed(args.output_dir / "demo.vertex_map.npz", vertex_map=vertex_map)
    print(f"Wrote demo data to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

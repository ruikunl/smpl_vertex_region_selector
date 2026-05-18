from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .region_io import load_region_file, write_region_csv, write_region_map


def default_output() -> Path:
    return (
        Path.cwd().parent
        / "algorithm"
        / "experiments"
        / "surface_body_preannotation"
        / "regions"
        / "smpl_27554_region_map.json"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export a selector region map into the surface_body_preannotation-compatible path."
    )
    parser.add_argument("--input", type=Path, required=True, help="Selector region_map.json or region_map.csv.")
    parser.add_argument("--output", type=Path, default=default_output())
    parser.add_argument("--status", default="confirmed")
    parser.add_argument("--csv-output", type=Path, help="Optional CSV export next to the compatible JSON.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    payload = load_region_file(args.input)
    exported = write_region_map(args.output, payload, status=args.status)
    csv_output = args.csv_output or args.output.with_suffix(".csv")
    write_region_csv(csv_output, exported)
    print(f"Wrote {args.output}")
    print(f"Wrote {csv_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

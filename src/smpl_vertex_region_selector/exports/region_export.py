from __future__ import annotations

from pathlib import Path

from ..region_io import write_region_csv, write_region_map
from ..selection.region_state import RegionState


def export_region_bundle(output_dir: Path, state: RegionState, status: str = "confirmed") -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = state.to_region_map(status=status)
    json_path = output_dir / "region_map.json"
    csv_path = output_dir / "region_map.csv"
    txt_dir = output_dir / "vertex_ids"
    txt_dir.mkdir(parents=True, exist_ok=True)
    write_region_map(json_path, payload, status=status)
    write_region_csv(csv_path, payload)
    for region, ids in payload["regions"].items():
        with (txt_dir / f"{region}.txt").open("w", encoding="utf-8") as handle:
            for vertex_id in ids:
                handle.write(f"{vertex_id}\n")
    return {"json": json_path, "csv": csv_path, "txt_dir": txt_dir}

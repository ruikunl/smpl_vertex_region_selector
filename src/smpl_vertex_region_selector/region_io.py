from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from .schema import DEFAULT_REGIONS, MESH_NAME, VERTEX_COUNT, ValidationIssue


def utc_now_compact() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def normalize_vertex_ids(values: Iterable[Any], vertex_count: int = VERTEX_COUNT) -> list[int]:
    ids: set[int] = set()
    for value in values:
        item = int(value)
        if item < 0 or item >= vertex_count:
            raise ValueError(f"vertex id {item} is outside [0, {vertex_count - 1}]")
        ids.add(item)
    return sorted(ids)


def empty_region_map(status: str = "draft") -> dict[str, Any]:
    return {
        "mesh_name": MESH_NAME,
        "vertex_count": VERTEX_COUNT,
        "status": status,
        "created_at": utc_now_compact(),
        "created_by": "smpl_vertex_region_selector",
        "region_sources": {name: "empty" for name in DEFAULT_REGIONS},
        "regions": {name: [] for name in DEFAULT_REGIONS},
    }


def normalize_region_map(payload: dict[str, Any], status: Optional[str] = None) -> dict[str, Any]:
    mesh_name = payload.get("mesh_name", MESH_NAME)
    vertex_count = int(payload.get("vertex_count", VERTEX_COUNT))
    if mesh_name != MESH_NAME:
        raise ValueError(f"expected mesh_name {MESH_NAME!r}, got {mesh_name!r}")
    if vertex_count != VERTEX_COUNT:
        raise ValueError(f"expected vertex_count {VERTEX_COUNT}, got {vertex_count}")

    input_regions = payload.get("regions", {})
    if not isinstance(input_regions, dict):
        raise ValueError("region map must contain a regions object")

    regions: dict[str, list[int]] = {}
    for name in DEFAULT_REGIONS:
        regions[name] = normalize_vertex_ids(input_regions.get(name, []), vertex_count)
    for name, ids in input_regions.items():
        if name not in regions:
            regions[str(name)] = normalize_vertex_ids(ids, vertex_count)

    sources_in = payload.get("region_sources", {})
    sources = {name: sources_in.get(name, "manual") for name in regions}
    return {
        **payload,
        "mesh_name": MESH_NAME,
        "vertex_count": VERTEX_COUNT,
        "status": status or payload.get("status", "draft"),
        "created_at": payload.get("created_at", utc_now_compact()),
        "created_by": payload.get("created_by", "smpl_vertex_region_selector"),
        "region_sources": sources,
        "regions": regions,
    }


def validate_region_map(payload: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if payload.get("mesh_name") != MESH_NAME:
        issues.append(ValidationIssue("error", f"mesh_name must be {MESH_NAME!r}"))
    if int(payload.get("vertex_count", -1)) != VERTEX_COUNT:
        issues.append(ValidationIssue("error", f"vertex_count must be {VERTEX_COUNT}"))
    regions = payload.get("regions")
    if not isinstance(regions, dict):
        return issues + [ValidationIssue("error", "regions must be an object")]
    for name, ids in regions.items():
        if not isinstance(ids, list):
            issues.append(ValidationIssue("error", f"{name}: vertex ids must be a list"))
            continue
        seen: set[int] = set()
        for value in ids:
            try:
                item = int(value)
            except Exception:
                issues.append(ValidationIssue("error", f"{name}: non-integer vertex id {value!r}"))
                continue
            if item < 0 or item >= VERTEX_COUNT:
                issues.append(ValidationIssue("error", f"{name}: vertex id {item} outside valid range"))
            if item in seen:
                issues.append(ValidationIssue("warning", f"{name}: duplicate vertex id {item}"))
            seen.add(item)
    return issues


def read_region_map(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return normalize_region_map(json.load(handle))


def write_region_map(path: Path, payload: dict[str, Any], status: Optional[str] = None) -> dict[str, Any]:
    normalized = normalize_region_map(payload, status=status)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return normalized


def write_region_csv(path: Path, payload: dict[str, Any]) -> None:
    normalized = normalize_region_map(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["region", "vertex_id"])
        for region, ids in normalized["regions"].items():
            if not ids:
                writer.writerow([region, ""])
            else:
                for vertex_id in ids:
                    writer.writerow([region, vertex_id])


def read_region_csv(path: Path) -> dict[str, Any]:
    regions: dict[str, list[int]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            region = (row.get("region") or "").strip()
            value = (row.get("vertex_id") or "").strip()
            if not region:
                continue
            regions.setdefault(region, [])
            if value:
                regions[region].append(int(value))
    payload = empty_region_map()
    payload["regions"].update(regions)
    payload["region_sources"].update({name: "csv_import" for name in regions})
    return normalize_region_map(payload)


def load_region_file(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".csv":
        return read_region_csv(path)
    return read_region_map(path)

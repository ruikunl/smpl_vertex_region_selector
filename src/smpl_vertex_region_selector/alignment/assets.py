from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class TriViewAsset:
    name: str
    image_path: Path
    vertex_id_map_path: Path
    image: Image.Image
    vertex_id_map: np.ndarray


@dataclass(frozen=True)
class AlignmentAssets:
    root: Path
    status: str
    mapping_path: Path
    vertex_ids: np.ndarray
    surface_points: np.ndarray
    tri_views: dict[str, TriViewAsset]
    fallback_ratio: float | None = None
    warnings: tuple[str, ...] = ()


def _resolve_asset_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    root_candidate = root / path
    if root_candidate.exists():
        return root_candidate
    for index in range(1, len(path.parts)):
        suffix_candidate = root.joinpath(*path.parts[index:])
        if suffix_candidate.exists():
            return suffix_candidate
    return Path.cwd() / path


def load_alignment_assets(root: Path) -> AlignmentAssets:
    report_path = root / "alignment_report.json"
    mapping_path = root / "smpl_27554_to_surface_map.npz"
    manifest_path = root / "tri_view_manifest.json"
    if not report_path.exists() or not mapping_path.exists() or not manifest_path.exists():
        raise FileNotFoundError(f"Alignment assets not found under {root}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    mapping = np.load(mapping_path)
    vertex_ids = np.asarray(mapping["vertex_id"], dtype=np.int32)
    surface_points = np.asarray(mapping["surface_points"], dtype=np.float32)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tri_views: dict[str, TriViewAsset] = {}
    for item in manifest.get("tri_views", []):
        name = str(item["view"])
        image_path = _resolve_asset_path(root, str(item["image"]))
        map_path = _resolve_asset_path(root, str(item["vertex_id_map"]))
        payload = np.load(map_path)
        tri_views[name] = TriViewAsset(
            name=name,
            image_path=image_path,
            vertex_id_map_path=map_path,
            image=Image.open(image_path).convert("RGB"),
            vertex_id_map=np.asarray(payload["vertex_id_map"], dtype=np.int32),
        )
    return AlignmentAssets(
        root=root,
        status=str(report.get("status", "unknown")),
        mapping_path=mapping_path,
        vertex_ids=vertex_ids,
        surface_points=surface_points,
        tri_views=tri_views,
        fallback_ratio=float(report["fallback_ratio"]) if "fallback_ratio" in report else None,
        warnings=tuple(str(item.get("message", item)) for item in report.get("warnings", [])),
    )

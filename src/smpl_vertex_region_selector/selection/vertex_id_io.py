from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image

from ..region_io import load_region_file, normalize_vertex_ids
from ..schema import VERTEX_COUNT


_TOKEN_RE = re.compile(r"[-+]?\d+(?:\s*-\s*[-+]?\d+)?")


@dataclass(frozen=True)
class CseVertexMap:
    path: Path
    vertex_map: np.ndarray
    key: str

    @property
    def shape(self) -> tuple[int, int]:
        return int(self.vertex_map.shape[0]), int(self.vertex_map.shape[1])

    @property
    def valid_pixel_count(self) -> int:
        return int(np.count_nonzero(self.vertex_map >= 0))

    @property
    def unique_vertex_count(self) -> int:
        return int(np.unique(self.vertex_map[self.vertex_map >= 0]).size)

    @property
    def valid_vertex_ids(self) -> list[int]:
        return np.unique(self.vertex_map[self.vertex_map >= 0]).astype(int).tolist()


def parse_vertex_id_text(text: str, vertex_count: int = VERTEX_COUNT) -> list[int]:
    """Parse ids like ``12, 55, 100-130`` into sorted unique vertex ids."""

    values: list[int] = []
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0).replace(" ", "")
        if "-" in token[1:]:
            split_at = token[1:].find("-") + 1
            start = int(token[:split_at])
            end = int(token[split_at + 1 :])
            step = 1 if start <= end else -1
            values.extend(range(start, end + step, step))
        else:
            values.append(int(token))
    return normalize_vertex_ids(values, vertex_count=vertex_count)


def load_vertex_ids(path: Path, vertex_count: int = VERTEX_COUNT) -> list[int]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = load_region_file(path)
        values: list[int] = []
        for ids in payload.get("regions", {}).values():
            values.extend(ids)
        return normalize_vertex_ids(values, vertex_count=vertex_count)
    if suffix == ".csv":
        return _load_vertex_ids_csv(path, vertex_count=vertex_count)
    return parse_vertex_id_text(path.read_text(encoding="utf-8"), vertex_count=vertex_count)


def _load_vertex_ids_csv(path: Path, vertex_count: int = VERTEX_COUNT) -> list[int]:
    values: list[int] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            has_header = csv.Sniffer().has_header(sample) if sample.strip() else False
        except csv.Error:
            has_header = False
        if has_header:
            reader = csv.DictReader(handle)
            for row in reader:
                value = row.get("vertex_id")
                if value is not None and str(value).strip():
                    values.append(int(value))
                    continue
                for cell in row.values():
                    values.extend(parse_vertex_id_text(str(cell), vertex_count=vertex_count))
        else:
            reader = csv.reader(handle)
            for row in reader:
                for cell in row:
                    values.extend(parse_vertex_id_text(cell, vertex_count=vertex_count))
    return normalize_vertex_ids(values, vertex_count=vertex_count)


def load_cse_vertex_map(path: Path, vertex_count: int = VERTEX_COUNT) -> CseVertexMap:
    suffix = path.suffix.lower()
    key = "array"
    if suffix == ".npz":
        payload = np.load(path)
        if "vertex_id" in payload:
            key = "vertex_id"
            vertex_map = payload["vertex_id"]
        elif "vertex_map" in payload:
            key = "vertex_map"
            vertex_map = payload["vertex_map"]
        else:
            raise ValueError(f"{path} must contain a 'vertex_id' or 'vertex_map' array")
    elif suffix == ".npy":
        vertex_map = np.load(path)
    else:
        raise ValueError("CSE vertex map must be a .npz or .npy file")
    vertex_map = np.asarray(vertex_map, dtype=np.int32)
    _validate_vertex_map(vertex_map, vertex_count=vertex_count)
    return CseVertexMap(path=path, vertex_map=vertex_map, key=key)


def _validate_vertex_map(vertex_map: np.ndarray, vertex_count: int = VERTEX_COUNT) -> None:
    if vertex_map.ndim != 2:
        raise ValueError(f"vertex map must be 2D, got shape {vertex_map.shape}")
    valid = vertex_map[vertex_map >= 0]
    if valid.size == 0:
        raise ValueError("vertex map contains no valid vertex ids")
    if int(valid.max()) >= vertex_count:
        raise ValueError(f"vertex map contains id {int(valid.max())}, outside [0, {vertex_count - 1}]")


def ids_from_vertex_map_mask(vertex_map: np.ndarray, mask: np.ndarray, vertex_count: int = VERTEX_COUNT) -> list[int]:
    _validate_vertex_map(np.asarray(vertex_map, dtype=np.int32), vertex_count=vertex_count)
    mask = np.asarray(mask)
    if mask.shape != vertex_map.shape:
        raise ValueError(f"mask shape {mask.shape} does not match vertex map shape {vertex_map.shape}")
    selected = vertex_map[(mask != 0) & (vertex_map >= 0)]
    return normalize_vertex_ids(np.unique(selected).astype(int).tolist(), vertex_count=vertex_count)


def ids_from_pixel_points(
    vertex_map: np.ndarray,
    points: Iterable[tuple[int, int]],
    vertex_count: int = VERTEX_COUNT,
) -> list[int]:
    _validate_vertex_map(np.asarray(vertex_map, dtype=np.int32), vertex_count=vertex_count)
    values: list[int] = []
    height, width = vertex_map.shape
    for x, y in points:
        ix, iy = int(x), int(y)
        if ix < 0 or iy < 0 or ix >= width or iy >= height:
            continue
        vertex_id = int(vertex_map[iy, ix])
        if vertex_id >= 0:
            values.append(vertex_id)
    return normalize_vertex_ids(values, vertex_count=vertex_count)


def load_mask_or_points(path: Path, vertex_map: np.ndarray, vertex_count: int = VERTEX_COUNT) -> list[int]:
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
        mask = np.asarray(Image.open(path).convert("L"))
        return ids_from_vertex_map_mask(vertex_map, mask, vertex_count=vertex_count)
    if suffix == ".npy":
        payload = np.load(path)
        return _ids_from_mask_or_points_array(payload, vertex_map, vertex_count=vertex_count)
    if suffix == ".npz":
        payload = np.load(path)
        key = "mask" if "mask" in payload else "points" if "points" in payload else payload.files[0]
        return _ids_from_mask_or_points_array(payload[key], vertex_map, vertex_count=vertex_count)
    if suffix == ".csv":
        return ids_from_pixel_points(vertex_map, _read_pixel_points_csv(path), vertex_count=vertex_count)
    raise ValueError("mask/points input must be an image, .npy, .npz, or .csv file")


def _ids_from_mask_or_points_array(
    payload: np.ndarray,
    vertex_map: np.ndarray,
    vertex_count: int = VERTEX_COUNT,
) -> list[int]:
    array = np.asarray(payload)
    if array.ndim == 2 and array.shape == vertex_map.shape:
        return ids_from_vertex_map_mask(vertex_map, array, vertex_count=vertex_count)
    if array.ndim == 2 and array.shape[1] >= 2:
        points = [(int(row[0]), int(row[1])) for row in array]
        return ids_from_pixel_points(vertex_map, points, vertex_count=vertex_count)
    raise ValueError(
        f"expected a mask matching {vertex_map.shape} or an Nx2 point array, got shape {array.shape}"
    )


def _read_pixel_points_csv(path: Path) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            has_header = csv.Sniffer().has_header(sample) if sample.strip() else False
        except csv.Error:
            has_header = False
        if has_header:
            reader = csv.DictReader(handle)
            for row in reader:
                x_value = row.get("x") or row.get("col") or row.get("column")
                y_value = row.get("y") or row.get("row")
                if x_value is None or y_value is None:
                    continue
                points.append((int(float(x_value)), int(float(y_value))))
        else:
            reader = csv.reader(handle)
            for row in reader:
                if len(row) < 2:
                    continue
                points.append((int(float(row[0])), int(float(row[1]))))
    return points

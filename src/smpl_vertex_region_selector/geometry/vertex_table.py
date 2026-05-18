from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from ..schema import VERTEX_COUNT


@dataclass(frozen=True)
class VertexTable:
    """Authoritative smpl_27554 vertex id table plus display coordinates."""

    vertex_ids: np.ndarray
    points: np.ndarray
    columns: tuple[str, ...]
    source_path: Path
    coordinate_mode: str

    @property
    def vertex_count(self) -> int:
        return int(self.vertex_ids.size)

    def point_for_id(self, vertex_id: int) -> np.ndarray:
        if vertex_id < 0 or vertex_id >= self.vertex_count:
            raise IndexError(f"vertex id {vertex_id} outside [0, {self.vertex_count - 1}]")
        return self.points[vertex_id]


def _normalize_columns(rows: list[dict[str, str]], columns: Iterable[str]) -> np.ndarray:
    raw = np.asarray([[float(row[col]) for col in columns] for row in rows], dtype=np.float32)
    mins = raw.min(axis=0)
    maxs = raw.max(axis=0)
    denom = np.where(maxs > mins, maxs - mins, 1.0)
    return (raw - mins) / denom


def _points_from_rows(rows: list[dict[str, str]], columns: set[str], mode: str) -> tuple[np.ndarray, str]:
    if mode in {"auto", "mds"} and {"mds0_norm", "mds1_norm", "mds2_norm"}.issubset(columns):
        norm = _normalize_columns(rows, ("mds0_norm", "mds1_norm", "mds2_norm"))
        return (norm - 0.5) * 4.0, "mds"
    if mode in {"auto", "atlas"} and {"atlas_u_norm", "atlas_v_norm"}.issubset(columns):
        norm = _normalize_columns(rows, ("atlas_u_norm", "atlas_v_norm"))
        points = np.zeros((len(rows), 3), dtype=np.float32)
        points[:, 0] = (norm[:, 0] - 0.5) * 4.0
        points[:, 2] = (0.5 - norm[:, 1]) * 4.0
        return points, "atlas"
    if mode != "auto":
        raise ValueError(f"CSV does not contain coordinates for requested mode {mode!r}")
    ids = np.asarray([int(row["vertex_id"]) for row in rows], dtype=np.int32)
    points = np.zeros((len(rows), 3), dtype=np.float32)
    points[:, 0] = (ids % 256) / 255.0 * 4.0 - 2.0
    points[:, 2] = (ids // 256) / 108.0 * 4.0 - 2.0
    return points, "grid"


def load_vertex_table(path: Path, mode: str = "auto", strict: bool = True) -> VertexTable:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "vertex_id" not in reader.fieldnames:
            raise ValueError(f"{path} must contain a vertex_id column")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path} contains no vertices")
    ids = np.asarray([int(row["vertex_id"]) for row in rows], dtype=np.int32)
    if len(set(ids.tolist())) != ids.size:
        raise ValueError(f"{path} contains duplicate vertex ids")
    order = np.argsort(ids)
    rows = [rows[int(i)] for i in order]
    ids = ids[order]
    if strict:
        if ids.size != VERTEX_COUNT:
            raise ValueError(f"{path} has {ids.size} vertices, expected {VERTEX_COUNT}")
        if int(ids[0]) != 0 or int(ids[-1]) != VERTEX_COUNT - 1:
            raise ValueError(f"{path} must cover vertex ids 0..{VERTEX_COUNT - 1}")
    columns = set(reader.fieldnames)
    points, resolved_mode = _points_from_rows(rows, columns, mode)
    return VertexTable(
        vertex_ids=ids,
        points=points.astype(np.float32, copy=False),
        columns=tuple(reader.fieldnames),
        source_path=path,
        coordinate_mode=resolved_mode,
    )

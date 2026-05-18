from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from ..schema import VERTEX_COUNT

ALIGNED_MESH = "aligned_mesh"
VISUAL_REFERENCE = "visual_reference"
POINT_CLOUD_ONLY = "point_cloud_only"
LOAD_ERROR = "load_error"


@dataclass(frozen=True)
class MeshAsset:
    path: Optional[Path]
    status: str
    vertex_count: int
    message: str
    vertices: Optional[np.ndarray] = None
    faces: Optional[np.ndarray] = None

    @property
    def is_aligned(self) -> bool:
        return self.status == ALIGNED_MESH


def _load_with_trimesh(path: Path) -> tuple[np.ndarray, np.ndarray]:
    import trimesh

    mesh = trimesh.load(path, force="mesh", process=False)
    if mesh.is_empty:
        raise ValueError(f"{path} is empty or not a mesh")
    return np.asarray(mesh.vertices, dtype=np.float32), np.asarray(mesh.faces, dtype=np.int32)


def _load_with_open3d(path: Path) -> tuple[np.ndarray, np.ndarray]:
    import open3d as o3d

    mesh = o3d.io.read_triangle_mesh(str(path))
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.triangles, dtype=np.int32)
    if vertices.size == 0:
        raise ValueError(f"{path} has no vertices")
    return vertices, faces


def _load_obj_vertices(path: Path) -> tuple[np.ndarray, np.ndarray]:
    vertices = []
    faces = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("v "):
                _, x, y, z, *_ = line.strip().split()
                vertices.append((float(x), float(y), float(z)))
            elif line.startswith("f "):
                items = [part.split("/")[0] for part in line.strip().split()[1:]]
                if len(items) >= 3:
                    faces.append(tuple(int(item) - 1 for item in items[:3]))
    if not vertices:
        raise ValueError(f"{path} has no OBJ vertices")
    return np.asarray(vertices, dtype=np.float32), np.asarray(faces, dtype=np.int32)


def load_mesh_asset(path: Optional[Path]) -> MeshAsset:
    if path is None:
        return MeshAsset(
            path=None,
            status=POINT_CLOUD_ONLY,
            vertex_count=0,
            message="No body mesh loaded; using smpl_27554 point cloud only.",
        )
    try:
        suffix = path.suffix.lower()
        if suffix == ".obj":
            vertices, faces = _load_obj_vertices(path)
        else:
            try:
                vertices, faces = _load_with_trimesh(path)
            except Exception:
                vertices, faces = _load_with_open3d(path)
        count = int(vertices.shape[0])
        if count == VERTEX_COUNT:
            return MeshAsset(
                path=path,
                status=ALIGNED_MESH,
                vertex_count=count,
                message="Mesh has 27,554 vertices and can be treated as smpl_27554-aligned.",
                vertices=vertices,
                faces=faces,
            )
        return MeshAsset(
            path=path,
            status=VISUAL_REFERENCE,
            vertex_count=count,
            message=(
                f"Mesh has {count} vertices, not {VERTEX_COUNT}; it is a visual reference only, "
                "and its local vertex ids are not exported."
            ),
            vertices=vertices,
            faces=faces,
        )
    except Exception as exc:
        return MeshAsset(
            path=path,
            status=LOAD_ERROR,
            vertex_count=0,
            message=f"Could not load mesh: {exc}",
        )

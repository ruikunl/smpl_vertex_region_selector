from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Optional

import numpy as np

from .alignment.renderer import VIEW_SPECS, render_vertex_id_view, write_obj
from .alignment.smpl_assets import write_json
from .schema import VERTEX_COUNT


PART_COUNTS = [
    ("head", 2200, (0.0, 1.72, 0.0), (0.18, 0.22, 0.16)),
    ("neck", 500, (0.0, 1.48, 0.0), (0.10, 0.11, 0.09)),
    ("chest_front", 3900, (0.0, 1.18, -0.035), (0.34, 0.36, 0.18)),
    ("abdomen_front", 3900, (0.0, 0.86, -0.045), (0.30, 0.30, 0.17)),
    ("pelvis_front", 2100, (0.0, 0.56, 0.0), (0.28, 0.20, 0.16)),
    ("left_upper_arm", 1300, (-0.48, 1.14, 0.0), (0.09, 0.34, 0.08)),
    ("right_upper_arm", 1300, (0.48, 1.14, 0.0), (0.09, 0.34, 0.08)),
    ("left_lower_arm", 1100, (-0.58, 0.78, 0.0), (0.075, 0.30, 0.07)),
    ("right_lower_arm", 1100, (0.58, 0.78, 0.0), (0.075, 0.30, 0.07)),
    ("left_hand", 550, (-0.60, 0.45, -0.01), (0.075, 0.09, 0.055)),
    ("right_hand", 550, (0.60, 0.45, -0.01), (0.075, 0.09, 0.055)),
    ("left_upper_leg", 2200, (-0.16, 0.18, 0.0), (0.13, 0.36, 0.10)),
    ("right_upper_leg", 2200, (0.16, 0.18, 0.0), (0.13, 0.36, 0.10)),
    ("left_lower_leg", 1900, (-0.15, -0.28, 0.0), (0.10, 0.40, 0.08)),
    ("right_lower_leg", 1900, (0.15, -0.28, 0.0), (0.10, 0.40, 0.08)),
    ("left_foot", 427, (-0.15, -0.72, -0.08), (0.15, 0.06, 0.22)),
    ("right_foot", 427, (0.15, -0.72, -0.08), (0.15, 0.06, 0.22)),
]


def _fibonacci_ellipsoid(count: int, center: tuple[float, float, float], radii: tuple[float, float, float]) -> np.ndarray:
    idx = np.arange(count, dtype=np.float32)
    golden = np.pi * (3.0 - np.sqrt(5.0))
    y = 1.0 - 2.0 * (idx + 0.5) / count
    radius = np.sqrt(np.maximum(0.0, 1.0 - y * y))
    theta = golden * idx
    unit = np.stack([np.cos(theta) * radius, y, np.sin(theta) * radius], axis=1)
    return unit * np.asarray(radii, dtype=np.float32) + np.asarray(center, dtype=np.float32)


def make_demo_surface_points() -> tuple[np.ndarray, list[str]]:
    if sum(item[1] for item in PART_COUNTS) != VERTEX_COUNT:
        raise AssertionError("demo part counts must sum to smpl_27554 vertex count")
    points = []
    labels: list[str] = []
    for name, count, center, radii in PART_COUNTS:
        points.append(_fibonacci_ellipsoid(count, center, radii))
        labels.extend([name] * count)
    return np.concatenate(points, axis=0).astype(np.float32), labels


def _ellipsoid_mesh(
    center: tuple[float, float, float],
    radii: tuple[float, float, float],
    lat_steps: int = 12,
    lon_steps: int = 18,
) -> tuple[np.ndarray, np.ndarray]:
    vertices = []
    for lat in range(lat_steps + 1):
        phi = np.pi * lat / lat_steps
        for lon in range(lon_steps):
            theta = 2.0 * np.pi * lon / lon_steps
            x = np.sin(phi) * np.cos(theta)
            y = np.cos(phi)
            z = np.sin(phi) * np.sin(theta)
            vertices.append(
                (
                    center[0] + radii[0] * x,
                    center[1] + radii[1] * y,
                    center[2] + radii[2] * z,
                )
            )
    faces = []
    for lat in range(lat_steps):
        for lon in range(lon_steps):
            a = lat * lon_steps + lon
            b = lat * lon_steps + (lon + 1) % lon_steps
            c = (lat + 1) * lon_steps + lon
            d = (lat + 1) * lon_steps + (lon + 1) % lon_steps
            faces.append((a, c, b))
            faces.append((b, c, d))
    return np.asarray(vertices, dtype=np.float32), np.asarray(faces, dtype=np.int32)


def make_demo_mesh() -> tuple[np.ndarray, np.ndarray]:
    all_vertices = []
    all_faces = []
    offset = 0
    for _name, _count, center, radii in PART_COUNTS:
        vertices, faces = _ellipsoid_mesh(center, radii)
        all_vertices.append(vertices)
        all_faces.append(faces + offset)
        offset += int(vertices.shape[0])
    return np.concatenate(all_vertices, axis=0), np.concatenate(all_faces, axis=0)


def _write_vertex_csv(path: Path, points: np.ndarray, labels: list[str]) -> None:
    mins = points.min(axis=0)
    maxs = points.max(axis=0)
    denom = np.where(maxs > mins, maxs - mins, 1.0)
    norm = (points - mins) / denom
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["vertex_id", "part_hint", "mds0_norm", "mds1_norm", "mds2_norm", "atlas_u_norm", "atlas_v_norm"],
        )
        writer.writeheader()
        for vertex_id, point in enumerate(norm):
            writer.writerow(
                {
                    "vertex_id": vertex_id,
                    "part_hint": labels[vertex_id],
                    "mds0_norm": f"{float(point[0]):.8f}",
                    "mds1_norm": f"{float(point[1]):.8f}",
                    "mds2_norm": f"{float(point[2]):.8f}",
                    "atlas_u_norm": f"{float(point[0]):.8f}",
                    "atlas_v_norm": f"{float(1.0 - point[1]):.8f}",
                }
            )


def build_demo_assets(output_dir: Path, image_size: int = 768) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    points, labels = make_demo_surface_points()
    mesh_vertices, mesh_faces = make_demo_mesh()
    np.savez_compressed(
        output_dir / "smpl_27554_to_surface_map.npz",
        vertex_id=np.arange(VERTEX_COUNT, dtype=np.int32),
        surface_points=points,
        proxy_vertex_ids=np.full((VERTEX_COUNT,), -1, dtype=np.int32),
        methods=np.full((VERTEX_COUNT,), "demo_reference", dtype="U16"),
        barycentric=np.zeros((VERTEX_COUNT, 3), dtype=np.float32),
        face_ids=np.full((VERTEX_COUNT,), -1, dtype=np.int32),
        part_hint=np.asarray(labels, dtype="U32"),
    )
    _write_vertex_csv(output_dir / "vertex_template_points.csv", points, labels)
    write_obj(output_dir / "surface_proxy.obj", mesh_vertices, mesh_faces)
    write_obj(output_dir / "smpl_27554_surface_points.obj", points, None)

    tri_dir = output_dir / "tri_views"
    tri_views = []
    for view in ("front", "back", "left", "right"):
        tri_views.append(
            render_vertex_id_view(
                points,
                tri_dir / f"{view}.png",
                tri_dir / f"{view}.vertex_id_map.npz",
                view=view,
                image_size=image_size,
                point_radius=max(2, image_size // 220),
            )
        )
    report = {
        "status": "demo_reference",
        "message": "Generated a license-safe synthetic mannequin for UI demos. It is not an official SMPL/DensePose alignment.",
        "vertex_count": VERTEX_COUNT,
        "surface_proxy_obj": str(output_dir / "surface_proxy.obj"),
        "smpl_27554_surface_points_obj": str(output_dir / "smpl_27554_surface_points.obj"),
        "mapping_npz": str(output_dir / "smpl_27554_to_surface_map.npz"),
        "vertex_csv": str(output_dir / "vertex_template_points.csv"),
        "tri_views": tri_views,
        "view_specs": VIEW_SPECS,
        "asset_class": "open_source_safe_demo",
        "license": (
            "Generated by this tool for repository demos; no SMPL model, DensePose raw asset, "
            "or private dataset image is included."
        ),
    }
    write_json(output_dir / "tri_view_manifest.json", {"status": report["status"], "tri_views": tri_views})
    write_json(output_dir / "alignment_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate license-safe demo mannequin assets for the region selector GUI.")
    parser.add_argument("--output-dir", type=Path, default=Path("assets/demo_reference/generated"))
    parser.add_argument("--image-size", type=int, default=768)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_demo_assets(args.output_dir, image_size=args.image_size)
    print(f"{report['status']}: {report['message']}")
    print(f"Report: {args.output_dir / 'alignment_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import csv
import json
import urllib.request
from pathlib import Path
from typing import Optional

import numpy as np

from .alignment.renderer import VIEW_SPECS, render_vertex_id_view, write_obj
from .schema import VERTEX_COUNT


MAKEHUMAN_MESHES = {
    "female_generic": {
        "url": "https://raw.githubusercontent.com/makehumancommunity/makehuman-assets/master/base/proxymeshes/female_generic/female_generic.obj",
        "license": "CC0-1.0",
        "source": "makehumancommunity/makehuman-assets base/proxymeshes/female_generic",
    },
    "male_generic": {
        "url": "https://raw.githubusercontent.com/makehumancommunity/makehuman-assets/master/base/proxymeshes/male_generic/male_generic.obj",
        "license": "CC0-1.0",
        "source": "makehumancommunity/makehuman-assets base/proxymeshes/male_generic",
    },
    "proxy741": {
        "url": "https://raw.githubusercontent.com/makehumancommunity/makehuman-assets/master/base/proxymeshes/proxy741/proxy741.obj",
        "license": "CC0-1.0",
        "source": "makehumancommunity/makehuman-assets base/proxymeshes/proxy741",
    },
}


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def download_makehuman_mesh(name: str, output_dir: Path) -> Path:
    if name not in MAKEHUMAN_MESHES:
        raise ValueError(f"Unknown MakeHuman mesh {name!r}; choices: {', '.join(sorted(MAKEHUMAN_MESHES))}")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.obj"
    if path.exists():
        return path
    request = urllib.request.Request(
        str(MAKEHUMAN_MESHES[name]["url"]),
        headers={"User-Agent": "smpl-vertex-region-selector/0.1"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        path.write_bytes(response.read())
    return path


def resolve_target_mesh(target_mesh: str, raw_dir: Path) -> tuple[Path, dict[str, str]]:
    if target_mesh.startswith("makehuman:"):
        name = target_mesh.split(":", 1)[1]
        path = download_makehuman_mesh(name, raw_dir)
        meta = dict(MAKEHUMAN_MESHES[name])
        meta["name"] = name
        return path, meta
    path = Path(target_mesh)
    if not path.exists():
        raise FileNotFoundError(f"Target mesh not found: {path}")
    return path, {"name": path.stem, "source": str(path), "license": "user-provided"}


def load_mesh(path: Path) -> tuple[np.ndarray, np.ndarray]:
    try:
        import trimesh
    except Exception as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("trimesh is required; install with pip install -e \".[gui]\"") from exc
    mesh = trimesh.load(path, process=False, force="mesh")
    vertices = np.asarray(mesh.vertices, dtype=np.float32)
    faces = np.asarray(mesh.faces, dtype=np.int32)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or faces.size == 0:
        raise ValueError(f"{path} did not load as a triangle mesh")
    return vertices, faces


def load_source_points(source_alignment: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    payload = np.load(source_alignment)
    vertex_ids = np.asarray(payload["vertex_id"], dtype=np.int32)
    surface_points = np.asarray(payload["surface_points"], dtype=np.float32)
    if vertex_ids.shape != (VERTEX_COUNT,) or surface_points.shape != (VERTEX_COUNT, 3):
        raise ValueError(f"{source_alignment} must contain {VERTEX_COUNT} vertex ids and surface points")
    labels = np.asarray(payload["part_hint"], dtype="U64") if "part_hint" in payload.files else np.full((VERTEX_COUNT,), "smpl_projected", dtype="U64")
    return vertex_ids, surface_points, labels


def align_points_to_target_bbox(source_points: np.ndarray, target_vertices: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    src_min = source_points.min(axis=0)
    src_max = source_points.max(axis=0)
    tgt_min = target_vertices.min(axis=0)
    tgt_max = target_vertices.max(axis=0)
    src_span = np.maximum(src_max - src_min, 1e-6)
    tgt_span = np.maximum(tgt_max - tgt_min, 1e-6)
    scale = float(tgt_span[1] / src_span[1])
    src_center = (src_min + src_max) * 0.5
    tgt_center = (tgt_min + tgt_max) * 0.5
    aligned = (source_points - src_center) * scale + tgt_center
    # Keep foot-to-head vertical registration more stable than center alignment.
    aligned[:, 1] += float(tgt_min[1] - aligned[:, 1].min())
    info = {
        "source_bounds": {"min": src_min.tolist(), "max": src_max.tolist()},
        "target_bounds": {"min": tgt_min.tolist(), "max": tgt_max.tolist()},
        "uniform_height_scale": scale,
        "method": "bbox_height_scale_center_xz_floor_y",
    }
    return aligned.astype(np.float32, copy=False), info


def align_points_to_target_bbox_anisotropic(source_points: np.ndarray, target_vertices: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    src_min = source_points.min(axis=0)
    src_max = source_points.max(axis=0)
    tgt_min = target_vertices.min(axis=0)
    tgt_max = target_vertices.max(axis=0)
    src_span = np.maximum(src_max - src_min, 1e-6)
    tgt_span = np.maximum(tgt_max - tgt_min, 1e-6)
    normalized = (source_points - src_min) / src_span
    aligned = normalized * tgt_span + tgt_min
    info = {
        "source_bounds": {"min": src_min.tolist(), "max": src_max.tolist()},
        "target_bounds": {"min": tgt_min.tolist(), "max": tgt_max.tolist()},
        "axis_scales": (tgt_span / src_span).tolist(),
        "method": "bbox_anisotropic_xyz",
    }
    return aligned.astype(np.float32, copy=False), info


def pca_basis(points: np.ndarray, primary_direction: np.ndarray | None = None) -> np.ndarray:
    centered = points - points.mean(axis=0, keepdims=True)
    if points.shape[0] < 3:
        basis = np.eye(3, dtype=np.float32)
    else:
        covariance = centered.T @ centered / max(points.shape[0] - 1, 1)
        _values, vectors = np.linalg.eigh(covariance)
        basis = vectors[:, np.argsort(_values)[::-1]].T.astype(np.float32)
    if primary_direction is not None and float(np.dot(basis[0], primary_direction)) < 0:
        basis[0] *= -1.0
    # Keep a right-handed basis after optional sign flip.
    basis[2] = np.cross(basis[0], basis[1])
    norm = np.linalg.norm(basis[2])
    if norm > 1e-6:
        basis[2] /= norm
    basis[1] = np.cross(basis[2], basis[0])
    norm = np.linalg.norm(basis[1])
    if norm > 1e-6:
        basis[1] /= norm
    return basis


def primary_direction_for_part(part: str, source: bool) -> np.ndarray | None:
    if part in {"left_arm", "left_upper_arm", "left_lower_arm", "left_hand"}:
        return np.asarray([-1.0, 0.0, 0.0] if source else [-0.65, -0.76, 0.0], dtype=np.float32)
    if part in {"right_arm", "right_upper_arm", "right_lower_arm", "right_hand"}:
        return np.asarray([1.0, 0.0, 0.0] if source else [0.65, -0.76, 0.0], dtype=np.float32)
    if part in {"left_leg", "right_leg", "left_upper_leg", "right_upper_leg", "left_lower_leg", "right_lower_leg"}:
        return np.asarray([0.0, -1.0, 0.0], dtype=np.float32)
    return None


def align_points_to_target_pca_bbox(source_points: np.ndarray, target_vertices: np.ndarray, part: str) -> tuple[np.ndarray, dict[str, object]]:
    src_center = source_points.mean(axis=0)
    tgt_center = target_vertices.mean(axis=0)
    src_basis = pca_basis(source_points, primary_direction_for_part(part, source=True))
    tgt_basis = pca_basis(target_vertices, primary_direction_for_part(part, source=False))
    src_local = (source_points - src_center) @ src_basis.T
    tgt_local = (target_vertices - tgt_center) @ tgt_basis.T
    src_min = src_local.min(axis=0)
    src_max = src_local.max(axis=0)
    tgt_min = tgt_local.min(axis=0)
    tgt_max = tgt_local.max(axis=0)
    src_span = np.maximum(src_max - src_min, 1e-6)
    tgt_span = np.maximum(tgt_max - tgt_min, 1e-6)
    normalized = (src_local - src_min) / src_span
    aligned_local = normalized * tgt_span + tgt_min
    aligned = aligned_local @ tgt_basis + tgt_center
    info = {
        "source_local_bounds": {"min": src_min.tolist(), "max": src_max.tolist()},
        "target_local_bounds": {"min": tgt_min.tolist(), "max": tgt_max.tolist()},
        "axis_scales": (tgt_span / src_span).tolist(),
        "source_basis": src_basis.tolist(),
        "target_basis": tgt_basis.tolist(),
        "method": "pca_bbox_anisotropic",
    }
    return aligned.astype(np.float32, copy=False), info


def classify_source_body_parts(points: np.ndarray) -> np.ndarray:
    mins = points.min(axis=0)
    maxs = points.max(axis=0)
    span = np.maximum(maxs - mins, 1e-6)
    center = (mins + maxs) * 0.5
    y_norm = (points[:, 1] - mins[1]) / span[1]
    x_rel = (points[:, 0] - center[0]) / (span[0] * 0.5)
    labels = np.full((points.shape[0],), "torso", dtype="U24")
    labels[(y_norm > 0.78) & (np.abs(x_rel) < 0.33)] = "head"
    labels[(y_norm < 0.43) & (points[:, 0] < center[0])] = "left_leg"
    labels[(y_norm < 0.43) & (points[:, 0] >= center[0])] = "right_leg"
    left_arm = (y_norm > 0.58) & (np.abs(x_rel) >= 0.33) & (points[:, 0] < center[0])
    right_arm = (y_norm > 0.58) & (np.abs(x_rel) >= 0.33) & (points[:, 0] >= center[0])
    low_left_arm = (y_norm >= 0.43) & (y_norm < 0.58) & (np.abs(x_rel) > 0.45) & (points[:, 0] < center[0])
    low_right_arm = (y_norm >= 0.43) & (y_norm < 0.58) & (np.abs(x_rel) > 0.45) & (points[:, 0] >= center[0])
    labels[left_arm | low_left_arm] = "left_arm"
    labels[right_arm | low_right_arm] = "right_arm"
    for side, coarse, upper, lower, hand in [
        ("left", "left_arm", "left_upper_arm", "left_lower_arm", "left_hand"),
        ("right", "right_arm", "right_upper_arm", "right_lower_arm", "right_hand"),
    ]:
        mask = labels == coarse
        if mask.any():
            xs = points[mask, 0]
            denom = max(float(xs.max() - xs.min()), 1e-6)
            if side == "left":
                distal = (float(xs.max()) - xs) / denom
            else:
                distal = (xs - float(xs.min())) / denom
            indices = np.where(mask)[0]
            labels[indices[distal < 0.48]] = upper
            labels[indices[(distal >= 0.48) & (distal < 0.84)]] = lower
            labels[indices[distal >= 0.84]] = hand
    for coarse, upper, lower in [
        ("left_leg", "left_upper_leg", "left_lower_leg"),
        ("right_leg", "right_upper_leg", "right_lower_leg"),
    ]:
        mask = labels == coarse
        if mask.any():
            ys = points[mask, 1]
            distal = (float(ys.max()) - ys) / max(float(ys.max() - ys.min()), 1e-6)
            indices = np.where(mask)[0]
            labels[indices[distal < 0.52]] = upper
            labels[indices[distal >= 0.52]] = lower
    return labels


def classify_target_body_parts(vertices: np.ndarray) -> np.ndarray:
    mins = vertices.min(axis=0)
    maxs = vertices.max(axis=0)
    span = np.maximum(maxs - mins, 1e-6)
    center = (mins + maxs) * 0.5
    y_norm = (vertices[:, 1] - mins[1]) / span[1]
    x_rel = (vertices[:, 0] - center[0]) / (span[0] * 0.5)
    labels = np.full((vertices.shape[0],), "torso", dtype="U24")
    labels[(y_norm > 0.80) & (np.abs(x_rel) < 0.45)] = "head"
    labels[(y_norm < 0.46) & (vertices[:, 0] < center[0])] = "left_leg"
    labels[(y_norm < 0.46) & (vertices[:, 0] >= center[0])] = "right_leg"
    left_arm = (y_norm > 0.45) & (y_norm < 0.82) & (np.abs(x_rel) > 0.36) & (vertices[:, 0] < center[0])
    right_arm = (y_norm > 0.45) & (y_norm < 0.82) & (np.abs(x_rel) > 0.36) & (vertices[:, 0] >= center[0])
    labels[left_arm] = "left_arm"
    labels[right_arm] = "right_arm"
    for coarse, upper, lower, hand in [
        ("left_arm", "left_upper_arm", "left_lower_arm", "left_hand"),
        ("right_arm", "right_upper_arm", "right_lower_arm", "right_hand"),
    ]:
        mask = labels == coarse
        if mask.any():
            ys = vertices[mask, 1]
            distal = (float(ys.max()) - ys) / max(float(ys.max() - ys.min()), 1e-6)
            indices = np.where(mask)[0]
            labels[indices[distal < 0.48]] = upper
            labels[indices[(distal >= 0.48) & (distal < 0.70)]] = lower
            labels[indices[distal >= 0.70]] = hand
    for coarse, upper, lower in [
        ("left_leg", "left_upper_leg", "left_lower_leg"),
        ("right_leg", "right_upper_leg", "right_lower_leg"),
    ]:
        mask = labels == coarse
        if mask.any():
            ys = vertices[mask, 1]
            distal = (float(ys.max()) - ys) / max(float(ys.max() - ys.min()), 1e-6)
            indices = np.where(mask)[0]
            labels[indices[distal < 0.52]] = upper
            labels[indices[distal >= 0.52]] = lower
    return labels


def faces_for_part(faces: np.ndarray, vertex_labels: np.ndarray, part: str) -> np.ndarray:
    membership = vertex_labels[faces] == part
    selected = membership.sum(axis=1) >= 2
    return faces[selected]


def closest_points_on_mesh(vertices: np.ndarray, faces: np.ndarray, query_points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    try:
        import open3d as o3d
    except Exception as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("open3d is required for closest-surface projection; install with pip install -e \".[gui]\"") from exc
    mesh = o3d.t.geometry.TriangleMesh()
    mesh.vertex["positions"] = o3d.core.Tensor(vertices.astype(np.float32))
    mesh.triangle["indices"] = o3d.core.Tensor(faces.astype(np.int32))
    scene = o3d.t.geometry.RaycastingScene()
    _mesh_id = scene.add_triangles(mesh)
    result = scene.compute_closest_points(o3d.core.Tensor(query_points.astype(np.float32)))
    points = result["points"].numpy().astype(np.float32)
    primitive_ids = result["primitive_ids"].numpy().astype(np.int32)
    return points, primitive_ids


def project_points_by_body_part(
    source_points: np.ndarray,
    target_vertices: np.ndarray,
    target_faces: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, object]]:
    source_labels = classify_source_body_parts(source_points)
    target_labels = classify_target_body_parts(target_vertices)
    projected = np.empty_like(source_points, dtype=np.float32)
    query_points = np.empty_like(source_points, dtype=np.float32)
    primitive_ids = np.full((source_points.shape[0],), -1, dtype=np.int32)
    stats: dict[str, object] = {
        "source_counts": {},
        "target_vertex_counts": {},
        "target_face_counts": {},
        "part_alignment": {},
    }
    for part in (
        "head",
        "torso",
        "left_upper_arm",
        "right_upper_arm",
        "left_lower_arm",
        "right_lower_arm",
        "left_hand",
        "right_hand",
        "left_upper_leg",
        "right_upper_leg",
        "left_lower_leg",
        "right_lower_leg",
    ):
        source_mask = source_labels == part
        target_mask = target_labels == part
        source_count = int(source_mask.sum())
        target_count = int(target_mask.sum())
        stats["source_counts"][part] = source_count
        stats["target_vertex_counts"][part] = target_count
        if source_count == 0:
            continue
        part_faces = faces_for_part(target_faces, target_labels, part)
        if part_faces.size == 0 or target_count == 0:
            part_faces = target_faces
            target_subset = target_vertices
            target_mode = "global_fallback"
        else:
            target_subset = target_vertices[target_mask]
            target_mode = "part_faces"
        stats["target_face_counts"][part] = int(part_faces.shape[0])
        if part in {"left_upper_arm", "right_upper_arm", "left_lower_arm", "right_lower_arm", "left_hand", "right_hand"}:
            aligned, info = align_points_to_target_pca_bbox(source_points[source_mask], target_subset, part)
        else:
            aligned, info = align_points_to_target_bbox_anisotropic(source_points[source_mask], target_subset)
        closest, part_primitive_ids = closest_points_on_mesh(target_vertices, part_faces, aligned)
        projected[source_mask] = closest
        query_points[source_mask] = aligned
        primitive_ids[source_mask] = part_primitive_ids
        distances = np.linalg.norm(closest - aligned, axis=1)
        stats["part_alignment"][part] = {
            "mode": target_mode,
            "query_count": source_count,
            "target_vertex_count": target_count,
            "target_face_count": int(part_faces.shape[0]),
            "bbox_alignment": info,
            "distance_mean": float(distances.mean()),
            "distance_p95": float(np.quantile(distances, 0.95)),
            "distance_max": float(distances.max()),
        }
    return projected, query_points, primitive_ids, stats


def write_vertex_csv(path: Path, vertex_ids: np.ndarray, points: np.ndarray, labels: np.ndarray) -> None:
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
        for row_index, vertex_id in enumerate(vertex_ids.tolist()):
            point = norm[row_index]
            writer.writerow(
                {
                    "vertex_id": int(vertex_id),
                    "part_hint": str(labels[row_index]),
                    "mds0_norm": f"{float(point[0]):.8f}",
                    "mds1_norm": f"{float(point[1]):.8f}",
                    "mds2_norm": f"{float(point[2]):.8f}",
                    "atlas_u_norm": f"{float(point[0]):.8f}",
                    "atlas_v_norm": f"{float(1.0 - point[1]):.8f}",
                }
            )


def project_alignment_to_mesh(
    source_alignment: Path,
    target_mesh: str,
    output_dir: Path,
    raw_dir: Path = Path("assets/raw/makehuman"),
    image_size: int = 768,
) -> dict[str, object]:
    target_path, target_meta = resolve_target_mesh(target_mesh, raw_dir)
    mesh_vertices, mesh_faces = load_mesh(target_path)
    vertex_ids, source_points, labels = load_source_points(source_alignment)
    projection_labels = classify_source_body_parts(source_points)
    projected_points, query_points, primitive_ids, alignment_info = project_points_by_body_part(
        source_points,
        mesh_vertices,
        mesh_faces,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_dir / "smpl_27554_to_surface_map.npz",
        vertex_id=vertex_ids,
        surface_points=projected_points,
        source_surface_points=source_points,
        body_part_aligned_query_points=query_points,
        target_face_ids=primitive_ids,
        methods=np.full((VERTEX_COUNT,), "body_part_closest_surface_makehuman", dtype="U40"),
        projection_region=projection_labels,
        part_hint=labels,
    )
    write_vertex_csv(output_dir / "vertex_template_points.csv", vertex_ids, projected_points, projection_labels)
    write_obj(output_dir / "surface_proxy.obj", mesh_vertices, mesh_faces)
    write_obj(output_dir / "smpl_27554_surface_points.obj", projected_points, None)

    tri_dir = output_dir / "tri_views"
    tri_views = []
    for view in ("front", "back", "left", "right"):
        tri_views.append(
            render_vertex_id_view(
                projected_points,
                tri_dir / f"{view}.png",
                tri_dir / f"{view}.vertex_id_map.npz",
                view=view,
                image_size=image_size,
                point_radius=max(2, image_size // 220),
            )
        )

    distances = np.linalg.norm(projected_points - query_points, axis=1)
    report = {
        "status": "demo_reference_smpl_id_projected",
        "message": "Projected local smpl_27554 IDs onto an open-source target mesh. Keep this output local unless your source alignment license allows redistribution.",
        "vertex_count": int(vertex_ids.size),
        "source_alignment": str(source_alignment),
        "target_mesh": str(target_path),
        "target_mesh_meta": target_meta,
        "projection_method": "body_part_bbox_align_then_open3d_closest_surface",
        "alignment_info": alignment_info,
        "distance_stats": {
            "mean": float(distances.mean()),
            "median": float(np.median(distances)),
            "p95": float(np.quantile(distances, 0.95)),
            "max": float(distances.max()),
        },
        "surface_proxy_obj": str(output_dir / "surface_proxy.obj"),
        "smpl_27554_surface_points_obj": str(output_dir / "smpl_27554_surface_points.obj"),
        "mapping_npz": str(output_dir / "smpl_27554_to_surface_map.npz"),
        "vertex_csv": str(output_dir / "vertex_template_points.csv"),
        "tri_views": tri_views,
        "view_specs": VIEW_SPECS,
        "asset_class": "local_smpl_projected_open_mesh",
        "license_note": (
            "The MakeHuman target mesh is CC0, but the projected vertex-id placement is derived from "
            "the local source alignment. Do not commit this generated alignment unless that source is redistributable."
        ),
    }
    write_json(output_dir / "tri_view_manifest.json", {"status": report["status"], "tri_views": tri_views})
    write_json(output_dir / "alignment_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project local smpl_27554 IDs onto a nicer open-source target mesh.")
    parser.add_argument("--source-alignment", type=Path, default=Path("assets/processed/alignment/smpl_27554_to_surface_map.npz"))
    parser.add_argument("--target-mesh", default="makehuman:female_generic", help="OBJ/PLY mesh path or makehuman:female_generic/male_generic/proxy741")
    parser.add_argument("--raw-dir", type=Path, default=Path("assets/raw/makehuman"))
    parser.add_argument("--output-dir", type=Path, default=Path("assets/demo_reference/generated/makehuman_smpl_projected"))
    parser.add_argument("--image-size", type=int, default=768)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    report = project_alignment_to_mesh(
        source_alignment=args.source_alignment,
        target_mesh=args.target_mesh,
        output_dir=args.output_dir,
        raw_dir=args.raw_dir,
        image_size=args.image_size,
    )
    print(f"{report['status']}: {report['message']}")
    print(f"Target mesh: {report['target_mesh']}")
    print(f"Report: {args.output_dir / 'alignment_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

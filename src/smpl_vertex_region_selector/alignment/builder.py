from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import numpy as np

from ..geometry.vertex_table import load_vertex_table
from ..schema import VERTEX_COUNT
from .renderer import VIEW_SPECS, render_vertex_id_view, write_obj
from .smpl_assets import (
    ensure_densepose_uv,
    ensure_smpl_subdiv,
    find_smpl_model,
    load_densepose_uv,
    load_smpl_subdiv,
    load_smpl_template,
    write_json,
)


def _densepose_atlas_uv(uv_payload: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    all_vertices = uv_payload["All_vertices"].astype(np.int64).reshape(-1) - 1
    faces = uv_payload["All_Faces"].astype(np.int64) - 1
    u = uv_payload["All_U_norm"].astype(np.float32).reshape(-1)
    v = uv_payload["All_V_norm"].astype(np.float32).reshape(-1)
    face_indices = uv_payload["All_FaceIndices"].astype(np.int64).reshape(-1)
    uv_atlas = np.full((u.shape[0], 2), np.nan, dtype=np.float32)
    cols, rows = 4, 6
    assigned: set[int] = set()
    for face_idx, tri in enumerate(faces):
        part = int(face_indices[face_idx])
        col = (part - 1) // rows
        row = (part - 1) % rows
        offset_u = col / cols
        offset_v = row / rows
        for vert_idx in tri:
            vert = int(vert_idx)
            if vert in assigned:
                continue
            uv_atlas[vert, 0] = u[vert] / cols + offset_u
            uv_atlas[vert, 1] = 1.0 - ((1.0 - v[vert]) / rows + offset_v)
            assigned.add(vert)
    return all_vertices, faces.astype(np.int32), uv_atlas, face_indices


def _barycentric(point: np.ndarray, tri: np.ndarray) -> Optional[np.ndarray]:
    a, b, c = tri
    v0 = b - a
    v1 = c - a
    v2 = point - a
    denom = float(v0[0] * v1[1] - v1[0] * v0[1])
    if abs(denom) < 1e-10:
        return None
    inv = 1.0 / denom
    u = float((v2[0] * v1[1] - v1[0] * v2[1]) * inv)
    v = float((v0[0] * v2[1] - v2[0] * v0[1]) * inv)
    w = 1.0 - u - v
    return np.asarray([w, u, v], dtype=np.float32)


def map_smpl_27554_to_surface(vertex_uv: np.ndarray, proxy_vertices: np.ndarray, proxy_faces: np.ndarray, proxy_uv: np.ndarray) -> dict[str, np.ndarray]:
    from scipy.spatial import cKDTree

    tri_uv = proxy_uv[proxy_faces]
    tri_valid = np.isfinite(tri_uv).all(axis=(1, 2))
    valid_face_indices = np.where(tri_valid)[0]
    centroids = tri_uv[tri_valid].mean(axis=1)
    centroid_tree = cKDTree(centroids)
    valid_uv_ids = np.where(np.isfinite(proxy_uv).all(axis=1))[0]
    uv_tree = cKDTree(proxy_uv[valid_uv_ids])

    points = np.zeros((vertex_uv.shape[0], 3), dtype=np.float32)
    proxy_ids = np.zeros((vertex_uv.shape[0],), dtype=np.int32)
    methods = np.empty((vertex_uv.shape[0],), dtype="U16")
    barycentric = np.zeros((vertex_uv.shape[0], 3), dtype=np.float32)
    face_ids = np.full((vertex_uv.shape[0],), -1, dtype=np.int32)

    for vertex_id, uv in enumerate(vertex_uv.astype(np.float32)):
        candidate_count = min(48, len(valid_face_indices))
        _, candidates = centroid_tree.query(uv, k=candidate_count)
        candidates = np.atleast_1d(candidates)
        found = False
        for local_idx in candidates:
            face_idx = int(valid_face_indices[int(local_idx)])
            weights = _barycentric(uv, tri_uv[face_idx])
            if weights is None:
                continue
            if np.all(weights >= -1e-4) and np.all(weights <= 1.0001):
                weights = np.clip(weights, 0.0, 1.0)
                weights /= max(float(weights.sum()), 1e-8)
                tri = proxy_faces[face_idx]
                points[vertex_id] = weights @ proxy_vertices[tri]
                proxy_ids[vertex_id] = int(tri[int(np.argmax(weights))])
                methods[vertex_id] = "barycentric"
                barycentric[vertex_id] = weights
                face_ids[vertex_id] = face_idx
                found = True
                break
        if not found:
            _, nearest_idx = uv_tree.query(uv)
            proxy_id = int(valid_uv_ids[int(nearest_idx)])
            points[vertex_id] = proxy_vertices[proxy_id]
            proxy_ids[vertex_id] = proxy_id
            methods[vertex_id] = "nearest_uv"
    return {
        "points": points,
        "proxy_vertex_ids": proxy_ids,
        "methods": methods,
        "barycentric": barycentric,
        "face_ids": face_ids,
    }


def build_smpl_subdiv_surface(payload: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    subdiv_vertices = payload["vertex"].T.astype(np.float32)
    subdiv_faces = payload["faces"].T.astype(np.int64) - 1
    transform = payload["index"].reshape(-1).astype(np.int64) - 1
    part_id = payload["part_id"].reshape(-1).astype(np.int32)
    u = payload["u"].reshape(-1).astype(np.float32)
    v = payload["v"].reshape(-1).astype(np.float32)
    if subdiv_vertices.shape[0] != transform.shape[0]:
        raise ValueError(
            f"SMPL subdiv vertex count {subdiv_vertices.shape[0]} does not match transform count {transform.shape[0]}"
        )
    if transform.min() < 0 or transform.max() >= VERTEX_COUNT:
        raise ValueError(f"SMPL subdiv transform ids must map to 0..{VERTEX_COUNT - 1}")

    counts = np.bincount(transform, minlength=VERTEX_COUNT).astype(np.float32)
    if int((counts == 0).sum()) > 0:
        missing = int((counts == 0).sum())
        raise ValueError(f"SMPL subdiv transform misses {missing} smpl_27554 ids")
    points = np.zeros((VERTEX_COUNT, 3), dtype=np.float32)
    uv_sum = np.zeros((VERTEX_COUNT, 2), dtype=np.float32)
    part_sum = np.zeros((VERTEX_COUNT,), dtype=np.float32)
    np.add.at(points, transform, subdiv_vertices)
    np.add.at(uv_sum[:, 0], transform, u)
    np.add.at(uv_sum[:, 1], transform, v)
    np.add.at(part_sum, transform, part_id.astype(np.float32))
    points /= counts[:, None]
    uv = uv_sum / counts[:, None]
    part = np.rint(part_sum / counts).astype(np.int32)

    faces = transform[subdiv_faces]
    keep = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
    faces = np.unique(np.sort(faces[keep], axis=1), axis=0).astype(np.int32)
    return {"points": points, "faces": faces, "uv": uv.astype(np.float32), "part_id": part}


def build_alignment_from_smpl_subdiv(
    vertex_csv: Path,
    output_dir: Path,
    raw_root: Path,
    download_smpl_subdiv: bool,
    image_size: int,
) -> Optional[dict[str, object]]:
    subdiv_path, transform_path = ensure_smpl_subdiv(raw_root, download=download_smpl_subdiv)
    if not subdiv_path or not transform_path:
        return None
    payload = load_smpl_subdiv(subdiv_path, transform_path)
    surface = build_smpl_subdiv_surface(payload)
    points = surface["points"]
    faces = surface["faces"]
    uv = surface["uv"]
    part_id = surface["part_id"]
    methods = np.full((VERTEX_COUNT,), "smpl_subdiv_transform", dtype="U24")
    np.savez_compressed(
        output_dir / "smpl_27554_to_surface_map.npz",
        vertex_id=np.arange(VERTEX_COUNT, dtype=np.int32),
        surface_points=points,
        proxy_vertex_ids=np.arange(VERTEX_COUNT, dtype=np.int32),
        methods=methods,
        barycentric=np.zeros((VERTEX_COUNT, 3), dtype=np.float32),
        face_ids=np.full((VERTEX_COUNT,), -1, dtype=np.int32),
        vertex_uv=uv,
        part_id=part_id,
    )
    write_obj(output_dir / "surface_proxy.obj", points, faces)
    write_obj(output_dir / "smpl_27554_surface_points.obj", points, None)
    tri_views = []
    tri_dir = output_dir / "tri_views"
    for view in ("front", "back", "left", "right"):
        tri_views.append(
            render_vertex_id_view(
                points,
                tri_dir / f"{view}.png",
                tri_dir / f"{view}.vertex_id_map.npz",
                view=view,
                image_size=image_size,
            )
        )
    report = {
        "status": "surface_proxy_aligned",
        "alignment_source": "densepose_smpl_subdiv_transform",
        "message": "Built smpl_27554 surface from official DensePose SMPL_subdiv transform.",
        "vertex_csv": str(vertex_csv),
        "output_dir": str(output_dir),
        "smpl_subdiv": str(subdiv_path),
        "smpl_subdiv_transform": str(transform_path),
        "surface_proxy_obj": str(output_dir / "surface_proxy.obj"),
        "smpl_27554_surface_points_obj": str(output_dir / "smpl_27554_surface_points.obj"),
        "mapping_npz": str(output_dir / "smpl_27554_to_surface_map.npz"),
        "vertex_count": VERTEX_COUNT,
        "proxy_vertex_count": VERTEX_COUNT,
        "proxy_face_count": int(faces.shape[0]),
        "method_counts": {"smpl_subdiv_transform": VERTEX_COUNT},
        "fallback_ratio": 0.0,
        "warnings": [],
        "tri_views": tri_views,
        "view_specs": VIEW_SPECS,
    }
    write_json(output_dir / "tri_view_manifest.json", {"status": report["status"], "tri_views": tri_views})
    write_json(output_dir / "alignment_report.json", report)
    return report


def build_alignment_assets(
    vertex_csv: Path,
    output_dir: Path,
    raw_root: Path,
    smpl_model: Optional[Path] = None,
    densepose_uv: Optional[Path] = None,
    download_densepose_uv: bool = True,
    download_smpl_subdiv: bool = True,
    image_size: int = 768,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "status": "missing_smpl",
        "vertex_csv": str(vertex_csv),
        "output_dir": str(output_dir),
        "message": "",
    }
    vertex_table = load_vertex_table(vertex_csv)
    subdiv_report = build_alignment_from_smpl_subdiv(
        vertex_csv=vertex_csv,
        output_dir=output_dir,
        raw_root=raw_root,
        download_smpl_subdiv=download_smpl_subdiv,
        image_size=image_size,
    )
    if subdiv_report is not None:
        return subdiv_report

    smpl_path = smpl_model or find_smpl_model(raw_root)
    if not smpl_path:
        report["message"] = (
            "No SMPL .pkl found. Place an official SMPL Python model under assets/raw/smpl/, "
            "run smpl-install-local-assets, or use the bundled assets/demo_reference/public demo for UI-only mode."
        )
        write_json(output_dir / "alignment_report.json", report)
        return report

    uv_path = densepose_uv or ensure_densepose_uv(raw_root, download=download_densepose_uv)
    if not uv_path:
        report["status"] = "missing_densepose_uv"
        report["message"] = "DensePose UV_Processed.mat was not found and was not downloaded."
        write_json(output_dir / "alignment_report.json", report)
        return report

    smpl_vertices, _smpl_faces, smpl_meta = load_smpl_template(smpl_path)
    uv_payload = load_densepose_uv(uv_path)
    all_vertices, proxy_faces, proxy_uv, face_indices = _densepose_atlas_uv(uv_payload)
    proxy_vertices = smpl_vertices[all_vertices]
    vertex_uv = vertex_table.points[:, :2].copy()
    if {"atlas_u_norm", "atlas_v_norm"}.issubset(set(vertex_table.columns)):
        import csv

        with vertex_csv.open("r", encoding="utf-8", newline="") as handle:
            rows = sorted(csv.DictReader(handle), key=lambda row: int(row["vertex_id"]))
        vertex_uv = np.asarray([[float(row["atlas_u_norm"]), float(row["atlas_v_norm"])] for row in rows], dtype=np.float32)

    mapping = map_smpl_27554_to_surface(vertex_uv, proxy_vertices, proxy_faces, proxy_uv)
    points = mapping["points"]
    np.savez_compressed(
        output_dir / "smpl_27554_to_surface_map.npz",
        vertex_id=np.arange(VERTEX_COUNT, dtype=np.int32),
        surface_points=points,
        proxy_vertex_ids=mapping["proxy_vertex_ids"],
        methods=mapping["methods"],
        barycentric=mapping["barycentric"],
        face_ids=mapping["face_ids"],
        vertex_uv=vertex_uv,
    )
    write_obj(output_dir / "surface_proxy.obj", proxy_vertices, proxy_faces)
    write_obj(output_dir / "smpl_27554_surface_points.obj", points, None)
    tri_views = []
    tri_dir = output_dir / "tri_views"
    for view in ("front", "back", "left", "right"):
        tri_views.append(
            render_vertex_id_view(
                points,
                tri_dir / f"{view}.png",
                tri_dir / f"{view}.vertex_id_map.npz",
                view=view,
                image_size=image_size,
            )
        )
    method_counts = {str(method): int((mapping["methods"] == method).sum()) for method in sorted(set(mapping["methods"].tolist()))}
    fallback_ratio = float(method_counts.get("nearest_uv", 0) / VERTEX_COUNT)
    warnings = []
    if fallback_ratio > 0.25:
        warnings.append(
            {
                "level": "warning",
                "message": (
                    "More than 25% of smpl_27554 vertices used nearest-UV fallback. "
                    "Use the tri-view/3D previews for manual quality checks before treating regions as authoritative."
                ),
            }
        )
    report.update(
        {
            "status": "surface_proxy_aligned",
            "message": "Built SMPL/DensePose surface proxy and smpl_27554 mapping assets.",
            "smpl": smpl_meta,
            "densepose_uv": str(uv_path),
            "surface_proxy_obj": str(output_dir / "surface_proxy.obj"),
            "smpl_27554_surface_points_obj": str(output_dir / "smpl_27554_surface_points.obj"),
            "mapping_npz": str(output_dir / "smpl_27554_to_surface_map.npz"),
            "vertex_count": VERTEX_COUNT,
            "proxy_vertex_count": int(proxy_vertices.shape[0]),
            "proxy_face_count": int(proxy_faces.shape[0]),
            "method_counts": method_counts,
            "fallback_ratio": fallback_ratio,
            "warnings": warnings,
            "tri_views": tri_views,
            "view_specs": VIEW_SPECS,
        }
    )
    write_json(output_dir / "tri_view_manifest.json", {"status": report["status"], "tri_views": tri_views})
    write_json(output_dir / "alignment_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build SMPL/DensePose surface alignment assets for smpl_27554.")
    parser.add_argument("--vertex-csv", type=Path, default=Path("assets/processed/vertex_template_points.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("assets/processed/alignment"))
    parser.add_argument("--raw-root", type=Path, default=Path("assets/raw"))
    parser.add_argument("--smpl-model", type=Path)
    parser.add_argument("--densepose-uv", type=Path)
    parser.add_argument("--no-download-densepose-uv", action="store_true")
    parser.add_argument("--no-download-smpl-subdiv", action="store_true")
    parser.add_argument("--image-size", type=int, default=768)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_alignment_assets(
        vertex_csv=args.vertex_csv,
        output_dir=args.output_dir,
        raw_root=args.raw_root,
        smpl_model=args.smpl_model,
        densepose_uv=args.densepose_uv,
        download_densepose_uv=not args.no_download_densepose_uv,
        download_smpl_subdiv=not args.no_download_smpl_subdiv,
        image_size=args.image_size,
    )
    print(f"{report['status']}: {report['message']}")
    print(f"Report: {args.output_dir / 'alignment_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

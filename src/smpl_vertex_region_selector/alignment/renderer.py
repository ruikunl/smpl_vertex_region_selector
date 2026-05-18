from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


VIEW_SPECS = {
    "front": {"axes": (0, 1), "depth": 2, "flip_x": False, "depth_sign": 1.0},
    "back": {"axes": (0, 1), "depth": 2, "flip_x": True, "depth_sign": -1.0},
    "left": {"axes": (2, 1), "depth": 0, "flip_x": False, "depth_sign": -1.0},
    "right": {"axes": (2, 1), "depth": 0, "flip_x": True, "depth_sign": 1.0},
}

# Approximate full-body vertical landmark fractions used only for visual guides.
# They follow common anthropometry landmarks: lower rib/costal margin, iliac
# crest, and the waist midpoint between those two landmarks.
COSTAL_MARGIN_Y = 0.39
WAIST_MIDPOINT_Y = 0.465
ILIAC_CREST_Y = 0.54


def project_points(points: np.ndarray, view: str, image_size: int = 768, margin: float = 0.08) -> tuple[np.ndarray, np.ndarray]:
    spec = VIEW_SPECS[view]
    xy = points[:, list(spec["axes"])].astype(np.float32)
    if spec["flip_x"]:
        xy[:, 0] *= -1.0
    depth = points[:, int(spec["depth"])].astype(np.float32) * float(spec["depth_sign"])
    mins = xy.min(axis=0)
    maxs = xy.max(axis=0)
    center = (mins + maxs) * 0.5
    span = max(float((maxs - mins).max()), 1e-5)
    scale = image_size * (1.0 - 2.0 * margin) / span
    projected = np.empty((points.shape[0], 2), dtype=np.float32)
    projected[:, 0] = image_size * 0.5 + (xy[:, 0] - center[0]) * scale
    projected[:, 1] = image_size * 0.5 - (xy[:, 1] - center[1]) * scale
    return projected, depth


def _projected_bbox(projected: np.ndarray, image_size: int) -> tuple[float, float, float, float]:
    in_frame = (
        (projected[:, 0] >= 0)
        & (projected[:, 0] < image_size)
        & (projected[:, 1] >= 0)
        & (projected[:, 1] < image_size)
    )
    pts = projected[in_frame] if in_frame.any() else projected
    return float(pts[:, 0].min()), float(pts[:, 1].min()), float(pts[:, 0].max()), float(pts[:, 1].max())


def _skin_color(depth_value: float, dmin: float, dmax: float, view: str) -> tuple[int, int, int, int]:
    norm = (depth_value - dmin) / max(dmax - dmin, 1e-6)
    shade = 0.86 + 0.18 * norm
    if view == "back":
        base = np.asarray((216, 174, 142), dtype=np.float32)
    elif view in {"left", "right"}:
        base = np.asarray((226, 184, 150), dtype=np.float32)
    else:
        base = np.asarray((234, 190, 154), dtype=np.float32)
    rgb = np.clip(base * shade, 0, 255).astype(np.uint8)
    return int(rgb[0]), int(rgb[1]), int(rgb[2]), 214


def _draw_body_guides(image: Image.Image, projected: np.ndarray, view: str, image_size: int) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    x0, y0, x1, y1 = _projected_bbox(projected, image_size)
    width = max(x1 - x0, 1.0)
    height = max(y1 - y0, 1.0)
    cx = (x0 + x1) * 0.5
    line = (112, 70, 55, 116)
    soft = (112, 70, 55, 72)
    if view in {"front", "back"}:
        shoulder_y = y0 + height * 0.27
        rib_y = y0 + height * COSTAL_MARGIN_Y
        waist_y = y0 + height * WAIST_MIDPOINT_Y
        pelvis_y = y0 + height * ILIAC_CREST_Y
        rib_w = width * 0.18
        draw.line((cx, shoulder_y, cx, pelvis_y), fill=soft, width=1)
        draw.arc((cx - rib_w, rib_y - height * 0.045, cx + rib_w, rib_y + height * 0.11), 198, 342, fill=line, width=2)
        draw.arc((cx - rib_w * 0.82, rib_y + height * 0.045, cx + rib_w * 0.82, rib_y + height * 0.16), 205, 335, fill=soft, width=1)
        if view == "front":
            navel_r = max(2.0, width * 0.009)
            draw.ellipse((cx - navel_r, waist_y - navel_r, cx + navel_r, waist_y + navel_r), fill=(95, 55, 45, 130))
        else:
            draw.line((cx, y0 + height * 0.20, cx, y0 + height * 0.58), fill=line, width=2)
        draw.arc((cx - width * 0.16, pelvis_y - height * 0.035, cx + width * 0.16, pelvis_y + height * 0.08), 195, 345, fill=soft, width=2)
    else:
        rib_y = y0 + height * COSTAL_MARGIN_Y
        abdomen_y = y0 + height * WAIST_MIDPOINT_Y
        pelvis_y = y0 + height * ILIAC_CREST_Y
        side_x = x0 + width * (0.54 if view == "left" else 0.46)
        draw.arc((side_x - width * 0.10, rib_y - height * 0.05, side_x + width * 0.12, rib_y + height * 0.13), 110, 260, fill=line, width=2)
        draw.arc((side_x - width * 0.08, abdomen_y - height * 0.04, side_x + width * 0.10, abdomen_y + height * 0.10), 95, 250, fill=soft, width=1)
        draw.line((side_x, y0 + height * 0.30, side_x, pelvis_y), fill=soft, width=1)


def _render_reference_body(projected: np.ndarray, depth: np.ndarray, view: str, image_size: int, point_radius: int) -> Image.Image:
    image = Image.new("RGBA", (image_size, image_size), (246, 247, 246, 255))
    surface = Image.new("RGBA", (image_size, image_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(surface, "RGBA")
    visual_radius = max(point_radius * 3, image_size // 42)
    dmin = float(depth.min())
    dmax = float(depth.max())
    for vertex_id in np.argsort(depth):
        x, y = projected[int(vertex_id)]
        xi, yi = int(round(float(x))), int(round(float(y)))
        if xi < -visual_radius or yi < -visual_radius or xi >= image_size + visual_radius or yi >= image_size + visual_radius:
            continue
        fill = _skin_color(float(depth[int(vertex_id)]), dmin, dmax, view)
        draw.ellipse((xi - visual_radius, yi - visual_radius, xi + visual_radius, yi + visual_radius), fill=fill)
    surface = surface.filter(ImageFilter.GaussianBlur(radius=max(1, visual_radius // 4)))
    image.alpha_composite(surface)
    grain = Image.new("RGBA", (image_size, image_size), (0, 0, 0, 0))
    grain_draw = ImageDraw.Draw(grain, "RGBA")
    grain_radius = max(1, point_radius // 2)
    for vertex_id in np.argsort(depth)[::3]:
        x, y = projected[int(vertex_id)]
        xi, yi = int(round(float(x))), int(round(float(y)))
        if 0 <= xi < image_size and 0 <= yi < image_size:
            grain_draw.ellipse(
                (xi - grain_radius, yi - grain_radius, xi + grain_radius, yi + grain_radius),
                fill=(70, 115, 140, 34),
            )
    image.alpha_composite(grain)
    _draw_body_guides(image, projected, view, image_size)
    return image.convert("RGB")


def render_vertex_id_view(
    points: np.ndarray,
    output_png: Path,
    output_npz: Path,
    view: str,
    image_size: int = 768,
    point_radius: int = 3,
) -> dict[str, object]:
    projected, depth = project_points(points, view, image_size=image_size)
    map_radius = max(point_radius, image_size // 95)
    id_map = np.full((image_size, image_size), -1, dtype=np.int32)
    depth_map = np.full((image_size, image_size), -np.inf, dtype=np.float32)
    image = _render_reference_body(projected, depth, view, image_size, map_radius)
    order = np.argsort(depth)
    for vertex_id in order:
        x, y = projected[vertex_id]
        xi, yi = int(round(float(x))), int(round(float(y)))
        if xi < -map_radius or yi < -map_radius or xi >= image_size + map_radius or yi >= image_size + map_radius:
            continue
        z = float(depth[vertex_id])
        x0 = max(0, xi - map_radius)
        x1 = min(image_size, xi + map_radius + 1)
        y0 = max(0, yi - map_radius)
        y1 = min(image_size, yi + map_radius + 1)
        yy, xx = np.ogrid[y0:y1, x0:x1]
        disk = (xx - xi) ** 2 + (yy - yi) ** 2 <= map_radius**2
        visible = disk & (z >= depth_map[y0:y1, x0:x1])
        depth_map[y0:y1, x0:x1][visible] = z
        id_map[y0:y1, x0:x1][visible] = int(vertex_id)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_png, quality=95)
    np.savez_compressed(output_npz, vertex_id_map=id_map, depth_map=depth_map, projected=projected)
    valid = int((id_map >= 0).sum())
    return {"view": view, "image": str(output_png), "vertex_id_map": str(output_npz), "valid_pixels": valid}


def write_obj(path: Path, vertices: np.ndarray, faces: np.ndarray | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for x, y, z in vertices:
            handle.write(f"v {float(x):.8f} {float(y):.8f} {float(z):.8f}\n")
        if faces is not None:
            for a, b, c in faces:
                handle.write(f"f {int(a) + 1} {int(b) + 1} {int(c) + 1}\n")

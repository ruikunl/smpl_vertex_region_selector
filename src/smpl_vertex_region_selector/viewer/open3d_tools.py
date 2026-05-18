from __future__ import annotations

import numpy as np

from ..geometry.mesh_loader import MeshAsset
from ..geometry.vertex_table import VertexTable
from ..schema import REGION_COLORS
from ..selection.region_state import RegionState


def _require_open3d():
    try:
        import open3d as o3d
    except Exception as exc:
        raise RuntimeError("Open3D is not installed. Install with: pip install -e '.[gui]'") from exc
    return o3d


def make_open3d_point_cloud(vertex_table: VertexTable, state: RegionState | None = None):
    o3d = _require_open3d()
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(vertex_table.points.astype(np.float64))
    colors = np.tile(np.asarray((0.08, 0.82, 1.0), dtype=np.float64), (vertex_table.vertex_count, 1))
    if state:
        for region, ids in state.regions.items():
            if region in state.hidden_regions or not ids:
                continue
            rgb = np.asarray(REGION_COLORS.get(region, (255, 255, 255)), dtype=np.float64) / 255.0
            colors[np.asarray(ids, dtype=np.int32)] = rgb
        if state.selected_ids:
            colors[np.asarray(sorted(state.selected_ids), dtype=np.int32)] = (1.0, 0.95, 0.1)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    return pcd


def make_open3d_mesh(mesh_asset: MeshAsset):
    if mesh_asset.vertices is None or mesh_asset.faces is None or mesh_asset.vertices.size == 0:
        return None
    o3d = _require_open3d()
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(mesh_asset.vertices.astype(np.float64))
    if mesh_asset.faces.size:
        mesh.triangles = o3d.utility.Vector3iVector(mesh_asset.faces.astype(np.int32))
    mesh.compute_vertex_normals()
    mesh.paint_uniform_color((0.76, 0.78, 0.82))
    return mesh


def make_open3d_wireframe(mesh_asset: MeshAsset):
    if mesh_asset.vertices is None or mesh_asset.faces is None or mesh_asset.vertices.size == 0 or mesh_asset.faces.size == 0:
        return None
    o3d = _require_open3d()
    mesh = make_open3d_mesh(mesh_asset)
    if mesh is None:
        return None
    line_set = o3d.geometry.LineSet.create_from_triangle_mesh(mesh)
    line_set.paint_uniform_color((0.54, 0.58, 0.64))
    return line_set


def open_preview(vertex_table: VertexTable, state: RegionState, mesh_asset: MeshAsset | None = None) -> None:
    o3d = _require_open3d()
    geometries = []
    if mesh_asset:
        wireframe = make_open3d_wireframe(mesh_asset)
        if wireframe is not None:
            geometries.append(wireframe)
    geometries.append(make_open3d_point_cloud(vertex_table, state))
    visualizer = o3d.visualization.Visualizer()
    visualizer.create_window(window_name="smpl_27554 Open3D Preview", width=1280, height=900)
    for geometry in geometries:
        visualizer.add_geometry(geometry)
    options = visualizer.get_render_option()
    options.background_color = np.asarray((0.02, 0.025, 0.03), dtype=np.float64)
    options.point_size = 5.5
    options.line_width = 1.0
    options.mesh_show_back_face = True
    visualizer.run()
    visualizer.destroy_window()

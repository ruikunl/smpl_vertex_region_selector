from __future__ import annotations

import math
from typing import Callable, Optional

import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QPolygon, QWheelEvent
from PySide6.QtWidgets import QWidget

from ..geometry.mesh_loader import MeshAsset
from ..geometry.vertex_table import VertexTable
from ..schema import REGION_COLORS
from ..selection.region_state import RegionState


class PointCloudCanvas(QWidget):
    """A lightweight cross-platform point cloud selector for smpl_27554 ids."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(720, 520)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.vertex_table: Optional[VertexTable] = None
        self.mesh_asset: Optional[MeshAsset] = None
        self.state: Optional[RegionState] = None
        self.selection_changed: Optional[Callable[[list[int]], None]] = None
        self.hover_changed: Optional[Callable[[Optional[int]], None]] = None
        self.zoom = 1.0
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.pan = np.zeros(2, dtype=np.float32)
        self.interaction_mode = "rotate"
        self.selection_shape = "box"
        self._projected: Optional[np.ndarray] = None
        self._depth: Optional[np.ndarray] = None
        self._mesh_projected: Optional[np.ndarray] = None
        self._mesh_depth: Optional[np.ndarray] = None
        self._drag_start: Optional[QPoint] = None
        self._drag_current: Optional[QPoint] = None
        self._drag_action: Optional[str] = None
        self._polygon_points: list[QPoint] = []
        self._polygon_current: Optional[QPoint] = None

    def set_vertex_table(self, vertex_table: VertexTable) -> None:
        self.vertex_table = vertex_table
        self._projected = None
        self.update()

    def set_mesh_asset(self, mesh_asset: Optional[MeshAsset]) -> None:
        self.mesh_asset = mesh_asset
        self._mesh_projected = None
        self.update()

    def set_region_state(self, state: RegionState) -> None:
        self.state = state
        self.update()

    def reset_view(self) -> None:
        self.zoom = 1.0
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.pan[:] = 0
        self._projected = None
        self._mesh_projected = None
        self.update()

    def set_interaction_mode(self, mode: str) -> None:
        if mode == "move":
            mode = "pan"
        if mode not in {"select", "rotate", "pan"}:
            raise ValueError(f"unknown interaction mode {mode!r}")
        self.interaction_mode = mode
        self._drag_start = None
        self._drag_current = None
        self._drag_action = None
        self.update()

    def _interaction_mode_label(self) -> str:
        return {"select": "Select", "rotate": "Rotate", "pan": "Move"}.get(self.interaction_mode, self.interaction_mode)

    def set_selection_shape(self, shape: str) -> None:
        if shape not in {"box", "polygon"}:
            raise ValueError(f"unknown selection shape {shape!r}")
        self.selection_shape = shape
        self._cancel_polygon()
        self.update()

    def set_view(self, view: str) -> None:
        presets = {
            "front": (0.0, 0.0),
            "back": (0.0, math.pi),
            "left": (0.0, -math.pi / 2.0),
            "right": (0.0, math.pi / 2.0),
            "top": (-math.pi / 2.0, 0.0),
            "bottom": (math.pi / 2.0, 0.0),
        }
        if view not in presets:
            raise ValueError(f"unknown view {view!r}")
        self.rot_x, self.rot_y = presets[view]
        self._projected = None
        self._mesh_projected = None
        self.update()

    def rotate_view(self, dx: float, dy: float) -> None:
        self.rot_y += dx
        self.rot_x += dy
        self._projected = None
        self._mesh_projected = None
        self.update()

    def _rotation(self) -> np.ndarray:
        cx, sx = math.cos(self.rot_x), math.sin(self.rot_x)
        cy, sy = math.cos(self.rot_y), math.sin(self.rot_y)
        rx = np.asarray([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float32)
        ry = np.asarray([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
        return ry @ rx

    def _project_points(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if points.size == 0:
            return np.zeros((0, 2), dtype=np.float32), np.zeros((0,), dtype=np.float32)
        rotated = points @ self._rotation().T
        xy = rotated[:, [0, 1]]
        depth = rotated[:, 2]
        span = max(float(np.ptp(xy[:, 0])), float(np.ptp(xy[:, 1])), 1e-5)
        scale = min(self.width(), self.height()) * 0.42 * self.zoom / span
        projected = np.empty((points.shape[0], 2), dtype=np.float32)
        projected[:, 0] = self.width() * 0.5 + self.pan[0] + xy[:, 0] * scale
        projected[:, 1] = self.height() * 0.5 + self.pan[1] - xy[:, 1] * scale
        return projected, depth

    def _ensure_projection(self) -> None:
        if self.vertex_table is None:
            self._projected = None
            self._depth = None
            return
        if self._projected is None:
            self._projected, self._depth = self._project_points(self.vertex_table.points)
        if (
            self.mesh_asset is not None
            and self.mesh_asset.vertices is not None
            and self.mesh_asset.vertices.size
            and self._mesh_projected is None
        ):
            self._mesh_projected, self._mesh_depth = self._project_points(self.mesh_asset.vertices)

    def _colors(self) -> np.ndarray:
        assert self.vertex_table is not None
        colors = np.full((self.vertex_table.vertex_count, 3), (70, 210, 255), dtype=np.uint8)
        if self.state:
            for region, ids in self.state.regions.items():
                if region in self.state.hidden_regions or not ids:
                    continue
                colors[np.asarray(ids, dtype=np.int32)] = REGION_COLORS.get(region, (240, 240, 240))
            if self.state.selected_ids:
                colors[np.asarray(sorted(self.state.selected_ids), dtype=np.int32)] = (255, 242, 20)
        return colors

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(22, 24, 27))
        if self.vertex_table is None:
            painter.setPen(QColor(210, 210, 210))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Load vertex_template_points.csv to begin")
            return
        self._ensure_projection()
        assert self._projected is not None and self._depth is not None
        if (
            self.mesh_asset is not None
            and self.mesh_asset.faces is not None
            and self.mesh_asset.faces.size
            and self._mesh_projected is not None
            and self._mesh_depth is not None
        ):
            faces = self.mesh_asset.faces
            face_depth = self._mesh_depth[faces].mean(axis=1)
            painter.setPen(QPen(QColor(115, 120, 128, 110), 1))
            painter.setBrush(QColor(170, 176, 186, 34))
            for face_idx in np.argsort(face_depth):
                tri = faces[int(face_idx)]
                pts = [QPoint(int(self._mesh_projected[v, 0]), int(self._mesh_projected[v, 1])) for v in tri]
                painter.drawPolygon(QPolygon(pts))
        order = np.argsort(self._depth)
        colors = self._colors()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        for idx in order:
            x, y = self._projected[idx]
            if x < -4 or y < -4 or x > self.width() + 4 or y > self.height() + 4:
                continue
            r, g, b = colors[idx]
            painter.setPen(QPen(QColor(int(r), int(g), int(b)), 4))
            painter.drawPoint(int(x), int(y))
        if self._drag_start and self._drag_current and self._drag_action == "select":
            painter.setPen(QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine))
            painter.drawRect(QRect(self._drag_start, self._drag_current).normalized())
        if self._polygon_points:
            painter.setPen(QPen(QColor(255, 245, 20), 2, Qt.PenStyle.DashLine))
            preview_points = list(self._polygon_points)
            if self._polygon_current is not None:
                preview_points.append(self._polygon_current)
            if len(preview_points) > 1:
                painter.drawPolyline(QPolygon(preview_points))
            for point in self._polygon_points:
                painter.setPen(QPen(QColor(255, 245, 20), 6))
                painter.drawPoint(point)
        painter.setPen(QColor(190, 190, 190))
        painter.drawText(
            12,
            72,
            (
                f"coords={self.vertex_table.coordinate_mode} | mode={self._interaction_mode_label()} | "
                f"shape={self.selection_shape} | zoom={self.zoom:.2f} | "
                "left-drag rotate, middle/right move, Shift/Select to pick"
            ),
        )

    def resizeEvent(self, event) -> None:
        self._projected = None
        self._mesh_projected = None
        super().resizeEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom = min(8.0, max(0.15, self.zoom * factor))
        self._projected = None
        self._mesh_projected = None
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus()
        pos = event.position().toPoint()
        self._drag_start = event.position().toPoint()
        self._drag_current = self._drag_start
        shift_select = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        polygon_select = (self.interaction_mode == "select" or shift_select) and self.selection_shape == "polygon"
        if polygon_select and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            self._drag_current = None
            self._drag_action = None
            self._polygon_points.append(pos)
            self._polygon_current = pos
            self.update()
            return
        if event.button() in {Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton} or self.interaction_mode == "pan":
            self._drag_action = "pan"
        elif self.interaction_mode == "select" or shift_select:
            self._drag_action = "select"
        else:
            self._drag_action = "rotate"

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._polygon_points and self.selection_shape == "polygon":
            self._polygon_current = pos
            self.update()
        if self._drag_start:
            if self._drag_action == "rotate":
                delta = pos - self._drag_current
                self.rotate_view(delta.x() * 0.01, delta.y() * 0.01)
            elif self._drag_action == "pan":
                delta = pos - self._drag_current
                self.pan += np.asarray([delta.x(), delta.y()], dtype=np.float32)
                self._projected = None
                self._mesh_projected = None
            self._drag_current = pos
            self.update()
        hover = self._nearest_vertex(pos, max_distance=12.0)
        if self.hover_changed:
            self.hover_changed(hover)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.vertex_table is None or self._drag_start is None:
            return
        pos = event.position().toPoint()
        if self._drag_action in {"pan", "rotate"}:
            self._drag_start = None
            self._drag_current = None
            self._drag_action = None
            return
        if self._drag_action != "select":
            self._drag_start = None
            self._drag_current = None
            self._drag_action = None
            return
        distance = math.hypot(pos.x() - self._drag_start.x(), pos.y() - self._drag_start.y())
        if distance < 4:
            vertex_id = self._nearest_vertex(pos, max_distance=18.0)
            ids = [] if vertex_id is None else [vertex_id]
        else:
            ids = self._ids_in_rect(QRect(self._drag_start, pos).normalized())
        self._drag_start = None
        self._drag_current = None
        self._drag_action = None
        if self.state:
            self.state.set_selection(ids)
        if self.selection_changed:
            self.selection_changed(ids)
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self.selection_shape == "polygon" and self._polygon_points:
            self._finish_polygon()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter} and self._polygon_points:
            self._finish_polygon()
            return
        if event.key() == Qt.Key.Key_Escape and self._polygon_points:
            self._cancel_polygon()
            return
        super().keyPressEvent(event)

    def _nearest_vertex(self, pos: QPoint, max_distance: float) -> Optional[int]:
        self._ensure_projection()
        if self._projected is None or self._projected.size == 0:
            return None
        target = np.asarray([pos.x(), pos.y()], dtype=np.float32)
        distances = np.linalg.norm(self._projected - target, axis=1)
        idx = int(np.argmin(distances))
        if float(distances[idx]) <= max_distance:
            if self.vertex_table is not None:
                return int(self.vertex_table.vertex_ids[idx])
            return idx
        return None

    def _ids_in_rect(self, rect: QRect) -> list[int]:
        self._ensure_projection()
        if self._projected is None:
            return []
        x0, x1 = rect.left(), rect.right()
        y0, y1 = rect.top(), rect.bottom()
        mask = (
            (self._projected[:, 0] >= x0)
            & (self._projected[:, 0] <= x1)
            & (self._projected[:, 1] >= y0)
            & (self._projected[:, 1] <= y1)
        )
        indices = np.where(mask)[0]
        if self.vertex_table is None:
            return indices.astype(int).tolist()
        return self.vertex_table.vertex_ids[indices].astype(int).tolist()

    def _ids_in_polygon(self, points: list[QPoint]) -> list[int]:
        self._ensure_projection()
        if self._projected is None or len(points) < 3:
            return []
        polygon = QPolygon(points)
        ids: list[int] = []
        for idx, (x, y) in enumerate(self._projected):
            if polygon.containsPoint(QPoint(int(x), int(y)), Qt.FillRule.OddEvenFill):
                if self.vertex_table is not None:
                    ids.append(int(self.vertex_table.vertex_ids[idx]))
                else:
                    ids.append(int(idx))
        return ids

    def _finish_polygon(self) -> None:
        ids = self._ids_in_polygon(self._polygon_points)
        self._cancel_polygon()
        if self.state:
            self.state.set_selection(ids)
        if self.selection_changed:
            self.selection_changed(ids)
        self.update()

    def _cancel_polygon(self) -> None:
        self._polygon_points = []
        self._polygon_current = None

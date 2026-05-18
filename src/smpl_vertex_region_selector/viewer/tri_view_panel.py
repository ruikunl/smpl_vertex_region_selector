from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap, QPolygon, QWheelEvent
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from ..alignment.assets import AlignmentAssets, TriViewAsset
from ..schema import REGION_COLORS
from ..selection.region_state import RegionState


def pil_to_qimage(image: Image.Image) -> QImage:
    rgb = image.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    return QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888).copy()


class TriViewCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.asset: Optional[TriViewAsset] = None
        self.state: Optional[RegionState] = None
        self.selection_changed: Optional[Callable[[list[int]], None]] = None
        self.show_valid_vertex_overlay = False
        self.selection_shape = "box"
        self.zoom = 1.0
        self.fit_mode = True
        self.pan = QPoint(0, 0)
        self._drag_start: Optional[QPoint] = None
        self._drag_current: Optional[QPoint] = None
        self._drag_action: Optional[str] = None
        self._polygon_points: list[QPoint] = []
        self._polygon_current: Optional[QPoint] = None
        self._pixmap: Optional[QPixmap] = None
        self._view_rect = QRect()

    def set_asset(self, asset: TriViewAsset, show_valid_vertex_overlay: bool = False) -> None:
        self.asset = asset
        self.show_valid_vertex_overlay = show_valid_vertex_overlay
        self._pixmap = None
        self.fit_view()
        self.update()

    def set_region_state(self, state: RegionState) -> None:
        self.state = state
        self._pixmap = None
        self.update()

    def refresh_overlay(self) -> None:
        self._pixmap = None
        self.update()

    def set_selection_shape(self, shape: str) -> None:
        if shape not in {"box", "polygon"}:
            raise ValueError(f"unknown selection shape {shape!r}")
        self.selection_shape = shape
        self._cancel_polygon()
        self.update()

    def fit_view(self) -> None:
        self.fit_mode = True
        self.zoom = 1.0
        self.pan = QPoint(0, 0)
        self.update()

    def actual_size(self) -> None:
        self.fit_mode = False
        self.zoom = 1.0
        self.pan = QPoint(0, 0)
        self.update()

    def _render_pixmap(self) -> Optional[QPixmap]:
        if self.asset is None:
            return None
        base = np.asarray(self.asset.image.convert("RGB"), dtype=np.float32).copy()
        if self.show_valid_vertex_overlay:
            valid_mask = self.asset.vertex_id_map >= 0
            if valid_mask.any():
                base[valid_mask] = base[valid_mask] * 0.76 + np.asarray((20, 215, 255), dtype=np.float32) * 0.24
        if self.state:
            alpha = 0.58
            id_map = self.asset.vertex_id_map
            for region, ids in self.state.regions.items():
                if region in self.state.hidden_regions or not ids:
                    continue
                mask = np.isin(id_map, np.asarray(ids, dtype=np.int32))
                if not mask.any():
                    continue
                color = np.asarray(REGION_COLORS.get(region, (255, 255, 255)), dtype=np.float32)
                base[mask] = base[mask] * (1.0 - alpha) + color * alpha
            if self.state.selected_ids:
                mask = np.isin(id_map, np.asarray(sorted(self.state.selected_ids), dtype=np.int32))
                base[mask] = base[mask] * 0.25 + np.asarray((255, 245, 20), dtype=np.float32) * 0.75
        image = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
        return QPixmap.fromImage(pil_to_qimage(image))

    def _image_rect(self) -> QRect:
        if not self.asset:
            return QRect()
        iw, ih = self.asset.image.size
        if iw <= 0 or ih <= 0:
            return QRect()
        base_scale = min(self.width() / iw, self.height() / ih) if self.fit_mode else 1.0
        scale = max(0.05, base_scale * self.zoom)
        w, h = int(iw * scale), int(ih * scale)
        return QRect((self.width() - w) // 2 + self.pan.x(), (self.height() - h) // 2 + self.pan.y(), w, h)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30, 32, 36))
        if self.asset is None:
            painter.setPen(QColor(210, 210, 210))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No alignment tri-view assets")
            return
        if self._pixmap is None:
            self._pixmap = self._render_pixmap()
        self._view_rect = self._image_rect()
        if self._pixmap:
            painter.drawPixmap(self._view_rect, self._pixmap)
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
        painter.setPen(QColor(235, 235, 235))
        painter.drawText(10, 20, f"{self.asset.name}  zoom={self.zoom:.2f}  shape={self.selection_shape}")
        if not self.show_valid_vertex_overlay:
            painter.setPen(QColor(80, 80, 80))
            painter.drawText(10, self.height() - 12, "Template guide lines: ribs / pelvis / navel, not CSE output")

    def _widget_to_image(self, point: QPoint, clamp: bool = False) -> tuple[int, int] | None:
        if self.asset is None:
            return None
        rect = self._image_rect()
        if not rect.contains(point) and not clamp:
            return None
        iw, ih = self.asset.image.size
        x = int((point.x() - rect.left()) / max(1, rect.width()) * iw)
        y = int((point.y() - rect.top()) / max(1, rect.height()) * ih)
        if clamp:
            x = min(iw - 1, max(0, x))
            y = min(ih - 1, max(0, y))
        if x < 0 or y < 0 or x >= iw or y >= ih:
            return None
        return x, y

    def _ids_from_widget_rect(self, rect: QRect) -> list[int]:
        if self.asset is None:
            return []
        intersected = rect.intersected(self._image_rect())
        if intersected.isEmpty():
            return []
        p0 = self._widget_to_image(intersected.topLeft(), clamp=True)
        p1 = self._widget_to_image(intersected.bottomRight(), clamp=True)
        if p0 is None or p1 is None:
            return []
        x0, x1 = sorted((p0[0], p1[0]))
        y0, y1 = sorted((p0[1], p1[1]))
        crop = self.asset.vertex_id_map[y0 : y1 + 1, x0 : x1 + 1]
        ids = np.unique(crop[crop >= 0]).astype(int).tolist()
        return ids

    def _ids_from_widget_polygon(self, points: list[QPoint]) -> list[int]:
        if self.asset is None or len(points) < 3:
            return []
        image_points = [self._widget_to_image(point, clamp=True) for point in points]
        image_points = [point for point in image_points if point is not None]
        if len(image_points) < 3:
            return []
        iw, ih = self.asset.image.size
        mask = Image.new("L", (iw, ih), 0)
        ImageDraw.Draw(mask).polygon(image_points, fill=255)
        mask_array = np.asarray(mask, dtype=bool)
        selected = self.asset.vertex_id_map[mask_array & (self.asset.vertex_id_map >= 0)]
        return np.unique(selected).astype(int).tolist()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus()
        pos = event.position().toPoint()
        if event.button() in {Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton}:
            self._drag_action = "pan"
            self._drag_start = pos
            self._drag_current = pos
            return
        if self.selection_shape == "polygon" and event.button() == Qt.MouseButton.LeftButton:
            self._polygon_points.append(pos)
            self._polygon_current = pos
            self.update()
            return
        self._drag_action = "select"
        self._drag_start = pos
        self._drag_current = self._drag_start

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._polygon_points and self.selection_shape == "polygon":
            self._polygon_current = pos
            self.update()
        if self._drag_start:
            if self._drag_action == "pan":
                delta = pos - self._drag_current
                self.pan = self.pan + delta
            self._drag_current = pos
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is None:
            return
        if self._drag_action == "pan":
            self._drag_start = None
            self._drag_current = None
            self._drag_action = None
            return
        if self._drag_action != "select":
            self._drag_start = None
            self._drag_current = None
            self._drag_action = None
            return
        end = event.position().toPoint()
        rect = QRect(self._drag_start, end).normalized()
        if rect.width() < 4 and rect.height() < 4:
            mapped = self._widget_to_image(end)
            if mapped is None or self.asset is None:
                ids = []
            else:
                vertex_id = int(self.asset.vertex_id_map[mapped[1], mapped[0]])
                ids = [] if vertex_id < 0 else [vertex_id]
        else:
            ids = self._ids_from_widget_rect(rect)
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

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom = min(20.0, max(0.05, self.zoom * factor))
        self.update()

    def _finish_polygon(self) -> None:
        ids = self._ids_from_widget_polygon(self._polygon_points)
        self._cancel_polygon()
        if self.state:
            self.state.set_selection(ids)
        if self.selection_changed:
            self.selection_changed(ids)
        self.update()

    def _cancel_polygon(self) -> None:
        self._polygon_points = []
        self._polygon_current = None


class TriViewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tabs = QTabWidget()
        self.canvases: dict[str, TriViewCanvas] = {}
        self.status_label = QLabel("Alignment: not loaded")
        self.selection_shape = "box"
        self.cse_canvas: Optional[TriViewCanvas] = None
        self.cse_asset: Optional[TriViewAsset] = None
        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.tabs, stretch=1)

    def set_region_state(self, state: RegionState) -> None:
        for canvas in self.canvases.values():
            canvas.set_region_state(state)

    def set_selection_callback(self, callback: Callable[[list[int]], None]) -> None:
        for canvas in self.canvases.values():
            canvas.selection_changed = callback

    def set_selection_shape(self, shape: str) -> None:
        self.selection_shape = shape
        for canvas in self.canvases.values():
            canvas.set_selection_shape(shape)

    def load_assets(self, assets: AlignmentAssets, state: RegionState, callback: Callable[[list[int]], None]) -> None:
        self.tabs.clear()
        self.canvases.clear()
        self.cse_canvas = None
        self.cse_asset = None
        suffix = ""
        if assets.fallback_ratio is not None:
            suffix = f" | UV fallback: {assets.fallback_ratio:.1%}"
            if assets.warnings:
                suffix += " (check preview)"
        self.status_label.setText(f"Alignment: {assets.status}{suffix}")
        for name in ("front", "back", "left", "right"):
            asset = assets.tri_views.get(name)
            if not asset:
                continue
            canvas = TriViewCanvas()
            canvas.set_asset(asset)
            canvas.set_region_state(state)
            canvas.set_selection_shape(self.selection_shape)
            canvas.selection_changed = callback
            self.canvases[name] = canvas
            self.tabs.addTab(canvas, name.capitalize())

    def load_cse_vertex_map(
        self,
        vertex_map: np.ndarray,
        map_path: Path,
        state: RegionState,
        callback: Callable[[list[int]], None],
    ) -> None:
        height, width = vertex_map.shape
        image = Image.new("RGB", (width, height), (28, 30, 34))
        asset = TriViewAsset(
            name=f"CSE: {map_path.name}",
            image_path=map_path,
            vertex_id_map_path=map_path,
            image=image,
            vertex_id_map=np.asarray(vertex_map, dtype=np.int32),
        )
        self.cse_asset = asset
        canvas = self.cse_canvas or TriViewCanvas()
        canvas.set_asset(asset, show_valid_vertex_overlay=True)
        canvas.set_region_state(state)
        canvas.set_selection_shape(self.selection_shape)
        canvas.selection_changed = callback
        if self.cse_canvas is None:
            self.cse_canvas = canvas
            self.canvases["cse"] = canvas
            self.tabs.addTab(canvas, "CSE/Image")
        else:
            index = self.tabs.indexOf(canvas)
            if index >= 0:
                self.tabs.setTabText(index, "CSE/Image")
        self.tabs.setCurrentWidget(canvas)
        valid = int(np.count_nonzero(vertex_map >= 0))
        unique = int(np.unique(vertex_map[vertex_map >= 0]).size)
        self.status_label.setText(f"CSE/Image: {width}x{height} | valid pixels: {valid} | unique vertices: {unique}")

    def load_cse_image(self, image_path: Path, resize_to_map: bool = False) -> None:
        if self.cse_asset is None or self.cse_canvas is None:
            raise ValueError("load a CSE vertex map before loading its image")
        image = Image.open(image_path).convert("RGB")
        map_height, map_width = self.cse_asset.vertex_id_map.shape
        if image.size != (map_width, map_height):
            if not resize_to_map:
                raise ValueError(
                    f"image size {image.size} does not match vertex map size {(map_width, map_height)}"
                )
            image = image.resize((map_width, map_height), Image.Resampling.BILINEAR)
        self.cse_asset = TriViewAsset(
            name=f"CSE/Image: {image_path.name}",
            image_path=image_path,
            vertex_id_map_path=self.cse_asset.vertex_id_map_path,
            image=image,
            vertex_id_map=self.cse_asset.vertex_id_map,
        )
        self.cse_canvas.set_asset(self.cse_asset, show_valid_vertex_overlay=True)
        self.tabs.setCurrentWidget(self.cse_canvas)
        height, width = self.cse_asset.vertex_id_map.shape
        self.status_label.setText(f"CSE/Image: {width}x{height} | image: {image_path.name}")

    def refresh_overlay(self) -> None:
        for canvas in self.canvases.values():
            canvas.refresh_overlay()

    def fit_current_view(self) -> None:
        canvas = self.tabs.currentWidget()
        if isinstance(canvas, TriViewCanvas):
            canvas.fit_view()

    def actual_size_current_view(self) -> None:
        canvas = self.tabs.currentWidget()
        if isinstance(canvas, TriViewCanvas):
            canvas.actual_size()

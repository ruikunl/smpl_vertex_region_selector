from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSplitter,
    QToolButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..exports.region_export import export_region_bundle
from ..alignment.assets import AlignmentAssets, load_alignment_assets
from ..geometry.mesh_loader import MeshAsset, load_mesh_asset
from ..geometry.vertex_table import VertexTable, load_vertex_table
from ..region_io import load_region_file
from ..schema import REGION_COLORS
from ..selection.region_state import RegionState
from ..selection.vertex_id_io import load_cse_vertex_map, load_mask_or_points, load_vertex_ids, parse_vertex_id_text
from ..viewer.point_cloud_canvas import PointCloudCanvas
from ..viewer.tri_view_panel import TriViewPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("smpl_27554 Vertex Region Selector")
        self.resize(1320, 860)
        self.vertex_table: Optional[VertexTable] = None
        self.mesh_asset: MeshAsset = load_mesh_asset(None)
        self.alignment_assets: Optional[AlignmentAssets] = None
        self.state = RegionState()
        self.selection_source = "none"
        self.selection_shape = "box"
        self.interaction_mode_buttons: dict[str, QToolButton] = {}

        self.asset_label = QLabel("Point cloud: not loaded")
        self.mesh_label = QLabel(self.mesh_asset.message)
        self.selection_label = QLabel("Selected: 0")
        self.selection_source_label = QLabel("Selection source: none")
        self.hover_label = QLabel("Hover vertex: -")
        self.vertex_id_input = QLineEdit()
        self.vertex_id_input.setPlaceholderText("12, 55, 100-130")
        self.vertex_id_input.returnPressed.connect(self.apply_vertex_id_input)
        self.region_list = QListWidget()
        self.canvas = PointCloudCanvas()
        self.canvas.set_region_state(self.state)
        self.canvas.selection_changed = self.on_canvas_selection
        self.canvas.hover_changed = self.on_canvas_hover
        self.canvas.installEventFilter(self)
        self._build_canvas_mode_overlay()
        self.tri_view_panel = TriViewPanel()
        self.tri_view_panel.set_region_state(self.state)

        self._build_ui()
        self._build_toolbar()
        self.refresh_region_list()
        self.try_load_default_assets()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)
        toolbar.setObjectName("main_toolbar")
        toolbar.setStyleSheet(
            """
            QToolBar QToolButton:checked {
                background: #2563eb;
                color: white;
                border: 1px solid #1d4ed8;
                border-radius: 4px;
                padding: 4px 8px;
            }
            """
        )
        for title, items in [
            (
                "File / Assets",
                [
                    ("Load Vertex CSV", self.load_vertex_csv),
                    ("Load Alignment", self.load_alignment),
                    ("Load Mesh", self.load_mesh),
                    ("Import Regions", self.import_region_map),
                    ("Import Vertex IDs", self.import_vertex_ids),
                    ("Export Bundle", self.export_bundle),
                ],
            ),
            (
                "CSE Inspector",
                [
                    ("Load CSE Map", self.load_cse_map),
                    ("Load CSE Image", self.load_cse_image),
                    ("Load Mask/Points", self.load_mask_points),
                    ("Open3D Preview", self.open_open3d_preview),
                ],
            ),
            (
                "View / Layout",
                [
                    ("3D Only", self.layout_3d_only),
                    ("2D Only", self.layout_2d_only),
                    ("Split", self.layout_split),
                    ("Reset Layout", self.reset_layout),
                    ("2D Fit", self.tri_view_panel.fit_current_view),
                    ("2D 100%", self.tri_view_panel.actual_size_current_view),
                    ("Reset 3D View", self.canvas.reset_view),
                ],
            ),
            (
                "3D Camera",
                [
                    ("Front", lambda: self.canvas.set_view("front")),
                    ("Back", lambda: self.canvas.set_view("back")),
                    ("Left", lambda: self.canvas.set_view("left")),
                    ("Right", lambda: self.canvas.set_view("right")),
                    ("Top", lambda: self.canvas.set_view("top")),
                    ("Bottom", lambda: self.canvas.set_view("bottom")),
                ],
            ),
        ]:
            toolbar.addWidget(self._toolbar_menu_button(title, items))

    def _build_canvas_mode_overlay(self) -> None:
        self.mode_overlay = QFrame(self.canvas)
        self.mode_overlay.setObjectName("interaction_mode_overlay")
        self.mode_overlay.setStyleSheet(
            """
            QFrame#interaction_mode_overlay {
                background: rgba(22, 24, 27, 210);
                border: 1px solid rgba(255, 255, 255, 48);
                border-radius: 7px;
            }
            QToolButton {
                color: #dbeafe;
                background: transparent;
                border: 0;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: 600;
            }
            QToolButton:hover {
                background: rgba(255, 255, 255, 28);
            }
            QToolButton:checked {
                background: #2563eb;
                color: white;
            }
            """
        )
        layout = QHBoxLayout(self.mode_overlay)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        self.interaction_mode_group = QButtonGroup(self)
        self.interaction_mode_group.setExclusive(True)
        for text, mode, tooltip in [
            ("Select", "select", "Select vertices in the 3D view"),
            ("Rotate", "rotate", "Rotate the 3D view"),
            ("Move", "pan", "Move the 3D view without rotating it"),
        ]:
            button = QToolButton(self.mode_overlay)
            button.setText(text)
            button.setCheckable(True)
            button.setToolTip(tooltip)
            button.setStatusTip(tooltip)
            button.clicked.connect(lambda _checked=False, name=mode: self.set_interaction_mode(name))
            self.interaction_mode_group.addButton(button)
            self.interaction_mode_buttons[mode] = button
            layout.addWidget(button)
        self.interaction_mode_buttons["rotate"].setChecked(True)
        self.mode_overlay.adjustSize()
        self._position_canvas_mode_overlay()

    def _position_canvas_mode_overlay(self) -> None:
        if not hasattr(self, "mode_overlay"):
            return
        self.mode_overlay.adjustSize()
        margin = 12
        self.mode_overlay.move(margin, margin)
        self.mode_overlay.raise_()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.canvas and event.type() in {QEvent.Type.Resize, QEvent.Type.Show}:
            self._position_canvas_mode_overlay()
        return super().eventFilter(watched, event)

    def _toolbar_menu_button(self, title: str, items: list[tuple[str, object]]) -> QToolButton:
        menu = QMenu(title, self)
        for text, callback in items:
            action = QAction(text, self)
            action.triggered.connect(lambda _checked=False, cb=callback: cb())
            menu.addAction(action)
        button = QToolButton()
        button.setText(title)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(menu)
        button.setObjectName(f"menu_{title.lower().replace(' ', '_').replace('/', '').replace('__', '_')}")
        return button

    def _build_ui(self) -> None:
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(self._left_panel())
        self.center_splitter = QSplitter(Qt.Orientation.Vertical)
        self.center_splitter.addWidget(self.canvas)
        self.center_splitter.addWidget(self.tri_view_panel)
        self.center_splitter.setStretchFactor(0, 3)
        self.center_splitter.setStretchFactor(1, 2)
        self.main_splitter.addWidget(self.center_splitter)
        self.main_splitter.addWidget(self._right_panel())
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        self.setCentralWidget(self.main_splitter)
        self.statusBar().showMessage("Ready")

    def _left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(self._section_label("Asset Status"))
        layout.addWidget(self.asset_label)
        layout.addWidget(self.mesh_label)
        layout.addWidget(self.selection_label)
        layout.addWidget(self.selection_source_label)
        layout.addWidget(self.hover_label)
        layout.addSpacing(12)
        layout.addWidget(self._section_label("Selection Input"))
        layout.addWidget(self.vertex_id_input)
        apply_button = QPushButton("Apply typed IDs")
        apply_button.clicked.connect(self.apply_vertex_id_input)
        layout.addWidget(apply_button)
        import_button = QPushButton("Import vertex IDs")
        import_button.clicked.connect(self.import_vertex_ids)
        layout.addWidget(import_button)
        layout.addSpacing(12)
        layout.addWidget(self._section_label("Assets"))
        for label, callback in [
            ("Load vertex_template_points.csv", self.load_vertex_csv),
            ("Load alignment assets", self.load_alignment),
            ("Load body mesh", self.load_mesh),
            ("Import region map", self.import_region_map),
            ("Open Open3D preview", self.open_open3d_preview),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            layout.addWidget(button)
        layout.addSpacing(12)
        layout.addWidget(self._section_label("CSE Inspector"))
        for label, callback in [
            ("Load CSE vertex map", self.load_cse_map),
            ("Load image for CSE map", self.load_cse_image),
            ("Load mask/points for CSE map", self.load_mask_points),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            layout.addWidget(button)
        layout.addStretch(1)
        panel.setMinimumWidth(270)
        return panel

    def _right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(self._section_label("Region List"))
        layout.addWidget(self.region_list, stretch=1)
        self.region_list.currentItemChanged.connect(self.on_region_changed)
        layout.addWidget(self._section_label("Selection Shape"))
        shape_row = QWidget()
        shape_layout = QHBoxLayout(shape_row)
        shape_layout.setContentsMargins(0, 0, 0, 0)
        self.box_radio = QRadioButton("Box")
        self.box_radio.setObjectName("selection_shape_box")
        self.box_radio.setChecked(True)
        self.box_radio.toggled.connect(lambda checked: checked and self.set_selection_shape("box"))
        self.polygon_radio = QRadioButton("Polygon")
        self.polygon_radio.setObjectName("selection_shape_polygon")
        self.polygon_radio.toggled.connect(lambda checked: checked and self.set_selection_shape("polygon"))
        shape_layout.addWidget(self.box_radio)
        shape_layout.addWidget(self.polygon_radio)
        layout.addWidget(shape_row)
        layout.addWidget(self._section_label("Region Editing"))

        button_rows = [
            [("New", self.new_region), ("Rename", self.rename_region)],
            [("Add Selected", self.add_selected), ("Remove Selected", self.remove_selected)],
            [("Clear", self.clear_current), ("Undo", self.undo)],
            [("Redo", self.redo), ("Export", self.export_bundle)],
        ]
        for row in button_rows:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            for label, callback in row:
                button = QPushButton(label)
                button.clicked.connect(callback)
                row_layout.addWidget(button)
            layout.addWidget(row_widget)
        panel.setMinimumWidth(310)
        return panel

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600; margin-top: 4px;")
        return label

    def default_alignment_roots(self) -> list[Path]:
        return [
            Path("assets/processed/alignment"),
            Path("assets/demo_reference/public"),
            Path("assets/demo_reference/generated"),
        ]

    def try_load_default_assets(self) -> None:
        default_csv = Path("assets/processed/vertex_template_points.csv")
        if default_csv.exists():
            self.set_vertex_table(default_csv)
        processed_alignment, public_demo_alignment, demo_alignment = self.default_alignment_roots()
        for root, label in [
            (processed_alignment, "Alignment"),
            (public_demo_alignment, "Public demo assets"),
        ]:
            if root.exists():
                try:
                    self.set_alignment(root)
                    return
                except Exception as exc:
                    self.statusBar().showMessage(f"{label} not loaded: {exc}")
        if not demo_alignment.exists():
            try:
                from ..demo_assets import build_demo_assets

                build_demo_assets(demo_alignment, image_size=512)
            except Exception as exc:
                self.statusBar().showMessage(f"Demo assets not generated: {exc}")
                return
        try:
            self.set_alignment(demo_alignment)
        except Exception as exc:
            self.statusBar().showMessage(f"Demo assets not loaded: {exc}")

    def set_vertex_table(self, path: Path) -> None:
        self.vertex_table = load_vertex_table(path)
        self.canvas.set_vertex_table(self.vertex_table)
        self.asset_label.setText(
            f"Point cloud: {path.name}\n"
            f"vertices: {self.vertex_table.vertex_count}\n"
            f"mode: {self.vertex_table.coordinate_mode}"
        )
        self.statusBar().showMessage(f"Loaded {path}")

    def set_alignment(self, root: Path) -> None:
        assets = load_alignment_assets(root)
        self.alignment_assets = assets
        if self.vertex_table is None:
            self.vertex_table = VertexTable(
                vertex_ids=assets.vertex_ids,
                points=assets.surface_points,
                columns=("vertex_id", "surface_x", "surface_y", "surface_z"),
                source_path=assets.mapping_path,
                coordinate_mode=assets.status,
            )
        self.vertex_table = VertexTable(
            vertex_ids=self.vertex_table.vertex_ids,
            points=assets.surface_points,
            columns=self.vertex_table.columns,
            source_path=self.vertex_table.source_path,
            coordinate_mode="surface_proxy",
        )
        self.canvas.set_vertex_table(self.vertex_table)
        surface_proxy = root / "surface_proxy.obj"
        if surface_proxy.exists():
            self.mesh_asset = load_mesh_asset(surface_proxy)
            self.canvas.set_mesh_asset(self.mesh_asset)
            self.mesh_label.setText(f"Mesh: surface_proxy\n{self.mesh_asset.message}")
        self.tri_view_panel.load_assets(assets, self.state, self.on_canvas_selection)
        fallback_line = ""
        if assets.fallback_ratio is not None:
            fallback_line = f"\nUV fallback: {assets.fallback_ratio:.1%}"
        self.asset_label.setText(
            f"Point cloud: {self.vertex_table.source_path.name}\n"
            f"vertices: {self.vertex_table.vertex_count}\n"
            f"mode: {self.vertex_table.coordinate_mode}\n"
            f"alignment: {assets.status}"
            f"{fallback_line}"
        )
        self.statusBar().showMessage(f"Loaded alignment assets from {root}")

    def load_alignment(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Load alignment asset directory", str(Path("assets/processed/alignment")))
        if not path:
            return
        try:
            self.set_alignment(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Could not load alignment", str(exc))

    def load_vertex_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load vertex_template_points.csv",
            str(Path.cwd()),
            "CSV files (*.csv);;All files (*.*)",
        )
        if not path:
            return
        try:
            self.set_vertex_table(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Could not load vertex CSV", str(exc))

    def load_mesh(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load body mesh",
            str(Path.cwd()),
            "Mesh files (*.obj *.ply *.glb *.gltf *.fbx);;All files (*.*)",
        )
        if not path:
            return
        self.mesh_asset = load_mesh_asset(Path(path))
        self.canvas.set_mesh_asset(self.mesh_asset)
        self.mesh_label.setText(f"Mesh: {self.mesh_asset.status}\n{self.mesh_asset.message}")
        if self.mesh_asset.status == "load_error":
            QMessageBox.warning(self, "Mesh load warning", self.mesh_asset.message)

    def import_region_map(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import region map",
            str(Path.cwd()),
            "Region files (*.json *.csv);;All files (*.*)",
        )
        if not path:
            return
        try:
            self.state = RegionState.from_region_map(load_region_file(Path(path)))
            self.canvas.set_region_state(self.state)
            self.tri_view_panel.set_region_state(self.state)
            self.tri_view_panel.set_selection_callback(self.on_canvas_selection)
            self.tri_view_panel.set_selection_shape(self.selection_shape)
            self.refresh_region_list()
            self.statusBar().showMessage(f"Imported {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Could not import regions", str(exc))

    def refresh_region_list(self) -> None:
        current = self.state.current_region
        self.region_list.blockSignals(True)
        self.region_list.clear()
        for region, ids in self.state.regions.items():
            item = QListWidgetItem(f"{region}  ({len(ids)})")
            item.setData(Qt.ItemDataRole.UserRole, region)
            rgb = REGION_COLORS.get(region, (220, 220, 220))
            item.setForeground(QColor(*rgb))
            self.region_list.addItem(item)
            if region == current:
                self.region_list.setCurrentItem(item)
        self.region_list.blockSignals(False)
        self.canvas.update()
        self.tri_view_panel.refresh_overlay()

    def on_region_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        if current is None:
            return
        self.state.set_current_region(current.data(Qt.ItemDataRole.UserRole))
        self.canvas.update()

    def on_canvas_selection(self, vertex_ids: list[int]) -> None:
        self.selection_source = "interactive"
        self._refresh_selection_status(len(vertex_ids))
        self.canvas.update()
        self.tri_view_panel.refresh_overlay()

    def _refresh_selection_status(self, count: Optional[int] = None) -> None:
        if count is None:
            count = len(self.state.selected_ids)
        self.selection_label.setText(f"Selected: {count}")
        self.selection_source_label.setText(f"Selection source: {self.selection_source}")
        ids = sorted(self.state.selected_ids)
        if count == 1 and ids:
            self.statusBar().showMessage(f"Selected vertex {ids[0]}")
        else:
            self.statusBar().showMessage(f"Selected {count} vertices")

    def apply_selection(self, vertex_ids: list[int], source: str) -> None:
        self.state.set_selection(vertex_ids)
        self.selection_source = source
        self._refresh_selection_status()
        self.canvas.update()
        self.tri_view_panel.refresh_overlay()

    def apply_vertex_id_input(self) -> None:
        try:
            vertex_ids = parse_vertex_id_text(self.vertex_id_input.text())
            self.apply_selection(vertex_ids, "typed vertex ids")
        except Exception as exc:
            QMessageBox.warning(self, "Invalid vertex ids", str(exc))

    def import_vertex_ids(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import vertex ids",
            str(Path.cwd()),
            "Vertex id files (*.txt *.csv *.json);;All files (*.*)",
        )
        if not path:
            return
        try:
            vertex_ids = load_vertex_ids(Path(path))
            self.apply_selection(vertex_ids, f"import: {Path(path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "Could not import vertex ids", str(exc))

    def load_cse_map(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load CSE vertex map",
            str(Path.cwd()),
            "Vertex map arrays (*.npz *.npy);;All files (*.*)",
        )
        if not path:
            return
        try:
            self.load_cse_map_path(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Could not load CSE vertex map", str(exc))

    def load_cse_map_path(self, path: Path) -> None:
        cse_map = load_cse_vertex_map(path)
        self.tri_view_panel.load_cse_vertex_map(cse_map.vertex_map, cse_map.path, self.state, self.on_canvas_selection)
        self.apply_selection(cse_map.valid_vertex_ids, f"CSE map all valid: {path.name}")
        self.selection_source_label.setText(
            f"Selection source: {self.selection_source}\n"
            f"valid pixels: {cse_map.valid_pixel_count}\n"
            f"unique ids: {cse_map.unique_vertex_count}"
        )
        self.statusBar().showMessage(f"Loaded CSE vertex map {path.name}; selected {cse_map.unique_vertex_count} vertices")

    def load_cse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load image for CSE map",
            str(Path.cwd()),
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;All files (*.*)",
        )
        if not path:
            return
        try:
            self.tri_view_panel.load_cse_image(Path(path), resize_to_map=False)
            self.statusBar().showMessage(f"Loaded CSE image {Path(path).name}")
        except ValueError as exc:
            if "does not match vertex map size" not in str(exc):
                QMessageBox.warning(self, "Could not load CSE image", str(exc))
                return
            answer = QMessageBox.question(
                self,
                "Resize display image?",
                f"{exc}\n\nResize only the displayed copy to match the vertex map?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                try:
                    self.tri_view_panel.load_cse_image(Path(path), resize_to_map=True)
                    self.statusBar().showMessage(f"Loaded resized display copy for {Path(path).name}")
                except Exception as resize_exc:
                    QMessageBox.warning(self, "Could not load CSE image", str(resize_exc))
        except Exception as exc:
            QMessageBox.warning(self, "Could not load CSE image", str(exc))

    def load_mask_points(self) -> None:
        if self.tri_view_panel.cse_asset is None:
            QMessageBox.information(self, "No CSE map", "Load a CSE vertex map first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load mask or pixel points",
            str(Path.cwd()),
            "Masks / points (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.npy *.npz *.csv);;All files (*.*)",
        )
        if not path:
            return
        try:
            ids = load_mask_or_points(Path(path), self.tri_view_panel.cse_asset.vertex_id_map)
            if not ids:
                QMessageBox.warning(self, "No overlap", "The mask/points did not overlap valid CSE vertex ids.")
                return
            self.apply_selection(ids, f"mask/points: {Path(path).name}")
        except Exception as exc:
            QMessageBox.warning(self, "Could not load mask/points", str(exc))

    def on_canvas_hover(self, vertex_id: Optional[int]) -> None:
        if vertex_id is None:
            self.hover_label.setText("Hover vertex: -")
        else:
            self.hover_label.setText(f"Hover vertex: {vertex_id}")

    def new_region(self) -> None:
        name, ok = QInputDialog.getText(self, "New region", "Region name:")
        if ok and name.strip():
            try:
                self.state.create_region(name)
                self.refresh_region_list()
            except Exception as exc:
                QMessageBox.warning(self, "Region error", str(exc))

    def rename_region(self) -> None:
        old = self.state.current_region
        name, ok = QInputDialog.getText(self, "Rename region", "Region name:", text=old)
        if ok and name.strip():
            try:
                self.state.rename_region(old, name)
                self.refresh_region_list()
            except Exception as exc:
                QMessageBox.warning(self, "Region error", str(exc))

    def add_selected(self) -> None:
        try:
            self.state.add_to_current(self.state.selected_ids)
            self.refresh_region_list()
        except Exception as exc:
            QMessageBox.warning(self, "Selection error", str(exc))

    def remove_selected(self) -> None:
        try:
            self.state.remove_from_current(self.state.selected_ids)
            self.refresh_region_list()
        except Exception as exc:
            QMessageBox.warning(self, "Selection error", str(exc))

    def clear_current(self) -> None:
        if QMessageBox.question(self, "Clear region", f"Clear {self.state.current_region}?") == QMessageBox.StandardButton.Yes:
            self.state.clear_current()
            self.refresh_region_list()

    def undo(self) -> None:
        if self.state.undo():
            self.refresh_region_list()

    def redo(self) -> None:
        if self.state.redo():
            self.refresh_region_list()

    def export_bundle(self) -> None:
        output = QFileDialog.getExistingDirectory(self, "Export region bundle", str(Path("outputs/manual_regions")))
        if not output:
            return
        try:
            paths = export_region_bundle(Path(output), self.state, status="confirmed")
            QMessageBox.information(self, "Exported", f"Wrote:\n{paths['json']}\n{paths['csv']}\n{paths['txt_dir']}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def open_open3d_preview(self) -> None:
        if self.vertex_table is None:
            QMessageBox.information(self, "No point cloud", "Load vertex_template_points.csv first.")
            return
        try:
            from ..viewer.open3d_tools import open_preview

            open_preview(self.vertex_table, self.state, self.mesh_asset)
        except Exception as exc:
            QMessageBox.warning(self, "Open3D preview unavailable", str(exc))

    def set_interaction_mode(self, mode: str) -> None:
        if mode == "move":
            mode = "pan"
        self.canvas.set_interaction_mode(mode)
        button = self.interaction_mode_buttons.get(mode)
        if button is not None and not button.isChecked():
            button.setChecked(True)
        label = {"select": "Select", "rotate": "Rotate", "pan": "Move"}.get(mode, mode)
        self.statusBar().showMessage(f"Interaction mode: {label}")

    def set_selection_shape(self, shape: str) -> None:
        self.selection_shape = shape
        self.canvas.set_selection_shape(shape)
        self.tri_view_panel.set_selection_shape(shape)
        if hasattr(self, "box_radio"):
            self.box_radio.blockSignals(True)
            self.polygon_radio.blockSignals(True)
            self.box_radio.setChecked(shape == "box")
            self.polygon_radio.setChecked(shape == "polygon")
            self.box_radio.blockSignals(False)
            self.polygon_radio.blockSignals(False)
        self.statusBar().showMessage(f"Selection shape: {shape}")

    def layout_3d_only(self) -> None:
        self.canvas.show()
        self.tri_view_panel.hide()
        self.statusBar().showMessage("Layout: 3D only")

    def layout_2d_only(self) -> None:
        self.canvas.hide()
        self.tri_view_panel.show()
        self.statusBar().showMessage("Layout: 2D only")

    def layout_split(self) -> None:
        self.canvas.show()
        self.tri_view_panel.show()
        self.center_splitter.setSizes([3, 2])
        self.statusBar().showMessage("Layout: split")

    def reset_layout(self) -> None:
        self.layout_split()
        self.main_splitter.setSizes([270, 900, 310])
        self.center_splitter.setSizes([520, 340])
        self.canvas.reset_view()
        self.tri_view_panel.fit_current_view()
        self.statusBar().showMessage("Layout reset")


def run_app(smoke_test: bool = False, alignment_dir: Path | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    if alignment_dir is not None:
        window.set_alignment(alignment_dir)
    if smoke_test:
        window.close()
        return 0
    window.show()
    return int(app.exec())

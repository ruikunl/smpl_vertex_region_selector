import os
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


class GuiSmokeTest(unittest.TestCase):
    def test_default_asset_order_prefers_processed_then_public_then_generated(self):
        try:
            from PySide6.QtWidgets import QApplication
            from smpl_vertex_region_selector.app.main_window import MainWindow
        except Exception as exc:
            self.skipTest(f"GUI dependencies unavailable: {exc}")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        expected = [
            Path("assets/processed/alignment"),
            Path("assets/demo_reference/public"),
            Path("assets/demo_reference/generated"),
        ]
        self.assertEqual(window.default_alignment_roots(), expected)
        window.close()

    def test_fresh_clone_style_loads_public_demo_assets(self):
        try:
            from PySide6.QtWidgets import QApplication
            from smpl_vertex_region_selector.app.main_window import MainWindow
        except Exception as exc:
            self.skipTest(f"GUI dependencies unavailable: {exc}")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        root = Path(__file__).resolve().parents[1]
        public = root / "assets" / "demo_reference" / "public"
        if not public.exists():
            self.skipTest("public demo assets are not present")
        app = QApplication.instance() or QApplication([])
        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            target = tmp_root / "assets" / "demo_reference" / "public"
            target.parent.mkdir(parents=True)
            shutil.copytree(public, target)
            os.chdir(tmp_root)
            try:
                window = MainWindow()
                self.assertIsNotNone(window.alignment_assets)
                self.assertEqual(window.alignment_assets.status, "makehuman_cc0_smpl_projected_demo")
                self.assertEqual(window.alignment_assets.root, Path("assets/demo_reference/public"))
                window.close()
            finally:
                os.chdir(old_cwd)

    def test_run_app_accepts_alignment_dir_for_smoke(self):
        try:
            from smpl_vertex_region_selector.app.main_window import run_app
        except Exception as exc:
            self.skipTest(f"GUI dependencies unavailable: {exc}")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        root = Path(__file__).resolve().parents[1]
        public = root / "assets" / "demo_reference" / "public"
        if not public.exists():
            self.skipTest("public demo assets are not present")
        self.assertEqual(run_app(smoke_test=True, alignment_dir=public), 0)

    def test_main_window_import_and_constructs_offscreen_when_pyside_is_available(self):
        try:
            from PySide6.QtWidgets import QApplication
            from smpl_vertex_region_selector.app.main_window import MainWindow
        except Exception as exc:
            self.skipTest(f"GUI dependencies unavailable: {exc}")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        self.assertEqual(window.state.current_region, "abdomen_front")
        window.close()

    def test_canvas_front_view_uses_y_as_vertical_axis(self):
        try:
            from PySide6.QtWidgets import QApplication
            from smpl_vertex_region_selector.geometry.vertex_table import VertexTable
            from smpl_vertex_region_selector.viewer.point_cloud_canvas import PointCloudCanvas
        except Exception as exc:
            self.skipTest(f"GUI dependencies unavailable: {exc}")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication([])
        canvas = PointCloudCanvas()
        canvas.resize(400, 400)
        points = np.asarray([[0, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
        table = VertexTable(
            vertex_ids=np.asarray([0, 1, 2], dtype=np.int32),
            points=points,
            columns=("vertex_id",),
            source_path=Path(__file__),
            coordinate_mode="test",
        )
        canvas.set_vertex_table(table)
        canvas.set_view("front")
        projected, _depth = canvas._project_points(points)
        self.assertLess(projected[1, 1], projected[0, 1])
        canvas.set_view("top")
        projected_top, _depth_top = canvas._project_points(points)
        self.assertNotAlmostEqual(float(projected_top[2, 1]), float(projected_top[0, 1]))
        canvas.set_view("bottom")
        self.assertEqual(canvas.interaction_mode, "rotate")
        canvas.close()

    def test_layout_controls_and_selection_shape_do_not_crash(self):
        try:
            from PySide6.QtWidgets import QApplication
            from smpl_vertex_region_selector.app.main_window import MainWindow
        except Exception as exc:
            self.skipTest(f"GUI dependencies unavailable: {exc}")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        self.assertTrue(window.interaction_mode_buttons["rotate"].isChecked())
        self.assertIs(window.mode_overlay.parent(), window.canvas)
        window.layout_3d_only()
        self.assertFalse(window.tri_view_panel.isVisible())
        window.layout_2d_only()
        self.assertFalse(window.canvas.isVisible())
        window.layout_split()
        window.set_interaction_mode("pan")
        self.assertEqual(window.interaction_mode_buttons["pan"].text(), "Move")
        self.assertTrue(window.interaction_mode_buttons["pan"].isChecked())
        self.assertFalse(window.interaction_mode_buttons["rotate"].isChecked())
        window.canvas.resize(800, 500)
        window._position_canvas_mode_overlay()
        self.assertEqual(window.mode_overlay.x(), 12)
        self.assertEqual(window.mode_overlay.y(), 12)
        window.set_selection_shape("polygon")
        self.assertEqual(window.canvas.selection_shape, "polygon")
        self.assertTrue(window.polygon_radio.isChecked())
        window.set_selection_shape("box")
        self.assertTrue(window.box_radio.isChecked())
        window.reset_layout()
        window.close()

    def test_cse_panel_loads_vertex_map_and_syncs_selection(self):
        try:
            from PySide6.QtWidgets import QApplication
            from smpl_vertex_region_selector.app.main_window import MainWindow
        except Exception as exc:
            self.skipTest(f"GUI dependencies unavailable: {exc}")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            cse_path = Path(tmp) / "sample.vertex_map.npz"
            np.savez_compressed(cse_path, vertex_id=np.asarray([[-1, 42], [43, 42]], dtype=np.int32))
            window = MainWindow()
            window.load_cse_map_path(cse_path)
            self.assertIsNotNone(window.tri_view_panel.cse_asset)
            self.assertEqual(window.state.selected_ids, {42, 43})
            self.assertIn("CSE map all valid", window.selection_source)
            window.close()

    def test_2d_polygon_selection_returns_vertex_ids(self):
        try:
            from PySide6.QtCore import QPoint
            from PySide6.QtWidgets import QApplication
            from smpl_vertex_region_selector.alignment.assets import TriViewAsset
            from smpl_vertex_region_selector.selection.region_state import RegionState
            from smpl_vertex_region_selector.viewer.tri_view_panel import TriViewCanvas
        except Exception as exc:
            self.skipTest(f"GUI dependencies unavailable: {exc}")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "view.png"
            Image.new("RGB", (10, 10), (40, 40, 40)).save(image_path)
            id_map = np.full((10, 10), -1, dtype=np.int32)
            id_map[2:6, 2:6] = 42
            canvas = TriViewCanvas()
            canvas.resize(100, 100)
            canvas.set_asset(
                TriViewAsset("test", image_path, image_path, Image.open(image_path).copy(), id_map)
            )
            canvas.set_region_state(RegionState())
            rect = canvas._image_rect()
            ids = canvas._ids_from_widget_polygon(
                [
                    QPoint(rect.left() + 20, rect.top() + 20),
                    QPoint(rect.left() + 70, rect.top() + 20),
                    QPoint(rect.left() + 70, rect.top() + 70),
                    QPoint(rect.left() + 20, rect.top() + 70),
                ]
            )
            self.assertEqual(ids, [42])
            canvas.actual_size()
            canvas.fit_view()
            canvas.close()

    def test_3d_polygon_selection_returns_projected_vertex_ids(self):
        try:
            from PySide6.QtCore import QPoint
            from PySide6.QtWidgets import QApplication
            from smpl_vertex_region_selector.geometry.vertex_table import VertexTable
            from smpl_vertex_region_selector.viewer.point_cloud_canvas import PointCloudCanvas
        except Exception as exc:
            self.skipTest(f"GUI dependencies unavailable: {exc}")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication([])
        canvas = PointCloudCanvas()
        canvas.resize(400, 400)
        points = np.asarray([[-1, -1, 0], [0, 0, 0], [1, 1, 0]], dtype=np.float32)
        table = VertexTable(
            vertex_ids=np.asarray([0, 1, 2], dtype=np.int32),
            points=points,
            columns=("vertex_id",),
            source_path=Path(__file__),
            coordinate_mode="test",
        )
        canvas.set_vertex_table(table)
        canvas.set_view("front")
        projected, _depth = canvas._project_points(points)
        cx, cy = projected[1]
        ids = canvas._ids_in_polygon(
            [
                QPoint(int(cx - 30), int(cy - 30)),
                QPoint(int(cx + 30), int(cy - 30)),
                QPoint(int(cx + 30), int(cy + 30)),
                QPoint(int(cx - 30), int(cy + 30)),
            ]
        )
        self.assertEqual(ids, [1])
        canvas.close()


if __name__ == "__main__":
    unittest.main()

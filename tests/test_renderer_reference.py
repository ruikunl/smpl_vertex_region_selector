import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from smpl_vertex_region_selector.alignment.renderer import render_vertex_id_view


class RendererReferenceTest(unittest.TestCase):
    def test_render_vertex_id_view_writes_colored_reference_and_valid_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            points = np.asarray(
                [
                    [-0.2, 0.0, -0.1],
                    [0.2, 0.0, -0.1],
                    [0.0, 0.6, 0.0],
                    [0.0, -0.5, 0.1],
                    [0.0, 0.2, 0.2],
                ],
                dtype=np.float32,
            )
            render_vertex_id_view(points, output / "front.png", output / "front.vertex_id_map.npz", view="front", image_size=96)
            image = np.asarray(Image.open(output / "front.png").convert("RGB"))
            self.assertGreater(float(np.abs(image[:, :, 0].astype(float) - image[:, :, 1].astype(float)).mean()), 1.0)
            id_map = np.load(output / "front.vertex_id_map.npz")["vertex_id_map"]
            valid = id_map[id_map >= 0]
            self.assertGreater(valid.size, 0)
            self.assertGreaterEqual(int(valid.min()), 0)
            self.assertLess(int(valid.max()), points.shape[0])

    def test_front_prefers_positive_z_and_back_prefers_negative_z(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            points = np.asarray(
                [
                    [0.0, 0.0, -0.2],
                    [0.0, 0.0, 0.2],
                ],
                dtype=np.float32,
            )
            render_vertex_id_view(points, output / "front.png", output / "front.vertex_id_map.npz", view="front", image_size=64)
            render_vertex_id_view(points, output / "back.png", output / "back.vertex_id_map.npz", view="back", image_size=64)
            front = np.load(output / "front.vertex_id_map.npz")["vertex_id_map"]
            back = np.load(output / "back.vertex_id_map.npz")["vertex_id_map"]
            self.assertEqual(int(front[32, 32]), 1)
            self.assertEqual(int(back[32, 32]), 0)


if __name__ == "__main__":
    unittest.main()

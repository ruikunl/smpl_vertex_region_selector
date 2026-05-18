import tempfile
import unittest
from pathlib import Path

from smpl_vertex_region_selector.exports.region_export import export_region_bundle
from smpl_vertex_region_selector.region_io import load_region_file
from smpl_vertex_region_selector.selection.region_state import RegionState


class RegionStateExportTest(unittest.TestCase):
    def test_add_remove_undo_redo_and_export_bundle(self):
        state = RegionState()
        state.set_current_region("abdomen_front")
        state.add_to_current([3, 1, 3])
        self.assertEqual(state.regions["abdomen_front"], [1, 3])
        state.remove_from_current([1])
        self.assertEqual(state.regions["abdomen_front"], [3])
        self.assertTrue(state.undo())
        self.assertEqual(state.regions["abdomen_front"], [1, 3])
        self.assertTrue(state.redo())
        self.assertEqual(state.regions["abdomen_front"], [3])
        with tempfile.TemporaryDirectory() as tmp:
            paths = export_region_bundle(Path(tmp), state)
            self.assertTrue(paths["json"].exists())
            self.assertTrue(paths["csv"].exists())
            self.assertTrue((paths["txt_dir"] / "abdomen_front.txt").exists())
            loaded = load_region_file(paths["json"])
            self.assertEqual(loaded["regions"]["abdomen_front"], [3])


if __name__ == "__main__":
    unittest.main()

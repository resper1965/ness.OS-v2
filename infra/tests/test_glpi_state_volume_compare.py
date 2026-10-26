import importlib.util
import os
import pathlib
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "glpi_state_volume_compare.py"
spec = importlib.util.spec_from_file_location("glpi_state_volume_compare", SCRIPT)
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)


class GLPIStateVolumeCompareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = pathlib.Path(self.temp.name)
        self.before = root / "before"
        self.after = root / "after"
        for directory in (self.before, self.after):
            directory.mkdir()
            (directory / "config").mkdir()
            (directory / "config" / "config_db.php").write_bytes(b"private synthetic data")
            (directory / "latest").symlink_to("config/config_db.php")

    def test_identical_tree_passes_without_following_symlinks(self):
        result = compare.compare_trees(self.before, self.after)
        self.assertEqual(result["files"], 1)
        self.assertEqual(result["bytes"], 22)

    def test_changed_file_fails(self):
        (self.after / "config" / "config_db.php").write_bytes(b"changed synthetic data")
        with self.assertRaisesRegex(ValueError, "differ"):
            compare.compare_trees(self.before, self.after)

    def test_missing_file_fails(self):
        (self.after / "config" / "config_db.php").unlink()
        with self.assertRaisesRegex(ValueError, "differ"):
            compare.compare_trees(self.before, self.after)

    def test_changed_mode_fails(self):
        os.chmod(self.after / "config" / "config_db.php", 0o600)
        with self.assertRaisesRegex(ValueError, "differ"):
            compare.compare_trees(self.before, self.after)


if __name__ == "__main__":
    unittest.main()

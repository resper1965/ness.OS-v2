import importlib.util
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "glpi_state_volume_preflight.py"
spec = importlib.util.spec_from_file_location("glpi_state_volume_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class GLPIStateVolumePreflightTests(unittest.TestCase):
    def setUp(self):
        self.runtime = [{"Mounts": [{"Type": "volume", "Name": "app_glpi-state", "Destination": "/var/glpi"}]}]
        self.compose = {
            "services": {"glpi": {"volumes": [{"type": "volume", "source": "glpi-state", "target": "/var/glpi"}]}},
            "volumes": {"glpi-state": {"name": "app_glpi-state"}},
        }

    def test_matching_named_state_volume_passes(self):
        self.assertEqual(preflight.validate_state_volume(self.compose, self.runtime), "app_glpi-state")

    def test_current_wrong_compose_mount_blocks_recreate(self):
        self.compose["services"]["glpi"]["volumes"][0]["target"] = "/var/www/html/glpi"
        with self.assertRaisesRegex(ValueError, "Compose.*var/glpi"):
            preflight.validate_state_volume(self.compose, self.runtime)

    def test_switching_to_different_named_volume_blocks_recreate(self):
        self.runtime[0]["Mounts"][0]["Name"] = "7dae4e8e-anonymous"
        with self.assertRaisesRegex(ValueError, "does not match"):
            preflight.validate_state_volume(self.compose, self.runtime)

    def test_anonymous_compose_volume_blocks_recreate(self):
        self.compose["services"]["glpi"]["volumes"][0].pop("source")
        with self.assertRaisesRegex(ValueError, "named volume"):
            preflight.validate_state_volume(self.compose, self.runtime)

    def test_bind_mount_blocks_recreate(self):
        self.compose["services"]["glpi"]["volumes"][0]["type"] = "bind"
        with self.assertRaisesRegex(ValueError, "named volume"):
            preflight.validate_state_volume(self.compose, self.runtime)


if __name__ == "__main__":
    unittest.main()

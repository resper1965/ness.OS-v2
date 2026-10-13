import importlib.util
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "glpi_caddy_maintenance.py"
spec = importlib.util.spec_from_file_location("glpi_caddy_maintenance", SCRIPT)
maintenance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maintenance)


class GLPICaddyMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.current = (pathlib.Path(__file__).resolve().parents[2] / "app" / "Caddyfile").read_text()

    def test_only_glpi_site_changes(self):
        candidate = maintenance.build_maintenance(self.current)
        before, original_glpi = self.current.split("# GLPI Service Desk with Authentik Forward Auth SSO\n", 1)
        _, after = original_glpi.split("# Psono Community", 1)
        self.assertTrue(candidate.startswith(before))
        self.assertTrue(candidate.endswith("# Psono Community" + after))
        self.assertIn('respond "GLPI temporariamente em manutenção" 503', candidate)
        self.assertIn('header Cache-Control "no-store"', candidate)
        self.assertNotIn("reverse_proxy ninf-glpi:80", candidate)

    def test_unknown_source_shape_blocks_generation(self):
        with self.assertRaisesRegex(ValueError, "GLPI site"):
            maintenance.build_maintenance("hub.example { respond 200 }\n")


if __name__ == "__main__":
    unittest.main()

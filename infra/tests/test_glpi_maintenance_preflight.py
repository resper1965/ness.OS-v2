import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/glpi_maintenance_preflight.py"
spec = importlib.util.spec_from_file_location("glpi_maintenance_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def _config(tmp_path):
    paths = []
    for name in ("app", "user", "bearer"):
        path = tmp_path / name
        path.write_text("opaque")
        path.chmod(0o600)
        paths.append(path)
    return {
        "image": "ghcr.io/ness/api@sha256:" + "a" * 64,
        "subnet": "172.30.250.0/28",
        "gateway_ip": "172.30.250.3",
        "secret_paths": paths,
    }


def test_valid_candidate_has_no_findings(tmp_path):
    assert preflight.validate(**_config(tmp_path)) == []


def test_image_must_have_immutable_digest(tmp_path):
    config = _config(tmp_path)
    config["image"] = "ghcr.io/ness/api:latest"
    assert "IMAGE_NOT_IMMUTABLE" in preflight.validate(**config)


def test_gateway_ip_must_be_usable_inside_private_subnet(tmp_path):
    config = _config(tmp_path)
    config["gateway_ip"] = "172.30.250.16"
    assert "IP_OUTSIDE_SUBNET" in preflight.validate(**config)
    config["gateway_ip"] = "172.30.250.0"
    assert "IP_NOT_USABLE" in preflight.validate(**config)


def test_secret_files_must_exist_be_nonempty_and_owner_only(tmp_path):
    config = _config(tmp_path)
    config["secret_paths"][0].chmod(0o644)
    config["secret_paths"][1].write_text("")
    config["secret_paths"][2].unlink()
    findings = preflight.validate(**config)
    assert findings.count("SECRET_UNSAFE") == 3

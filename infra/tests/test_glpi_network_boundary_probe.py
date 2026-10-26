import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/glpi_network_boundary_probe.py"
spec = importlib.util.spec_from_file_location("glpi_network_boundary_probe", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_shared_network_blocks_boundary():
    report = module.assess_networks({"app_ninf-net"}, {"app_ninf-net"})
    assert report == {"status": "BLOCKED_DIRECT_PATH", "shared_networks": 1}


def test_separate_networks_are_not_accepted_as_full_isolation():
    report = module.assess_networks({"hub_only"}, {"glpi_only"})
    assert report == {"status": "NETWORK_SEPARATED_UNVERIFIED", "shared_networks": 0}


def test_missing_network_data_fails_closed():
    report = module.assess_networks(set(), {"glpi_only"})
    assert report == {"status": "UNKNOWN_NETWORK_TOPOLOGY", "shared_networks": 0}


def test_alert_worker_direct_path_blocks_even_if_api_is_separated():
    report = module.assess_consumers(
        {"api": {"hub_only"}, "worker_alerts": {"app_ninf-net"}},
        {"app_ninf-net"},
    )
    assert report == {
        "status": "BLOCKED_DIRECT_PATH",
        "shared_networks": 1,
        "direct_consumers": ["worker_alerts"],
    }


def test_missing_worker_topology_fails_closed():
    report = module.assess_consumers(
        {"api": {"hub_only"}, "worker_alerts": set()}, {"glpi_only"}
    )
    assert report["status"] == "UNKNOWN_NETWORK_TOPOLOGY"

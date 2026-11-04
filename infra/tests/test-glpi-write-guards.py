from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARDED_SCRIPTS = (
    "infra/scripts/glpi-hub-resolution-webhook.php",
    "infra/scripts/glpi-hub-complete-inventory.php",
    "infra/scripts/glpi-hub-link-tickets.php",
    "infra/scripts/glpi-hub-default-owners.php",
    "infra/scripts/glpi-hub-client-check.php",
    "infra/scripts/zabbix-hub-rollout.php",
    "infra/scripts/zabbix-hub-recovery.php",
    "infra/scripts/glpi-t07-inventory-prepare.php",
)


def test_write_scripts_require_apply_before_bootstrapping_application():
    for relative_path in GUARDED_SCRIPTS:
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        apply_guard = source.find("--apply")
        bootstrap = min(
            position
            for marker in ("require ", "APP::getInstance()->run")
            if (position := source.find(marker)) >= 0
        )
        assert apply_guard >= 0, relative_path
        assert apply_guard < bootstrap, relative_path


def test_temporary_account_cleanup_requires_apply_too():
    source = (ROOT / "infra/scripts/glpi-hub-client-check.php").read_text(
        encoding="utf-8"
    )
    cleanup_branch = source.find("if (in_array('--cleanup', $argv, true))")
    apply_guard = source.find("if (!in_array('--apply', $argv, true))")
    assert cleanup_branch >= 0 and apply_guard < cleanup_branch

def test_t07_prepare_dry_run_never_writes_and_never_enables_inventory():
    source = (ROOT / "infra/scripts/glpi-t07-inventory-prepare.php").read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("//"))
    dry_run_return = code.find("if (!$apply)")
    assert dry_run_return >= 0
    for write in ("setConfigurationValues", "->delete(", "beginTransaction", "STDOUT"):
        assert code.find(write) > dry_run_return, write
    assert "callAsSystem" not in code
    call = code[code.find("setConfigurationValues"):]
    assert "enabled_inventory" not in call[:call.find("]);")]

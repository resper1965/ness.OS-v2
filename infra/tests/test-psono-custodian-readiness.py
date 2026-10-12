import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "custodian_readiness",
    Path(__file__).resolve().parents[1] / "psono/scripts/check-custodian-readiness.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def compliant_report():
    rows = {
        "psono_health": "healthy",
        "database_health": "healthy",
        "https_health": "yes",
        "backup_timer_active": "yes",
        "last_backup_result": "success",
        "psono_env_permissions": "root:root:600",
        "backup_env_permissions": "root:root:600",
        "registration_enabled": "no",
        "multifactor_enforced": "yes",
        "psono_f2_readiness_report": "PASS",
        "emergency_code_count": "1",
    }
    for user in ("resper", "iaraujo"):
        for field in ("active", "superuser", "mfa", "has_logged_in"):
            rows[f"custodian_{user}_{field}"] = "yes"
        rows[f"custodian_{user}_password_change_required"] = "no"
        rows[f"custodian_{user}_recovery_codes"] = "2"
    return "\n".join(f"{key}={value}" for key, value in rows.items())


def test_two_custodians_ready():
    assert module.readiness_failures(compliant_report()) == []


def test_missing_report_fails_closed():
    assert module.readiness_failures("")


def test_one_custodian_without_mfa_is_rejected():
    report = compliant_report().replace(
        "custodian_resper_mfa=yes", "custodian_resper_mfa=no"
    )
    assert module.readiness_failures(report) == ["custodian_resper_mfa"]


def test_missing_or_invalid_recovery_is_rejected():
    for value in ("0", "-1", "unknown", ""):
        report = compliant_report().replace(
            "custodian_iaraujo_recovery_codes=2",
            f"custodian_iaraujo_recovery_codes={value}",
        )
        assert "custodian_iaraujo_recovery_codes" in module.readiness_failures(report)


def test_duplicate_status_cannot_override_failure():
    report = compliant_report() + "\nmultifactor_enforced=yes"
    assert module.readiness_failures(report) == ["multifactor_enforced"]

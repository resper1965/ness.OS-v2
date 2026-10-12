#!/usr/bin/env python3
"""Validate a Psono F2 status report; never consume secret values."""

import sys


def readiness_failures(report: str) -> list[str]:
    values = {}
    duplicates = set()
    for line in report.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            if key in values:
                duplicates.add(key)
            values[key] = value
    required = {
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
    }
    for custodian in ("resper", "iaraujo"):
        prefix = f"custodian_{custodian}_"
        for field in ("active", "superuser", "mfa", "has_logged_in"):
            required[prefix + field] = "yes"
        required[prefix + "password_change_required"] = "no"
    failures = [key for key, expected in required.items() if values.get(key) != expected]
    for key in (
        "custodian_resper_recovery_codes",
        "custodian_iaraujo_recovery_codes",
        "emergency_code_count",
    ):
        value = values.get(key, "")
        if not value.isascii() or not value.isdecimal() or int(value) < 1:
            failures.append(key)
    return sorted(set(failures) | duplicates)


if __name__ == "__main__":
    failures = readiness_failures(sys.stdin.read())
    for key in failures:
        print(f"psono_custodian_pending={key}")
    print("psono_custodian_readiness=" + ("FAIL" if failures else "PASS"))
    sys.exit(1 if failures else 0)

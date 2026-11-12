from app.services.stack_health import build_stack_health_report


def test_stack_health_marks_runtime_issue_when_provider_is_running():
    report = build_stack_health_report(
        {
            "sources": {
                "zabbix": {"status": "down", "error_code": "TimeoutError"},
                "glpi": {"status": "ok"},
            },
            "contabo": {
                "stacks": {
                    "aiops": {"status": "ok", "provider_status": "running"},
                    "zabbix-prod": {"status": "ok", "provider_status": "running"},
                    "zabbix-prd-01": {"status": "ok", "provider_status": "running"},
                }
            },
            "pipeline": {"status": "degraded", "detail": "workers_timeout"},
        }
    )

    assert report["summary"]["total"] == 3
    assert report["summary"]["degraded"] >= 1
    assert any(
        finding["code"] == "runtime_issue_with_provider_running"
        for finding in report["findings"]
    )


def test_stack_health_ok_summary_when_domains_are_healthy():
    report = build_stack_health_report(
        {
            "sources": {
                "zabbix": {"status": "ok"},
                "glpi": {"status": "ok"},
            },
            "contabo": {
                "stacks": {
                    "aiops": {"status": "ok", "provider_status": "running"},
                    "zabbix-prod": {"status": "ok", "provider_status": "running"},
                    "zabbix-prd-01": {"status": "ok", "provider_status": "running"},
                }
            },
            "pipeline": {"status": "ok"},
        }
    )

    assert report["summary"] == {"total": 3, "ok": 3, "degraded": 0, "down": 0}
    assert report["findings"] == []

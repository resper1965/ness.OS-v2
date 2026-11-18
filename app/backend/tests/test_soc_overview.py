from datetime import UTC, datetime, timedelta

from app.api.routers.secops import summarize_soc

NOW = datetime(2026, 11, 15, 12, tzinfo=UTC)


def _row(level, minutes_ago, agent="dc-01", groups=(), tactic=(), action="ESCALATE"):
    return {
        "id": minutes_ago,
        "created_at": NOW - timedelta(minutes=minutes_ago),
        "customer_id": "cavan",
        "agent_name": agent,
        "classification": "HIGH",
        "action_taken": action,
        "rule": {
            "id": f"r{level}",
            "level": level,
            "description": f"regra {level}",
            "groups": list(groups),
            "mitre": {"tactic": list(tactic)},
        },
    }


def test_summarize_bands_series_and_tops():
    rows = [
        _row(15, 10, tactic=["Credential Access"]),
        _row(12, 70, groups=["authentication_failed"], tactic=["Credential Access"]),
        _row(7, 130, agent="web-01"),
        _row(
            3,
            30,
            agent="web-01",
            groups=["authentication_success"],
            action="ARCHIVE_NO_LLM",
        ),
        {**_row(5, 5), "rule": None, "action_taken": "PENDING_TENANT_REVIEW"},
    ]
    s = summarize_soc(rows, 24, NOW)
    assert s["bands"] == {"critical": 1, "high": 1, "medium": 1, "low": 2}
    assert (
        len(s["series"]) == 24
        and sum(sum(b[k] for k in s["bands"]) for b in s["series"]) == 5
    )
    assert s["series"][-1]["critical"] == 1 and s["series"][-2]["high"] == 1
    assert (s["auth_failures"], s["auth_successes"]) == (1, 1)
    assert (s["pending_tenant_review"], s["archived_no_llm"]) == (1, 1)
    assert s["top_tactics"] == [{"key": "Credential Access", "count": 2}]
    assert s["top_agents"][0] == {"key": "dc-01", "count": 3}
    assert s["top_rules"][0]["id"] in {"r15", "r12", "r7", "r3", "—"}
    assert s["events"][0]["band"] == "critical" and not s["truncated"]


def test_summarize_long_window_uses_daily_buckets():
    s = summarize_soc([_row(9, 60 * 24 * 3)], 168, NOW)
    assert s["bucket_seconds"] == 86400 and len(s["series"]) == 7
    assert s["series"][4]["medium"] == 1  # 7 dias atrás é o balde 0

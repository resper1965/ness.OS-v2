#!/usr/bin/env python3
"""Persist validated hub health samples; summarize probe latency, not event latency."""

import argparse
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

COMPONENTS = ("zabbix", "glpi", "workers", "delivery")
RETENTION_DAYS = 30


def normalized(raw, exit_code, now):
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or value.get("status") not in {"ok", "degraded"}:
            raise ValueError()
        for key in COMPONENTS:
            component = value[key]
            if component["status"] not in {"ok", "error", "degraded"}:
                raise ValueError()
            duration = component["duration_ms"]
            if (
                type(duration) not in (int, float)
                or not math.isfinite(duration)
                or duration < 0
            ):
                raise ValueError()
        if value["status"] == "ok" and any(
            value[k]["status"] != "ok" for k in COMPONENTS
        ):
            raise ValueError()
        if exit_code and value["status"] == "ok":
            raise ValueError()
        value = {
            k: value[k] for k in ("status", "checked_at", "duration_ms", *COMPONENTS)
        }
        if type(value["duration_ms"]) not in (int, float) or value["duration_ms"] < 0:
            raise ValueError()
        json.dumps(value, allow_nan=False)
        checked = datetime.fromisoformat(value["checked_at"])
        if checked.tzinfo is None or abs((now - checked).total_seconds()) > 120:
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        # Never copy malformed stdout or a traceback into the published report.
        value = {
            "status": "error",
            "checked_at": now.isoformat(),
            "detail": "MonitorExecutionFailed",
        }
    value["recorded_at"] = now.isoformat()
    value["monitor_exit_code"] = exit_code
    return value


def record(directory, raw, exit_code, now):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    value = normalized(raw, exit_code, now)
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".health-", dir=directory)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, directory / "status.json")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    daily = directory / f"health-{now:%Y-%m-%d}.jsonl"
    with daily.open("a") as handle:
        handle.write(encoded)
    daily.chmod(0o600)
    cutoff = (now - timedelta(days=RETENTION_DAYS)).date()
    for path in directory.glob("health-*.jsonl"):
        match = re.fullmatch(r"health-(\d{4}-\d{2}-\d{2})\.jsonl", path.name)
        if match:
            try:
                expired = datetime.strptime(match[1], "%Y-%m-%d").date() < cutoff
            except ValueError:
                continue
            if expired:
                path.unlink()
    return value


def summarize(directory, hours, now):
    samples = []
    invalid = 0
    cutoff = now - timedelta(hours=hours)
    for path in sorted(directory.glob("health-*.jsonl")):
        for line in path.read_text().splitlines():
            try:
                value = json.loads(line)
                at = datetime.fromisoformat(value["recorded_at"])
                if cutoff <= at <= now:
                    samples.append(value)
            except (ValueError, TypeError, KeyError):
                invalid += 1
    samples.sort(key=lambda s: s["recorded_at"])
    components = {}
    for key in COMPONENTS:
        durations = sorted(s[key]["duration_ms"] for s in samples if key in s)
        components[key] = {
            "measured_samples": len(durations),
            "unhealthy_samples": sum(
                s.get(key, {}).get("status") != "ok" for s in samples
            ),
            "p50_ms": (
                durations[math.ceil(len(durations) * 0.5) - 1] if durations else None
            ),
            "p95_ms": (
                durations[math.ceil(len(durations) * 0.95) - 1] if durations else None
            ),
        }
    unhealthy = sum(s["status"] != "ok" for s in samples)
    return {
        "window_hours": hours,
        "samples": len(samples),
        "invalid_lines": invalid,
        "first_sample": samples[0]["recorded_at"] if samples else None,
        "last_sample": samples[-1]["recorded_at"] if samples else None,
        "unhealthy_samples": unhealthy,
        "unhealthy_sample_percent": (
            round(100 * unhealthy / len(samples), 2) if samples else None
        ),
        "components": components,
        "interpretation": "Probe samples only; gaps are not evidence of availability or an SLA.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--directory", type=Path, default=Path("/var/lib/ness-os/hub-integration")
    )
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--hours", type=int, default=24, choices=range(1, 721))
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    os.umask(0o077)
    if args.summary:
        value = summarize(args.directory, args.hours, now)
    else:
        raw = sys.stdin.read(100001)
        value = record(
            args.directory, raw if len(raw) <= 100000 else "", args.exit_code, now
        )
    print(json.dumps(value, ensure_ascii=False, allow_nan=False))
    return 0 if args.summary or value["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

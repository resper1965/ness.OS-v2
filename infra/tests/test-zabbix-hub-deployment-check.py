from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/zabbix-hub-deployment-check.py"


def test_synthetic_trapper_write_requires_explicit_apply():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 2
    assert "Usage: zabbix-hub-deployment-check.py --apply 0|1" in result.stderr

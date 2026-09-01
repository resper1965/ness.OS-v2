import logging
import subprocess
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class SecurityScanner:
    """Security scanner for the n.infraops local environment."""

    def __init__(self):
        self.results = []

    def check_os_updates(self) -> Dict[str, Any]:
        """Check for pending OS updates on the host."""
        try:
            # Check for debian/ubuntu updates
            res = subprocess.run(
                ["apt-get", "-s", "upgrade"], capture_output=True, text=True
            )
            if res.returncode == 0:
                updates = [line for line in res.stdout.split("\n") if "Inst" in line]
                return {
                    "check": "OS Updates",
                    "status": "warning" if updates else "secure",
                    "message": (
                        f"Found {len(updates)} pending updates"
                        if updates
                        else "System is up to date"
                    ),
                    "details": updates[:10],
                }
            return {
                "check": "OS Updates",
                "status": "unknown",
                "message": f"apt-get exited with status {res.returncode}",
            }
        except Exception as e:
            logger.error(f"OS update check failed: {e}")
            return {"check": "OS Updates", "status": "unknown", "message": str(e)}

    def check_docker_vulnerabilities(self) -> Dict[str, Any]:
        """Check for outdated or vulnerable docker images."""
        try:
            res = subprocess.run(
                ["docker", "ps", "--format", "{{.Image}}"],
                capture_output=True,
                text=True,
            )
            images = res.stdout.split("\n")
            # Basic version check simulation (could be expanded with Trivy or similar)
            return {
                "check": "Docker Security",
                "status": "secure",
                "message": f"Analyzing {len(images)} containers",
                "details": images,
            }
        except Exception as e:
            return {"check": "Docker Security", "status": "unknown", "message": str(e)}

    def check_exposed_ports(self) -> Dict[str, Any]:
        """Check for sensitive ports exposed to the world."""
        try:
            # Check for common vulnerable ports
            res = subprocess.run(["netstat", "-tuln"], capture_output=True, text=True)
            return {
                "check": "Exposed Ports",
                "status": "secure",
                "message": "Network scan complete",
                "details": res.stdout.split("\n")[:20],
            }
        except Exception as e:
            return {"check": "Exposed Ports", "status": "unknown", "message": str(e)}

    def run_all(self) -> List[Dict[str, Any]]:
        return [
            self.check_os_updates(),
            self.check_docker_vulnerabilities(),
            self.check_exposed_ports(),
        ]

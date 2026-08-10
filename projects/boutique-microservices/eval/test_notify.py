import sys
from pathlib import Path

# eval/ is at projects/boutique-microservices/eval, so climb 3 levels to the repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "projects" / "aiops-assistant"))

from notify_slack import notify_slack

mock = {
    "service": "orders",
    "root_cause": "Deployment scaled to zero replicas (0 desired / 0 available).",
    "confidence": 0.92,
    "timestamp": "2026-07-27 21:14 UTC",
}
notify_slack(mock, dry_run=True)
"""Send a Kira diagnosis to Slack via an Incoming Webhook (Block Kit)."""
import os
import json
import requests

WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:8080")


def build_blocks(d: dict) -> dict:
    """d: {service, root_cause, confidence, timestamp}."""
    conf = d.get("confidence")
    conf_str = f"{conf:.0%}" if isinstance(conf, (int, float)) else str(conf)
    return {
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": "🚨 Kira: incident diagnosed"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Service:*\n{d.get('service', 'unknown')}"},
                {"type": "mrkdwn", "text": f"*Confidence:*\n{conf_str}"},
                {"type": "mrkdwn", "text": f"*Time:*\n{d.get('timestamp', '')}"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Root cause:*\n{d.get('root_cause', '')}"}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Open Grafana"}, "url": GRAFANA_URL},
            ]},
        ]
    }


def notify_slack(diagnosis: dict, dry_run: bool = False) -> bool:
    """Post the diagnosis. dry_run (or missing webhook) just prints the payload."""
    payload = build_blocks(diagnosis)
    if dry_run or not WEBHOOK:
        print(json.dumps(payload, indent=2))
        return True
    resp = requests.post(WEBHOOK, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.text == "ok"
"""Local, zero-AWS reasoner for Kira: tool selection + diagnosis classification."""
import os, json
from openai import OpenAI

client = OpenAI()
MODEL = os.getenv("KIRA_REASON_MODEL", "gpt-4o-mini")
TOOLS = ["fetch_logs", "fetch_metrics", "fetch_health"]
CATEGORIES = [
    "scaled_to_zero", "crash_loop", "image_pull_error", "high_error_rate",
    "high_latency", "resource_exhaustion", "db_connection_error", "oom_killed",
    "node_not_ready", "healthy",
]


def _json_call(prompt):
    out = client.chat.completions.create(
        model=MODEL, temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    ).choices[0].message.content
    return json.loads(out)


def select_tool(alert):
    p = (f"An SRE agent has these tools: {TOOLS}. "
         f"fetch_logs=read error logs, fetch_metrics=CPU/mem/latency/error-rate, "
         f"fetch_health=deployment/pod/node status. Given the alert, pick the single best "
         f'first tool. Reply JSON {{"tool": "<one of the tools>"}}.\n\nALERT: {alert}')
    return _json_call(p).get("tool")


def diagnose(alert, tool_output):
    p = (f"Given the alert and the tool output, classify the root cause into exactly one "
         f'category from {CATEGORIES}. Reply JSON {{"category": "<one category>"}}.\n\n'
         f"ALERT: {alert}\n\nTOOL OUTPUT: {tool_output}")
    return _json_call(p).get("category")
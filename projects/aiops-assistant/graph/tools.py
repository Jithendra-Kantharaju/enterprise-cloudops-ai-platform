"""Kira's three tools with a mock/live switch. mock = canned outputs (zero AWS)."""
import os

KIRA_TOOL_MODE = os.getenv("KIRA_TOOL_MODE", "mock").lower()
SCENARIO = os.getenv("KIRA_MOCK_SCENARIO", "orders_scaled_zero")

# Canned tool outputs per scenario — deterministic, good for the trace screenshot.
_SCENARIOS = {
    "orders_scaled_zero": {
        "fetch_health": {
            "cluster": "ACTIVE", "nodes_ready": 2,
            "deployments": [
                {"name": "orders", "desired": 0, "available": 0},
                {"name": "auth", "desired": 1, "available": 1},
                {"name": "gateway", "desired": 1, "available": 1},
            ],
        },
        "fetch_metrics": {"pod_cpu": {"auth": 0.12, "gateway": 0.20},
                          "pod_restarts": {}, "unavailable_replicas": {}},
        "fetch_logs": {"status": "no_logs_found",
                       "message": "No ERROR logs for orders in the last 1h"},
    },
    "auth_crashloop": {
        "fetch_health": {"cluster": "ACTIVE", "nodes_ready": 2,
                         "deployments": [{"name": "auth", "desired": 1, "available": 0}]},
        "fetch_metrics": {"pod_cpu": {"auth": 0.05}, "pod_restarts": {"auth": 7}},
        "fetch_logs": {"status": "logs_found",
                       "events": ["FATAL: database \"auth_db\" does not exist (3D000)"]},
    },
}


def _mock(tool_name: str):
    return _SCENARIOS.get(SCENARIO, _SCENARIOS["orders_scaled_zero"]).get(tool_name, {})


def _live(tool_name: str, **params):
    """Call the real Lambda handler (needs AWS creds). Used only when KIRA_TOOL_MODE=live."""
    import importlib
    mod = importlib.import_module(f"lambda.{tool_name}.lambda_function")
    event = {"parameters": [{"name": k, "value": str(v)} for k, v in params.items()]}
    return mod.lambda_handler(event, None)


def fetch_health(**p):   return _mock("fetch_health")  if KIRA_TOOL_MODE == "mock" else _live("fetch_health", **p)
def fetch_metrics(**p):  return _mock("fetch_metrics") if KIRA_TOOL_MODE == "mock" else _live("fetch_metrics", **p)
def fetch_logs(**p):     return _mock("fetch_logs")    if KIRA_TOOL_MODE == "mock" else _live("fetch_logs", **p)

TOOLS = {"fetch_health": fetch_health, "fetch_metrics": fetch_metrics, "fetch_logs": fetch_logs}
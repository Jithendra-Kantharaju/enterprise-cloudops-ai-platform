"""
Kira reasoning as a LangGraph state machine, with a decision trace.

Flow: classify_intent -> select_tool -> call_tool -> correlate
      -> (loop back to select_tool if confidence low) -> generate_diagnosis
"""
import os
import json
from typing import TypedDict, List, Dict, Any

from openai import OpenAI
from langgraph.graph import StateGraph, END

from graph.tools import TOOLS

MODEL = os.getenv("KIRA_REASON_MODEL", "gpt-4o-mini")
CONFIDENCE_THRESHOLD = 0.7
MAX_LOOPS = 3
_client = OpenAI()

# Same fixed vocabulary as eval/kira_reasoner.py (Step 3), so both eval layers
# describe root causes with the same words instead of free-text drifting apart.
CATEGORIES = [
    "scaled_to_zero", "crash_loop", "image_pull_error", "high_error_rate",
    "high_latency", "resource_exhaustion", "db_connection_error", "oom_killed",
    "node_not_ready", "healthy",
]


class KiraState(TypedDict):
    alert: str
    tools_called: List[str]
    tool_results: Dict[str, Any]
    confidence: float
    diagnosis: Dict[str, Any]
    trace: List[Dict[str, str]]
    loops: int


def _json_llm(prompt: str) -> dict:
    out = _client.chat.completions.create(
        model=MODEL, temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    ).choices[0].message.content
    return json.loads(out)


def classify_intent(state: KiraState) -> dict:
    r = _json_llm(
        f'Classify this ops alert. Reply JSON {{"intent": "...", "needed_info": "..."}}.\n\n'
        f'ALERT: {state["alert"]}'
    )
    step = {"node": "classify_intent",
            "detail": f'intent="{r.get("intent")}", needs: {r.get("needed_info")}'}
    return {"trace": state["trace"] + [step]}


def select_tool(state: KiraState) -> dict:
    available = [t for t in TOOLS if t not in state["tools_called"]] or list(TOOLS)
    r = _json_llm(
        f'SRE tools: fetch_logs (error logs), fetch_metrics (cpu/mem/restarts), '
        f'fetch_health (deployment/pod/node status). Already used: {state["tools_called"]}. '
        f'Pick the single best NEXT tool from {available}. Reply JSON {{"tool": "..."}}.\n\n'
        f'ALERT: {state["alert"]}'
    )
    tool = r.get("tool") if r.get("tool") in TOOLS else available[0]
    step = {"node": "select_tool", "detail": f'chose {tool} (loop {state["loops"] + 1})'}
    return {"tools_called": state["tools_called"] + [tool],
            "loops": state["loops"] + 1, "trace": state["trace"] + [step],
            "_next_tool": tool}  # stashed for call_tool


def call_tool(state: KiraState) -> dict:
    tool = state["tools_called"][-1]
    output = TOOLS[tool]()
    results = dict(state["tool_results"]); results[tool] = output
    step = {"node": "call_tool", "detail": f'{tool} -> {json.dumps(output)[:160]}'}
    return {"tool_results": results, "trace": state["trace"] + [step]}


def correlate(state: KiraState) -> dict:
    r = _json_llm(
        f'Given the alert and tool results so far, how confident are you that you can name '
        f'the root cause? Reply JSON {{"confidence": 0.0-1.0, "reason": "..."}}.\n\n'
        f'ALERT: {state["alert"]}\nTOOL RESULTS: {json.dumps(state["tool_results"])}'
    )
    conf = float(r.get("confidence", 0.0))
    step = {"node": "correlate", "detail": f'confidence={conf:.2f} — {r.get("reason", "")}'}
    return {"confidence": conf, "trace": state["trace"] + [step]}


def generate_diagnosis(state: KiraState) -> dict:
    r = _json_llm(
        f'Produce the final diagnosis. The "category" field MUST be exactly one value from '
        f'this list, no other wording is allowed: {CATEGORIES}. Reply JSON '
        f'{{"service": "...", "category": "<one of {CATEGORIES}>", "root_cause": "...", '
        f'"confidence": 0.0-1.0}}.\n\n'
        f'ALERT: {state["alert"]}\nTOOL RESULTS: {json.dumps(state["tool_results"])}'
    )
    # Guard against the model drifting off-list despite the instruction.
    if r.get("category") not in CATEGORIES:
        r["category"] = "healthy" if not state["tool_results"] else r.get("category", "unknown")
    step = {"node": "generate_diagnosis",
            "detail": f'{r.get("service")}: {r.get("category")} ({r.get("confidence")})'}
    return {"diagnosis": r, "trace": state["trace"] + [step]}


def _route(state: KiraState) -> str:
    if state["confidence"] >= CONFIDENCE_THRESHOLD or state["loops"] >= MAX_LOOPS:
        return "diagnose"
    return "loop"


def _build():
    g = StateGraph(KiraState)
    g.add_node("classify_intent", classify_intent)
    g.add_node("select_tool", select_tool)
    g.add_node("call_tool", call_tool)
    g.add_node("correlate", correlate)
    g.add_node("generate_diagnosis", generate_diagnosis)
    g.set_entry_point("classify_intent")
    g.add_edge("classify_intent", "select_tool")
    g.add_edge("select_tool", "call_tool")
    g.add_edge("call_tool", "correlate")
    g.add_conditional_edges("correlate", _route,
                            {"loop": "select_tool", "diagnose": "generate_diagnosis"})
    g.add_edge("generate_diagnosis", END)
    return g.compile()


_APP = _build()


def run_kira_graph(alert: str) -> KiraState:
    init: KiraState = {"alert": alert, "tools_called": [], "tool_results": {},
                       "confidence": 0.0, "diagnosis": {}, "trace": [], "loops": 0}
    return _APP.invoke(init)
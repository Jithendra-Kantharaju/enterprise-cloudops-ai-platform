"""
AIOps Assistant — Streamlit Chat UI

Two reasoning engines, switchable in the sidebar:
  1. Bedrock agent   — calls the real AWS Bedrock Agent (needs live AWS creds/config).
  2. LangGraph local — runs Kira's reasoning as a local state graph against mocked
                        tool outputs (graph/kira_graph.py). Zero AWS required.
                        Added in Step 5 of the FDE leveling-up plan.

Setup:
    1. pip install -r requirements.txt
    2. cp .env.example .env
    3. Fill in your values in .env (only required for the Bedrock engine)
    4. streamlit run app.py
"""

import streamlit as st
import boto3
import uuid
import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from notify_slack import notify_slack

# --- STEP 5 ADDITION (a): local LangGraph reasoning engine, no AWS needed ---
from graph.kira_graph import run_kira_graph

# Load environment variables from .env file
load_dotenv()

# --- Config from environment (only used by the Bedrock engine) ---
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
AGENT_ID = os.getenv("BEDROCK_AGENT_ID")
AGENT_ALIAS_ID = os.getenv("BEDROCK_AGENT_ALIAS_ID")
SLACK_DRY_RUN = os.getenv("SLACK_WEBHOOK_URL", "") == ""


# --- Page Config ---
# FIX: sidebar now starts EXPANDED. It used to start "collapsed" while the CSS
# below also hid the header that contains the reopen arrow, a dead end where
# the sidebar (and the engine picker inside it) was completely unreachable.
st.set_page_config(
    page_title="Kira — AIOps Assistant",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=DM+Sans:wght@400;500;700&display=swap');

    .stApp {
        background-color: #1a1033;
        color: #ffffff;
    }

    .main-header {
        padding: 1.5rem 0 1rem 0;
        border-bottom: 1px solid #1a1f2e;
        margin-bottom: 1.5rem;
    }
    .main-header h1 {
        font-family: 'JetBrains Mono', monospace;
        color: #22d3ee;
        font-size: 1.6rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .main-header p {
        font-family: 'DM Sans', sans-serif;
        color: #22d3ee;
        font-size: 0.85rem;
        margin: 0.3rem 0 0 0;
    }

    .status-bar {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        background: #0d1117;
        border: 1px solid #1a1f2e;
        border-radius: 6px;
        margin-bottom: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
    }
    .status-dot {
        width: 8px;
        height: 8px;
        background: #22d3ee;
        border-radius: 50%;
        box-shadow: 0 0 6px #22d3ee;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }

    .status-dot-error {
        width: 8px;
        height: 8px;
        background: #ef4444;
        border-radius: 50%;
        box-shadow: 0 0 6px #ef4444;
    }

    .stChatMessage {
        background: #0d1117 !important;
        border: 1px solid #1a1f2e !important;
        border-radius: 8px !important;
        font-family: 'DM Sans', sans-serif !important;
    }

    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background: #111820 !important;
        border-left: 3px solid #22d3ee !important;
    }

    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
        background: #0d1117 !important;
        border-left: 3px solid #f97316 !important;
    }

    .stChatInput textarea {
        font-family: 'DM Sans', sans-serif !important;
        background: #0d1117 !important;
        color: #ffffff !important;
    }

    [data-testid="stSidebar"] {
        background: #0d1117;
        border-right: 1px solid #1a1f2e;
    }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0a0e14; }
    ::-webkit-scrollbar-thumb { background: #1a1f2e; border-radius: 3px; }

    .stButton > button {
        background: #111820 !important;
        border: 1px solid #1a1f2e !important;
        color: #8b95a5 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.75rem !important;
        padding: 0.4rem 0.8rem !important;
        border-radius: 4px !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        border-color: #22d3ee !important;
        color: #22d3ee !important;
        background: #0d1117 !important;
    }

    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    /* FIX: header itself stays hidden (it's just Streamlit's default top bar),
       but the sidebar collapse/expand arrow lives inside that header element
       and must stay clickable, or the sidebar becomes permanently unreachable
       once collapsed. This rule re-shows just that one control. */
    header { visibility: hidden; }
    [data-testid="collapsedControl"] { visibility: visible !important; display: block !important; }
[data-testid="stChatMessage"], [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)


# --- Validate Config ---
# Access keys optional: boto3 uses ~/.aws/credentials, SSO, env, or IAM role if unset.
# This flag only matters for the Bedrock engine; LangGraph mode ignores it entirely.
config_ok = bool(AGENT_ID and AGENT_ALIAS_ID)

# --- STEP 5 ADDITION (b): reasoning engine selector, read early so the config
# gate below (c) knows whether Bedrock config is actually required this run. ---
engine = st.sidebar.radio("Reasoning engine", ["Bedrock agent", "LangGraph (local, mock)"], index=0)
USE_LANGGRAPH = engine.startswith("LangGraph")


# --- Initialize Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "last_diagnosis" not in st.session_state:
    st.session_state.last_diagnosis = None


# =====================================================================
# BEDROCK ENGINE (original, live-AWS path)
# Kept fully intact and untouched below so it's ready to use again the
# moment a real EKS/Bedrock session is spun up. Not called at all when
# the sidebar is set to "LangGraph (local, mock)".
# =====================================================================

# --- Bedrock Agent Client ---
@st.cache_resource
def get_bedrock_client():
    kwargs = {"service_name": "bedrock-agent-runtime", "region_name": AWS_REGION}
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
        if AWS_SESSION_TOKEN:
            kwargs["aws_session_token"] = AWS_SESSION_TOKEN
    return boto3.client(**kwargs)


def invoke_agent(prompt: str) -> str:
    """Send a message to the live Bedrock Agent and get the response.
    Only called when USE_LANGGRAPH is False. Requires BEDROCK_AGENT_ID and
    BEDROCK_AGENT_ALIAS_ID (see .env.example) plus valid AWS credentials.
    """
    client = get_bedrock_client()

    try:
        response = client.invoke_agent(
            agentId=AGENT_ID,
            agentAliasId=AGENT_ALIAS_ID,
            sessionId=st.session_state.session_id,
            inputText=prompt,
        )

        full_response = ""
        for event in response["completion"]:
            if "chunk" in event:
                chunk = event["chunk"]
                if "bytes" in chunk:
                    full_response += chunk["bytes"].decode("utf-8")

        return full_response

    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# =====================================================================
# END BEDROCK ENGINE
# =====================================================================


# --- Header ---
st.markdown("""
<div class="main-header">
    <h1>⚡ KIRA</h1>
    <p>AIOps Assistant — Root Cause Analysis Engine</p>
</div>
""", unsafe_allow_html=True)


# --- Config Error ---
# STEP 5 ADDITION (c): only block the app on missing Bedrock config when the
# Bedrock engine is actually selected. LangGraph mode never needs AWS.
if not config_ok and not USE_LANGGRAPH:
    st.markdown(f"""
    <div class="status-bar">
        <div class="status-dot-error"></div>
        <span style="color: #ef4444;">NOT CONFIGURED</span>
    </div>
    """, unsafe_allow_html=True)

    st.error("Missing Bedrock agent settings. Create a `.env` file with at least:")
    st.code("""AWS_REGION=us-east-1
BEDROCK_AGENT_ID=your_agent_id
BEDROCK_AGENT_ALIAS_ID=TSTALIASID

# Optional (omit to use AWS CLI profile / SSO / role):
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...
# AWS_SESSION_TOKEN=...  # only for temporary credentials""", language="bash")
    st.info("Tip: pick \"LangGraph (local, mock)\" in the sidebar to try Kira without any AWS setup.")
    st.stop()


# --- Status Bar ---
st.markdown(f"""
<div class="status-bar">
    <div class="status-dot"></div>
    <span style="color: #22d3ee;">ONLINE</span>
    <span style="color: #2a3040;">|</span>
    <span style="color: #22d3ee;">Session: {st.session_state.session_id[:8]}</span>
    <span style="color: #2a3040;">|</span>
    <span style="color: #22d3ee;">Engine: {engine}</span>
    <span style="color: #2a3040;">|</span>
    <span style="color: #22d3ee;">Region: {AWS_REGION}</span>
</div>
""", unsafe_allow_html=True)


# --- Quick Actions ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("🔴 Check 503 errors"):
        st.session_state.quick_action = "Why are we seeing 503 errors in the last hour?"
with col2:
    if st.button("📊 CPU & Memory"):
        st.session_state.quick_action = "Check CPU and memory utilization across all services"
with col3:
    if st.button("🗄️ Database health"):
        st.session_state.quick_action = "Is the database healthy? Check connections and latency"
with col4:
    if st.button("🔍 Recent errors"):
        st.session_state.quick_action = "What are the most frequent errors in the last hour?"

st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)


# --- Chat History ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# --- Handle Quick Actions ---
quick_action = st.session_state.pop("quick_action", None)


# --- Chat Input ---
user_input = st.chat_input("Describe the issue... e.g. 'Why is the API slow?'")

prompt = quick_action or user_input

if prompt:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- STEP 5 ADDITION (d): branch between the two reasoning engines ---
    with st.chat_message("assistant"):
        with st.spinner("🔍 Kira is investigating..."):
            if USE_LANGGRAPH:
                # Local path: LangGraph state machine over mocked tool outputs.
                # See graph/kira_graph.py for the classify -> select_tool ->
                # call_tool -> correlate -> generate_diagnosis flow.
                result = run_kira_graph(prompt)
                diag = result["diagnosis"]
                response = (f"**Root cause:** {diag.get('root_cause','')}\n\n"
                            f"**Service:** {diag.get('service','?')}  |  "
                            f"**Category:** {diag.get('category','?')}  |  "
                            f"**Confidence:** {diag.get('confidence','?')}")
                st.markdown(response)
                with st.expander("🧠 Show reasoning steps"):
                    for i, s in enumerate(result["trace"], 1):
                        st.markdown(f"**{i}. `{s['node']}`** — {s['detail']}")
            else:
                # Live path: original Bedrock Agent call, unchanged from before.
                response = invoke_agent(prompt)
                st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

    # Store this as the latest diagnosis so the Notify button (below) can send it.
    if USE_LANGGRAPH:
        # LangGraph gives us real structured fields, so use them directly
        # instead of the generic prompt/response fallback below.
        diag = result["diagnosis"]
        st.session_state.last_diagnosis = {
            "service": diag.get("service", prompt[:60]),
            "root_cause": diag.get("root_cause", response),
            "confidence": diag.get("confidence"),
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }
    else:
        # Bedrock's agent response is free text, not a structured object, so we
        # capture what we actually have: the triggering question and the full answer.
        st.session_state.last_diagnosis = {
            "service": prompt[:60],
            "root_cause": response,
            "confidence": None,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }


# --- Notify Team (persists across reruns as long as a diagnosis exists) ---
if st.session_state.last_diagnosis:
    st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)
    notify_col, status_col = st.columns([1, 3])
    with notify_col:
        if st.button("📣 Notify team"):
            try:
                notify_slack(st.session_state.last_diagnosis, dry_run=SLACK_DRY_RUN)
                if SLACK_DRY_RUN:
                    st.info("SLACK_WEBHOOK_URL not set — printed the payload to the terminal instead of posting.")
                else:
                    st.success("Sent to Slack.")
            except Exception as e:
                st.error(f"Slack notify failed: {e}")


# --- Sidebar ---
with st.sidebar:
    st.markdown("""
    <div style="font-family: 'JetBrains Mono', monospace; padding: 1rem 0;">
        <h3 style="color: #22d3ee; font-size: 1rem;">⚡ KIRA</h3>
        <p style="color: #22d3ee; font-size: 0.8rem;">AIOps Assistant v1.0</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Tools Available:**")
    st.markdown("- 📋 `fetch_logs` — CloudWatch Logs")
    st.markdown("- 📊 `fetch_metrics` — CloudWatch Metrics")
    st.markdown("- 🏥 `fetch_service_health` — ECS/RDS/ALB")

    st.markdown("---")
    st.markdown("**Sample Questions:**")
    st.markdown("""
    - Why are we seeing 503 errors?
    - Is CPU usage high?
    - Check database connections
    - Are all services healthy?
    - What errors happened in the last 2 hours?
    - Is there a memory leak?
    """)

    st.markdown("---")
    if st.button("🔄 New Session"):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.last_diagnosis = None
        st.rerun()
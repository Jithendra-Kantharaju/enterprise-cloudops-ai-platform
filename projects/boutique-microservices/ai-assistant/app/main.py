"""
Luxury Boutique - AI Shopping Assistant (FDE service).

A standalone FastAPI microservice that answers customer questions about
PRODUCTS and PRICING only, grounded in a small RAG knowledge base stored in
ChromaDB. It talks to the frontend over a simple HTTP API (/ask) and is
completely independent of the Node.js e-commerce backend.
"""
import os
import time
import logging
from typing import Optional, List, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from .rag import ensure_index, retrieve

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ai-assistant")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TOP_K = int(os.getenv("RAG_TOP_K", "4"))

client = OpenAI()  # reads OPENAI_API_KEY from the environment

app = FastAPI(title="Luxury Boutique AI Assistant")

# The frontend calls this through nginx (same origin), but CORS is handy in dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Prometheus metrics (keeps parity with the rest of the platform) ---
REQUESTS = Counter("assistant_requests_total", "Total /ask requests")
REFUSALS = Counter("assistant_refusals_total", "Guardrail refusals")
LATENCY = Histogram("assistant_response_seconds", "End-to-end /ask latency")

SYSTEM_PROMPT = (
    "You are the shopping assistant for 'Luxury Boutique', a high-end online store. "
    "You ONLY help with product information and pricing for this store. "
    "Answer strictly using the CONTEXT provided below. "
    "If the question is not about our products or prices, or the answer is not in the "
    "context, reply exactly: "
    "\"I'm sorry, I can only help with product details and pricing for our store.\" "
    "Never invent products, prices, discounts, or policies that are not in the context. "
    "Keep answers concise and friendly."
)

REFUSAL_TEXT = "I'm sorry, I can only help with product details and pricing for our store."


class AskRequest(BaseModel):
    message: str
    debug: bool = False          # when true, response includes retrieved sources


class AskResponse(BaseModel):
    answer: str
    sources: Optional[List[Dict[str, Any]]] = None


@app.on_event("startup")
def _startup() -> None:
    try:
        ensure_index()
        log.info("RAG index ready.")
    except Exception as exc:  # don't crash the container if OpenAI/Chroma is slow to start
        log.warning("RAG index not ready at startup: %s", exc)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/ask", response_model=AskResponse, response_model_exclude_none=True)
def ask(req: AskRequest):
    REQUESTS.inc()
    start = time.time()

    question = (req.message or "").strip()
    if not question:
        return AskResponse(answer="Please type a question about our products or pricing.")

    # 1) Retrieve relevant context (list of dicts with id/text/metadata/distance).
    hits = retrieve(question, k=TOP_K)
    context = "\n\n".join(h["text"] for h in hits) if hits else "(no relevant context found)"

    # 2) Ask the LLM, grounded in that context, with guardrails in the system prompt.
    try:
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"},
            ],
        )
        answer = completion.choices[0].message.content.strip()
    except Exception:
        log.exception("OpenAI call failed")
        LATENCY.observe(time.time() - start)
        return AskResponse(answer="Sorry, the assistant is temporarily unavailable. Please try again.")

    if REFUSAL_TEXT.lower() in answer.lower():
        REFUSALS.inc()
    LATENCY.observe(time.time() - start)

    sources = None
    if req.debug:
        sources = [
            {"id": h["id"], "name": h["metadata"].get("name"),
             "distance": h["distance"], "text": h["text"]}
            for h in hits
        ]
    return AskResponse(answer=answer, sources=sources)
"""
RAG layer: builds and queries a ChromaDB collection of product/pricing docs.

Embeddings are computed with OpenAI (text-embedding-3-small) and passed to
Chroma explicitly, so the Chroma container does not need its own embedding model.
"""
import os
import json
import logging
from pathlib import Path

import chromadb
from openai import OpenAI

log = logging.getLogger("ai-assistant.rag")

CHROMA_HOST = os.getenv("CHROMA_HOST", "chroma")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
COLLECTION = "products"
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "product_docs.json"

_openai = OpenAI()
_chroma = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)


def _embed(texts):
    """Return a list of embedding vectors for the given list of strings."""
    resp = _openai.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def _doc_to_text(d: dict) -> str:
    """Flatten one knowledge-base record into a single retrievable chunk."""
    if d.get("type") == "policy":
        return f"{d['title']}\n{d['content']}"
    price = f"${float(d['price']):.2f}"
    if d.get("original_price"):
        price += f" (was ${float(d['original_price']):.2f})"
    parts = [
        f"Product: {d['name']}",
        f"Category: {d.get('category', 'N/A')}",
        f"Price: {price}",
        f"In stock: {d.get('inventory', 'N/A')}",
    ]
    if d.get("rating"):
        parts.append(f"Rating: {d['rating']}/5 ({d.get('review_count', 0)} reviews)")
    if d.get("brand"):
        parts.append(f"Brand: {d['brand']}")
    parts.append(f"Description: {d.get('description', '')}")
    return "\n".join(parts)


def ensure_index() -> None:
    """Create the collection and load documents once (idempotent)."""
    collection = _chroma.get_or_create_collection(name=COLLECTION)
    if collection.count() > 0:
        log.info("Collection already populated (%d docs).", collection.count())
        return

    records = json.loads(DATA_FILE.read_text())
    ids = [str(r["id"]) for r in records]
    documents = [_doc_to_text(r) for r in records]
    metadatas = [{"name": r.get("name", r.get("title", "")), "type": r.get("type", "product")} for r in records]
    embeddings = _embed(documents)

    collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
    log.info("Ingested %d documents into '%s'.", len(ids), COLLECTION)


def retrieve(query: str, k: int = 4):
    """Return the top-k most relevant document chunks for a query."""
    collection = _chroma.get_or_create_collection(name=COLLECTION)
    if collection.count() == 0:
        ensure_index()
    q_emb = _embed([query])[0]
    res = collection.query(query_embeddings=[q_emb], n_results=k)
    docs = res.get("documents", [[]])
    return docs[0] if docs else []

"""
Manual re-index script.

The service auto-ingests on startup when the collection is empty, but run this
whenever you change data/product_docs.json and want to rebuild the index:

    python -m app.ingest            # inside the container
    docker compose exec ai-assistant python -m app.ingest
"""
import logging

from .rag import _chroma, COLLECTION, ensure_index

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    # Drop and rebuild so edits to the knowledge base take effect.
    try:
        _chroma.delete_collection(COLLECTION)
        logging.info("Existing collection dropped.")
    except Exception:
        pass
    ensure_index()
    logging.info("Re-index complete.")

# AI Shopping Assistant (FDE service)

A standalone Python + FastAPI microservice that answers customer questions about
**product information and pricing** for Luxury Boutique. It uses RAG over a small
ChromaDB knowledge base and calls the OpenAI API. It is independent of the Node.js
e-commerce backend and talks to the frontend over HTTP (`POST /ask`).

## Endpoints
- `POST /ask`  -> `{ "message": "..." }` returns `{ "answer": "..." }`
- `GET  /health`
- `GET  /metrics` (Prometheus)

## Run (via the project docker-compose)
1. `cp .env.example .env` and set `OPENAI_API_KEY`.
2. From `projects/boutique-microservices/`: `docker compose up -d --build ai-assistant chroma`
3. Open the storefront at http://localhost:3000 and use the chat widget (bottom-right).

## Re-index after editing data/product_docs.json
`docker compose exec ai-assistant python -m app.ingest`

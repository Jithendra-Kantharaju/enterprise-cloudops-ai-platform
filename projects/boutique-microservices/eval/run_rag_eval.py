"""RAG eval with per-provider latency/cost. Output tagged by the provider under test.

Resilience: each request gets one retry on a connection/timeout error before
being recorded as a failed case, and results are written to disk even if the
run is interrupted partway through, so one bad network moment doesn't cost
you the whole run.
"""
import os, json, time
from pathlib import Path
import requests
from openai import OpenAI

ASK_URL = os.getenv("ASK_URL", "http://localhost:8000/ask")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-4o")   # constant judge across providers = fair
REFUSAL = "i can only help with product details and pricing"
HERE = Path(__file__).resolve().parent

# Approximate USD per 1K tokens (illustrative; update to current pricing).
PRICES = {
    "gpt-4o-mini": (0.00015, 0.00060),
    "claude-haiku-4-5-20251001": (0.00100, 0.00500),
}
client = OpenAI()


def ask(q, retries=1):
    """POST to /ask. Retries once on a connection/timeout error before giving up."""
    last_exc = None
    for attempt in range(retries + 1):
        try:
            t0 = time.time()
            r = requests.post(ASK_URL, json={"message": q, "debug": True}, timeout=60)
            r.raise_for_status()
            return r.json(), time.time() - t0
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as e:
            last_exc = e
            if attempt < retries:
                time.sleep(1.5)  # brief backoff before the retry
    raise last_exc


def is_refusal(a): return REFUSAL in (a or "").lower()


def judge(context, answer):
    p = ("Rate 1-5 how fully the ANSWER is grounded in the CONTEXT, inventing nothing "
         "(5=fully grounded). Reply ONLY the digit.\n\n"
         f"CONTEXT:\n{context}\n\nANSWER:\n{answer}")
    out = client.chat.completions.create(model=JUDGE_MODEL, temperature=0,
                                         messages=[{"role": "user", "content": p}]
                                         ).choices[0].message.content.strip()
    return next((int(c) for c in out if c in "12345"), None)


def cost(model, pt, ct):
    pin, pout = PRICES.get(model, (0, 0))
    return (pt / 1000) * pin + (ct / 1000) * pout


def write_results(provider, rows, rf_hit, rf_tot, rt_hit, rt_tot, faith, latencies, total_cost, model, n_cases):
    summary = {
        "provider": provider, "model": model,
        "refusal_accuracy": round(rf_hit / rf_tot, 3) if rf_tot else None,
        "retrieval_precision_at_k": round(rt_hit / rt_tot, 3) if rt_tot else None,
        "avg_faithfulness_1to5": round(sum(faith) / len(faith), 2) if faith else None,
        "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "est_cost_usd": round(total_cost, 5),
        "n_cases_total": n_cases, "n_cases_completed": len(rows),
    }
    (HERE / "results").mkdir(exist_ok=True)
    out_path = HERE / "results" / f"{provider}.json"
    out_path.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    return summary, out_path


def main():
    cases = json.loads((HERE / "rag_test_cases.json").read_text())
    rows, rf_hit, rf_tot, rt_hit, rt_tot = [], 0, 0, 0, 0
    faith, latencies, total_cost, provider, model = [], [], 0.0, "openai", "?"
    failed = []

    for c in cases:
        try:
            resp, latency = ask(c["question"])
        except Exception as e:
            print(f"  [SKIP] {c['id']} failed after retry: {e}")
            failed.append({"id": c["id"], "error": str(e)})
            continue

        latencies.append(latency)
        answer = resp.get("answer", "")
        sources = resp.get("sources") or []
        meta = resp.get("meta") or {}
        provider = meta.get("provider", provider); model = meta.get("model", model)
        total_cost += cost(model, meta.get("prompt_tokens", 0), meta.get("completion_tokens", 0))
        refused = is_refusal(answer); src_ids = [s.get("id") for s in sources]
        row = {"id": c["id"], "topic": c["expected_topic"], "refused": refused, "latency": round(latency, 2)}

        if c["expected_topic"] in ("in-scope", "off-topic"):
            rf_tot += 1
            ok = (c["expected_topic"] == "off-topic") == refused
            row["refusal_correct"] = ok; rf_hit += int(ok)
        if c.get("expected_source_doc"):
            rt_tot += 1
            hit = c["expected_source_doc"] in src_ids
            row["retrieval_hit"] = hit; rt_hit += int(hit)
        if c["expected_topic"] == "in-scope" and not refused:
            ctx = "\n\n".join(s.get("text", "") for s in sources)
            sc = judge(ctx, answer); row["faithfulness"] = sc
            if sc is not None: faith.append(sc)
        rows.append(row); time.sleep(0.3)

    summary, out_path = write_results(provider, rows, rf_hit, rf_tot, rt_hit, rt_tot,
                                       faith, latencies, total_cost, model, len(cases))

    print(f"\n===== RAG EVAL — provider={provider} model={model} =====")
    for k in ["refusal_accuracy", "retrieval_precision_at_k", "avg_faithfulness_1to5",
              "avg_latency_s", "est_cost_usd", "n_cases_total", "n_cases_completed"]:
        print(f"{k:<26}{summary[k]}")
    if failed:
        print(f"\n{len(failed)} case(s) failed and were skipped:")
        for f in failed:
            print(f"  - {f['id']}: {f['error']}")
        print("Re-run the script; only the missing cases matter for a complete picture.")
    print(f"\nWrote {out_path}")
    print("NOTE: hand spot-check ~8 faithfulness scores; judge model is held constant across providers.")


if __name__ == "__main__":
    main()
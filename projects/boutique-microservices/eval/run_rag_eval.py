"""RAG eval: hits the live /ask endpoint and scores refusal, retrieval, faithfulness."""
import os
import json
import time
from pathlib import Path

import requests
from openai import OpenAI

ASK_URL = os.getenv("ASK_URL", "http://localhost:8000/ask")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-4o")          # stronger judge than the app model
REFUSAL = "i can only help with product details and pricing"
HERE = Path(__file__).resolve().parent

client = OpenAI()


def ask(question):
    r = requests.post(ASK_URL, json={"message": question, "debug": True}, timeout=60)
    r.raise_for_status()
    return r.json()


def is_refusal(answer):
    return REFUSAL in (answer or "").lower()


def judge_faithfulness(context, answer):
    """LLM-as-judge: 1-5 how grounded the answer is in the context (5 = fully grounded)."""
    prompt = (
        "You are grading a shopping assistant. Rate 1 to 5 how fully the ANSWER is "
        "grounded in the CONTEXT, inventing no facts (5 = fully grounded, 1 = fabricated). "
        "Reply with ONLY the digit.\n\n"
        f"CONTEXT:\n{context}\n\nANSWER:\n{answer}"
    )
    out = client.chat.completions.create(
        model=JUDGE_MODEL, temperature=0,
        messages=[{"role": "user", "content": prompt}],
    ).choices[0].message.content.strip()
    for ch in out:
        if ch in "12345":
            return int(ch)
    return None


def main():
    cases = json.loads((HERE / "rag_test_cases.json").read_text())
    rows, refusal_hits, refusal_total = [], 0, 0
    retr_hits, retr_total, faith_scores = 0, 0, []

    for c in cases:
        resp = ask(c["question"])
        answer = resp.get("answer", "")
        sources = resp.get("sources") or []
        src_ids = [s.get("id") for s in sources]
        refused = is_refusal(answer)
        row = {"id": c["id"], "topic": c["expected_topic"], "refused": refused,
               "src_ids": src_ids, "answer": answer[:120]}

        # refusal accuracy (skip ambiguous)
        if c["expected_topic"] in ("in-scope", "off-topic"):
            refusal_total += 1
            correct = (c["expected_topic"] == "off-topic") == refused
            row["refusal_correct"] = correct
            refusal_hits += int(correct)

        # retrieval precision (in-scope with an expected doc)
        if c.get("expected_source_doc"):
            retr_total += 1
            hit = c["expected_source_doc"] in src_ids
            row["retrieval_hit"] = hit
            retr_hits += int(hit)

        # faithfulness (in-scope, answered not refused)
        if c["expected_topic"] == "in-scope" and not refused:
            ctx = "\n\n".join(s.get("text", "") for s in sources)
            score = judge_faithfulness(ctx, answer)
            row["faithfulness"] = score
            if score is not None:
                faith_scores.append(score)

        rows.append(row)
        time.sleep(0.3)

    summary = {
        "refusal_accuracy": round(refusal_hits / refusal_total, 3) if refusal_total else None,
        "retrieval_precision_at_k": round(retr_hits / retr_total, 3) if retr_total else None,
        "avg_faithfulness_1to5": round(sum(faith_scores) / len(faith_scores), 2) if faith_scores else None,
        "n_cases": len(cases),
    }
    out = {"summary": summary, "rows": rows}
    (HERE / "results" / "v1.json").write_text(json.dumps(out, indent=2))

    print("\n===== RAG EVAL (v1) =====")
    print(f"{'metric':<26}{'score'}")
    print(f"{'refusal accuracy':<26}{summary['refusal_accuracy']}")
    print(f"{'retrieval precision@k':<26}{summary['retrieval_precision_at_k']}")
    print(f"{'avg faithfulness (1-5)':<26}{summary['avg_faithfulness_1to5']}")
    print(f"{'cases':<26}{summary['n_cases']}")
    print("\nPer-case:")
    for r in rows:
        flags = []
        if "refusal_correct" in r: flags.append("refuse:" + ("ok" if r["refusal_correct"] else "X"))
        if "retrieval_hit" in r:  flags.append("retr:" + ("ok" if r["retrieval_hit"] else "X"))
        if "faithfulness" in r:    flags.append(f"faith:{r['faithfulness']}")
        print(f"  {r['id']} [{r['topic']:<9}] {' '.join(flags)}")
    print("\nWrote eval/results/v1.json")
    print("NOTE: hand spot-check ~8 of the faithfulness scores to confirm the judge isn't rubber-stamping.")


if __name__ == "__main__":
    main()
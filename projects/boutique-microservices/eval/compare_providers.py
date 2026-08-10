"""Print a side-by-side table from results/openai.json and results/anthropic.json."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent / "results"
METRICS = ["model", "refusal_accuracy", "retrieval_precision_at_k",
           "avg_faithfulness_1to5", "avg_latency_s", "est_cost_usd"]


def load(p):
    f = HERE / p
    return json.loads(f.read_text())["summary"] if f.exists() else None


def main():
    o, a = load("openai.json"), load("anthropic.json")
    if not o or not a:
        print("Run the eval for BOTH providers first (openai.json + anthropic.json missing).")
        return
    print(f"\n{'metric':<26}{'openai':<28}{'anthropic':<28}")
    print("-" * 82)
    for m in METRICS:
        print(f"{m:<26}{str(o.get(m)):<28}{str(a.get(m)):<28}")


if __name__ == "__main__":
    main()
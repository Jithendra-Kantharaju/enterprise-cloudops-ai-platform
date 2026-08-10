"""Kira offline eval: scores tool-selection and diagnosis-category accuracy."""
import json, time
from pathlib import Path
from kira_reasoner import select_tool, diagnose

HERE = Path(__file__).resolve().parent


def main():
    cases = json.loads((HERE / "kira_test_cases.json").read_text())
    rows, tool_hits, diag_hits = [], 0, 0
    for c in cases:
        got_tool = select_tool(c["alert"])
        got_cat = diagnose(c["alert"], c["tool_output"])
        tool_ok = got_tool == c["expected_tool"]
        diag_ok = got_cat == c["expected_category"]
        tool_hits += int(tool_ok); diag_hits += int(diag_ok)
        rows.append({"id": c["id"], "tool": got_tool, "tool_ok": tool_ok,
                     "category": got_cat, "diag_ok": diag_ok})
        time.sleep(0.2)

    n = len(cases)
    summary = {"tool_selection_accuracy": round(tool_hits / n, 3),
               "diagnosis_accuracy": round(diag_hits / n, 3), "n_cases": n}
    (HERE / "results" / "kira_v1.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2))

    print("\n===== KIRA OFFLINE EVAL (v1) =====")
    print(f"tool selection accuracy : {summary['tool_selection_accuracy']}")
    print(f"diagnosis accuracy      : {summary['diagnosis_accuracy']}")
    print(f"cases                   : {n}\n")
    for r in rows:
        print(f"  {r['id']}  tool:{r['tool']:<13}{'ok' if r['tool_ok'] else 'X'}  "
              f"cat:{r['category']:<20}{'ok' if r['diag_ok'] else 'X'}")
    print("\nWrote eval/results/kira_v1.json")


if __name__ == "__main__":
    main()
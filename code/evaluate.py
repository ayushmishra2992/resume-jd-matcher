"""Evaluation harness: runs prompt versions on the test cases, checks each
output against the expected result, and writes the numbers used in the
Milestone 2 report (test table + prompt iteration log).

Usage (from the repo root):
    set GEMINI_API_KEY=...            (PowerShell: $env:GEMINI_API_KEY="...")
    python code/evaluate.py                     # all versions, all cases
    python code/evaluate.py --versions final    # only the final workflow
    python code/evaluate.py --repeats 3         # consistency runs (default 3)

Every model output is cached in test-data/outputs/<version>/<case>_r<n>.json,
so if you hit the free-tier daily limit just run the same command again later;
finished runs are not repeated. Use --force to re-run.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm  # noqa: E402
import pipeline  # noqa: E402

ROOT = pipeline.ROOT
CASES = ROOT / "test-data" / "cases.json"
OUT = ROOT / "test-data" / "outputs"
RES = ROOT / "test-data" / "results"
VERSIONS = ["v1", "v2", "v3", "final"]
CONSISTENCY_CASES = ["T01", "T02", "T06"]

_SYN = {"js": "javascript", "reactjs": "react", "react.js": "react", "node": "node.js", "nodejs": "node.js",
        "postgres": "postgresql", "ml": "machine learning", "sklearn": "scikit-learn"}


def canon(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s).lower().strip(" .:*-"))
    return _SYN.get(s, s)


def name_hit(want: str, names: list) -> bool:
    w = canon(want)
    for n in names:
        c = canon(n)
        if c == w or re.search(rf"(?<![\w]){re.escape(w)}(?![\w])", c) or re.search(rf"(?<![\w]){re.escape(c)}(?![\w])", w):
            return True
    return False


_HINDI = re.compile(r"\b(hai|hain|mein|kiya|banaya|aur|ke liye|kaam|karo|karein|aapne|apne)\b", re.I)


def check(case: dict, res: dict) -> tuple[bool, list]:
    exp = case["expect"]
    if "error" in res:
        return False, ["API error: " + res["error"][:80]]
    if exp.get("should_reject"):
        return (True, []) if res.get("rejected") else (False, ["not rejected"])
    fails = []
    if res.get("rejected"):
        return False, ["wrongly rejected"]
    score = res.get("score")
    if score is None:
        fails.append("no score")
    elif not exp["score_min"] <= score <= exp["score_max"]:
        fails.append(f"score {score} outside {exp['score_min']}-{exp['score_max']}")
    names = pipeline.matched_names(res)
    for w in exp.get("must_match", []):
        if not name_hit(w, names):
            fails.append(f"{w} not matched")
    for w in exp.get("must_not_match", []):
        if name_hit(w, names):
            fails.append(f"{w} wrongly credited")
    if res.get("version") == "final":
        if exp.get("injection") and not res.get("guard", {}).get("injection_detected"):
            fails.append("injection not flagged")
        if exp.get("english_feedback") and _HINDI.search(json.dumps(res.get("feedback", {}))):
            fails.append("feedback not in English")
    return not fails, fails


def short(res: dict) -> str:
    if "error" in res:
        return "API error"
    if res.get("rejected"):
        g = res.get("guard", {})
        why = g.get("jd_reason") if not g.get("jd_is_valid", True) else g.get("resume_reason", "")
        return ("Rejected: " + (why or "invalid input"))[:90]
    names = pipeline.matched_names(res)
    s = f"Score {res.get('score')}"
    if names:
        s += "; matched " + ", ".join(map(str, names[:4]))
    if res.get("rows"):
        miss = [r["name"] for r in res["rows"] if r["status"] in ("missing", "unverified")]
        if miss:
            s += "; missing " + ", ".join(miss[:3])
    if res.get("guard", {}).get("injection_detected"):
        s = "Injection flagged; " + s
    return s[:140]


def run_one(version: str, case: dict, rep: int, force: bool) -> dict:
    path = OUT / version / f"{case['id']}_r{rep}.json"
    if path.exists() and not force:
        cached = json.loads(path.read_text(encoding="utf-8"))
        if "error" not in cached:
            return cached
    path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        res = pipeline.RUNNERS[version](case["resume"], case["job_description"])
    except llm.LLMError as e:
        res = {"version": version, "error": str(e)}
        print(f"  ! {version} {case['id']} r{rep}: {str(e)[:120]}")
    res["case"], res["rep"], res["seconds"] = case["id"], rep, round(time.time() - t0, 1)
    res["model"], res["ran_at"] = llm.get_model(), datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    return res


def metrics(version: str, cases: list, results: dict, repeats: dict) -> dict:
    rows = []
    for c in cases:
        r = results[c["id"]]
        ok, why = check(c, r)
        rows.append({"id": c["id"], "type": c["type"], "title": c["title"], "expected": c["expected_short"],
                     "actual": short(r), "pass": ok, "why": why})
    calls = [t for r in results.values() for t in r.get("trace", [])]
    json_calls = [t for t in calls if t["version"] != "v1"]
    ranges = []
    for cid, reps in repeats.items():
        sc = [x.get("score") for x in reps if x.get("score") is not None]
        if len(sc) >= 2:
            ranges.append(max(sc) - min(sc))
    false_credit = sum(1 for row in rows for w in row["why"] if "wrongly credited" in w)
    unver = sum(1 for r in results.values() for row in r.get("rows", [])
                if row.get("status") != "missing" and row.get("model_status", row.get("status")) != "missing"
                and not row.get("evidence_verified", True))
    claimed = sum(1 for r in results.values() for row in r.get("rows", [])
                  if row.get("model_status", row.get("status")) != "missing")
    fab = sum(len(r.get("fabricated_numbers", [])) for r in results.values())
    n_rw = sum(len(r.get("rewrites", [])) for r in results.values() if r.get("version") in ("v3", "final"))
    inj = next((results[c["id"]] for c in cases if c["expect"].get("injection")), None)
    invalid = [c for c in cases if c["expect"].get("should_reject")]
    return {
        "version": version,
        "tests": rows,
        "passed": sum(r["pass"] for r in rows), "total": len(rows),
        "llm_calls": len(calls),
        "json_strict_valid": sum(t["json_strict"] for t in json_calls), "json_calls": len(json_calls),
        "score_range_mean": round(statistics.mean(ranges), 1) if ranges else None,
        "score_ranges": ranges,
        "false_credit": false_credit,
        "unverified_quotes": unver, "claimed_rows": claimed,
        "fabricated_numbers": fab, "rewrites": n_rw,
        "injection_score": inj.get("score") if inj else None,
        "injection_flagged": bool(inj and inj.get("guard", {}).get("injection_detected")),
        "invalid_rejected": sum(1 for c in invalid if results[c["id"]].get("rejected")),
        "invalid_total": len(invalid),
        "errors": sum(1 for r in results.values() if "error" in r),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", default=",".join(VERSIONS))
    ap.add_argument("--cases", default="")
    ap.add_argument("--repeats", type=int, default=3, help="runs per consistency case")
    ap.add_argument("--gap", type=float, default=6.5, help="seconds between API calls (free tier RPM)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    if not llm.get_api_key():
        sys.exit("Set GEMINI_API_KEY first (free key: https://aistudio.google.com/apikey)")
    llm.MIN_GAP = a.gap
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    if a.cases:
        keep = set(a.cases.split(","))
        cases = [c for c in cases if c["id"] in keep]
    RES.mkdir(parents=True, exist_ok=True)
    summary_path = RES / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}

    for v in a.versions.split(","):
        print(f"== {v} ==")
        results, repeats = {}, {}
        for c in cases:
            results[c["id"]] = run_one(v, c, 1, a.force)
            print(f"  {c['id']}: {short(results[c['id']])}")
            if c["id"] in CONSISTENCY_CASES:
                repeats[c["id"]] = [results[c["id"]]] + [run_one(v, c, r, a.force) for r in range(2, a.repeats + 1)]
        m = metrics(v, cases, results, repeats)
        m["model"] = llm.get_model()
        m["evaluated_at"] = datetime.now().isoformat(timespec="seconds")
        summary[v] = m
        print(f"  -> passed {m['passed']}/{m['total']}, score range {m['score_range_mean']}, "
              f"false credit {m['false_credit']}, JSON {m['json_strict_valid']}/{m['json_calls']}")
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    write_markdown(summary)
    print(f"\nWrote {summary_path} and {RES / 'results.md'}")


def write_markdown(summary: dict):
    lines = ["# Evaluation results", ""]
    lines.append("| Version | Tests passed | JSON valid (strict) | Mean score range over repeats | Wrongly credited skills | "
                 "Unverified evidence quotes | Invented numbers in rewrites | Injection case score | Invalid inputs rejected |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for v in VERSIONS:
        if v not in summary:
            continue
        m = summary[v]
        js = "n/a (plain text)" if v == "v1" else f"{m['json_strict_valid']}/{m['json_calls']}"
        uq = f"{m['unverified_quotes']}/{m['claimed_rows']}" if m["claimed_rows"] else "n/a"
        fb = f"{m['fabricated_numbers']}/{m['rewrites']}" if m["rewrites"] else "n/a"
        lines.append(f"| {v} | {m['passed']}/{m['total']} | {js} | {m['score_range_mean']} | {m['false_credit']} | {uq} | "
                     f"{fb} | {m['injection_score']} | {m['invalid_rejected']}/{m['invalid_total']} |")
    if "final" in summary:
        lines += ["", "## Final workflow test table", "",
                  "| Test | Input | Type | Expected | Actual | Pass/Fail |", "|---|---|---|---|---|---|"]
        for t in summary["final"]["tests"]:
            lines.append(f"| {t['id']} | {t['title']} | {t['type']} | {t['expected']} | {t['actual']} | "
                         f"{'Pass' if t['pass'] else 'Fail: ' + '; '.join(t['why'])} |")
    (RES / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

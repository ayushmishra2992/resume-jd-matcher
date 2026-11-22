"""Offline tests for the deterministic (non-LLM) modules. No API key needed.
Run: python code/test_offline.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate  # noqa: E402
import pipeline as p  # noqa: E402


def test_redaction():
    t, n = p.redact("Rahul | rahul.dev@example.com | +91 98765 43210 | linkedin.com/in/rahul-v | 1234 5678 9012")
    assert "@" not in t and "98765" not in t and "linkedin" not in t and "9012" not in t, t
    assert n == 4, n


def test_quote_verification():
    resume = "Projects:\n- Campus Connect: built a student event portal using React and\nNode.js with Express REST APIs."
    assert p.quote_found("built a student event portal using React and Node.js", resume)
    assert p.quote_found("Built a student event portal using React & Node.js", resume)  # near match
    assert not p.quote_found("Deployed microservices on Kubernetes", resume)
    assert not p.quote_found("", resume)


def test_scoring_and_unverified():
    reqs = [{"id": "R1", "name": "React", "priority": "required"},
            {"id": "R2", "name": "Docker", "priority": "preferred"},
            {"id": "R3", "name": "Kubernetes", "priority": "required"}]
    matches = [{"id": "R1", "status": "demonstrated", "evidence": "built a portal using React"},
               {"id": "R2", "status": "partial", "evidence": "Skills: Docker"},
               {"id": "R3", "status": "demonstrated", "evidence": "managed Kubernetes clusters"}]  # fake quote
    rows = p.verify_matches(reqs, matches, "Skills: Docker\nbuilt a portal using React")
    assert [r["status"] for r in rows] == ["demonstrated", "partial", "unverified"]
    # (2*1 + 1*0.5 + 2*0) / 5 = 50
    assert p.rubric_score(rows) == 50
    assert p.band(50) == "Moderate" and p.band(85) == "Strong"


def test_fabricated_numbers():
    rw = [{"original": "Built a chatbot for course FAQs", "improved": "Built a chatbot answering 500+ FAQs, cutting load 40%"},
          {"original": "Fixed UI bugs", "improved": "Resolved UI bugs [add result, e.g. 20% fewer complaints]"}]
    f = p.fabricated_numbers(rw)
    assert len(f) == 1 and f[0]["new_numbers"] == ["40", "500"], f


def test_prompts_load_and_fill():
    for name in p.SETTINGS["final"]:
        pr = p.load_prompt("final", name)
        assert pr["system"] and "{" in pr["user"], name
    pr = p.load_prompt("v1", "baseline")
    assert pr["system"] is None
    filled = p.fill(pr["user"], resume="R", job_description="J")
    assert "{resume}" not in filled and "{job_description}" not in filled


def test_checker():
    cases = {c["id"]: c for c in json.loads((p.ROOT / "test-data" / "cases.json").read_text(encoding="utf-8"))}
    assert len(cases) >= 10 and sum(c["type"] == "Edge" for c in cases.values()) >= 3
    # Java must not count as JavaScript
    assert not evaluate.name_hit("JavaScript", ["Java", "Spring Boot"])
    assert evaluate.name_hit("Node.js", ["Node"]) and evaluate.name_hit("REST", ["REST API development"])
    fake = {"version": "final", "rejected": False, "score": 20, "guard": {},
            "rows": [{"name": "Java", "status": "demonstrated"}]}
    ok, why = evaluate.check(cases["T08"], fake)
    assert ok, why
    ok, why = evaluate.check(cases["T14"], {"version": "final", "rejected": True})
    assert ok


def test_v1_parser():
    import llm
    raw = "**Match Score: 72/100**\n\n**Matching Skills:** React, Node.js\n\n**Missing Skills:** Docker"
    orig = llm.call
    llm.call = lambda *a, **k: raw
    try:
        r = p.run_v1("resume", "jd")
    finally:
        llm.call = orig
    assert r["score"] == 72 and "React" in r["matched"], r


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} offline tests passed")

"""Resume-JD Matcher pipeline.

Final workflow (v4):
    redact PII -> P1 Input Guard -> P2 JD Requirement Extractor -> P3 Evidence Matcher
    -> [code] evidence verification + rubric score -> P4 Truthful Bullet Rewriter
    -> P5 Feedback Coach

Older versions (v1, v2, v3) are kept runnable so they can be compared in the
evaluation harness and in the app's "Prompt Experiment" tab.
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

import llm

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"

# Settings for each prompt of each version. temperature None = model default.
SETTINGS = {
    "v1": {"baseline": dict(temperature=None, json_mode=False)},
    "v2": {"structured_single": dict(temperature=None, json_mode=False)},
    "v3": {k: dict(temperature=None, json_mode=False) for k in
           ("P2_jd_extractor", "P3_evidence_matcher", "P4_bullet_rewriter", "P5_feedback_coach")},
    "final": {
        "P1_input_guard": dict(temperature=0.0, json_mode=True),
        "P2_jd_extractor": dict(temperature=0.2, json_mode=True),
        "P3_evidence_matcher": dict(temperature=0.2, json_mode=True),
        "P4_bullet_rewriter": dict(temperature=0.4, json_mode=True),
        "P5_feedback_coach": dict(temperature=0.4, json_mode=True),
    },
}

WEIGHTS = {"required": 2.0, "preferred": 1.0}
CREDIT = {"demonstrated": 1.0, "matched": 1.0, "partial": 0.5, "missing": 0.0, "unverified": 0.0}


# --------------------------------------------------------------------- prompts
def load_prompt(version: str, name: str) -> dict:
    """Read a prompt file and split it into META / SYSTEM / USER parts."""
    text = (PROMPTS / version / f"{name}.txt").read_text(encoding="utf-8")
    parts = dict(re.findall(r"### (META|SYSTEM|USER)\n(.*?)(?=\n### |\Z)", text, re.S))
    system = parts.get("SYSTEM", "").strip()
    return {
        "meta": parts.get("META", "").strip(),
        "system": None if system.lower() == "none" else system,
        "user": parts.get("USER", "").strip(),
    }


def fill(template: str, **vars) -> str:
    """Replace {name} placeholders. Uses str.replace so JSON braces in the
    prompt text are left alone."""
    for k, v in vars.items():
        template = template.replace("{" + k + "}", str(v))
    return template


def run_prompt(version: str, name: str, trace: list, **vars):
    p = load_prompt(version, name)
    s = SETTINGS[version][name]
    user = fill(p["user"], **vars)
    raw = llm.call(p["system"], user, temperature=s["temperature"], json_mode=s["json_mode"])
    obj, ok = llm.parse_json(raw) if (s["json_mode"] or version != "v1") else (None, False)
    strict = _strict_json(raw)
    trace.append({"prompt": name, "version": version, "raw": raw, "json_ok": ok, "json_strict": strict})
    return raw, obj, ok


def _strict_json(raw: str) -> bool:
    try:
        json.loads(raw.strip())
        return True
    except Exception:
        return False


# ------------------------------------------------------------------- redaction
_PII = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    (re.compile(r"(?:\+?91[\s-]?)?(?<!\d)[6-9]\d{4}[\s-]?\d{5}(?!\d)"), "[PHONE]"),
    (re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com)/[\w\-/]+", re.I), "[PROFILE_LINK]"),
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "[ID_NUMBER]"),  # Aadhaar-like
]


def redact(text: str) -> tuple[str, int]:
    """Remove e-mails, phone numbers, profile links and ID numbers before any
    text is sent to the model. Returns (clean_text, number_of_redactions)."""
    n = 0
    for pat, repl in _PII:
        text, k = pat.subn(repl, text)
        n += k
    return text, n


# --------------------------------------------------------- verification/score
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w%+#.]+", " ", s.lower())).strip()


def quote_found(quote: str, resume: str, threshold: float = 0.85) -> bool:
    """True if `quote` really appears in the resume (exact after normalising
    case/punctuation/whitespace, or a near match >= threshold)."""
    q, r = _norm(quote), _norm(resume)
    if not q:
        return False
    if q in r:
        return True
    words, qn = r.split(), len(q.split())
    best = 0.0
    for i in range(max(1, len(words) - qn + 1)):
        window = " ".join(words[i:i + qn])
        best = max(best, difflib.SequenceMatcher(None, q, window).ratio())
        if best >= threshold:
            return True
    return False


def verify_matches(requirements: list, matches: list, resume: str) -> list:
    """Join requirements with matches and check every evidence quote.
    A 'demonstrated'/'partial' status whose quote is not in the resume becomes
    'unverified' and earns no credit."""
    by_id = {m.get("id"): m for m in matches if isinstance(m, dict)}
    rows = []
    for r in requirements:
        m = by_id.get(r.get("id"), {})
        status = str(m.get("status", "missing")).lower()
        if status == "matched":
            status = "demonstrated"
        if status not in CREDIT:
            status = "missing"
        ev = m.get("evidence", "") or ""
        verified = status == "missing" or quote_found(ev, resume)
        rows.append({
            "id": r.get("id"), "name": r.get("name"), "priority": r.get("priority", "required"),
            "category": r.get("category", ""), "model_status": status,
            "status": status if verified else "unverified",
            "evidence": ev, "evidence_verified": verified, "reason": m.get("reason", ""),
        })
    return rows


def rubric_score(rows: list) -> int:
    """Weighted score: required = 2, preferred = 1; demonstrated = 1,
    partial = 0.5, missing/unverified = 0."""
    total = sum(WEIGHTS.get(r["priority"], 2.0) for r in rows)
    if not total:
        return 0
    got = sum(WEIGHTS.get(r["priority"], 2.0) * CREDIT[r["status"]] for r in rows)
    return round(100 * got / total)


def band(score: int) -> str:
    return "Strong" if score >= 80 else "Good" if score >= 60 else "Moderate" if score >= 40 else "Low"


_NUM = re.compile(r"\d+(?:\.\d+)?")


def fabricated_numbers(rewrites: list) -> list:
    """Numbers in an improved bullet that are not in its original line
    (text inside [placeholders] is ignored)."""
    issues = []
    for rw in rewrites or []:
        if not isinstance(rw, dict):
            continue
        orig = rw.get("original", "")
        imp = re.sub(r"\[[^\]]*\]", "", rw.get("improved", ""))
        new = set(_NUM.findall(imp)) - set(_NUM.findall(orig))
        if new:
            issues.append({"improved": rw.get("improved", ""), "new_numbers": sorted(new)})
    return issues


def strip_injection(text: str, injection_text: str) -> str:
    if injection_text and injection_text in text:
        return text.replace(injection_text, "[REMOVED: instruction to AI]")
    return text


# ------------------------------------------------------------ version runners
def run_final(resume: str, job_description: str, progress=None) -> dict:
    """Run the final 5-prompt workflow. `progress(step, label)` is an optional
    UI callback."""
    tick = progress or (lambda *a: None)
    trace: list = []
    out: dict = {"version": "final", "trace": trace}

    resume, n1 = redact(resume)
    job_description, n2 = redact(job_description)
    out["redactions"] = n1 + n2

    if not resume.strip() or not job_description.strip():
        out.update(rejected=True, guard={"proceed": False, "resume_reason": "Resume is empty." if not resume.strip() else "",
                                         "jd_reason": "Job description is empty." if not job_description.strip() else ""})
        return out

    tick(1, "P1 Input Guard: checking inputs")
    _, guard, ok = run_prompt("final", "P1_input_guard", trace, resume=resume, job_description=job_description)
    guard = guard if ok and isinstance(guard, dict) else {"proceed": True}
    out["guard"] = guard
    if not guard.get("proceed", True):
        out["rejected"] = True
        return out
    out["rejected"] = False
    if guard.get("injection_detected"):
        resume = strip_injection(resume, guard.get("injection_text", ""))
        job_description = strip_injection(job_description, guard.get("injection_text", ""))

    tick(2, "P2 JD Requirement Extractor: reading the job")
    _, jd, _ = run_prompt("final", "P2_jd_extractor", trace, job_description=job_description)
    jd = jd if isinstance(jd, dict) else {}
    reqs = [r for r in jd.get("requirements", []) if isinstance(r, dict)][:15]
    out["role_title"] = jd.get("role_title", "")
    out["requirements"] = reqs

    tick(3, "P3 Evidence Matcher: finding proof in the resume")
    req_json = json.dumps([{k: r.get(k) for k in ("id", "name", "priority")} for r in reqs], ensure_ascii=False)
    _, mt, _ = run_prompt("final", "P3_evidence_matcher", trace, requirements_json=req_json, resume=resume)
    matches = (mt or {}).get("matches", []) if isinstance(mt, dict) else []

    tick(4, "Verifying evidence quotes and computing rubric score")
    rows = verify_matches(reqs, matches, resume)
    score = rubric_score(rows)
    out.update(rows=rows, score=score, band=band(score),
               unverified=sum(1 for r in rows if r["status"] == "unverified"))

    rows_json = json.dumps([{k: r[k] for k in ("id", "name", "priority", "status", "evidence")} for r in rows],
                           ensure_ascii=False)
    tick(5, "P4 Truthful Bullet Rewriter: improving bullet points")
    _, rw, _ = run_prompt("final", "P4_bullet_rewriter", trace, requirements_json=req_json,
                          matches_json=rows_json, resume=resume)
    rewrites = (rw or {}).get("rewrites", []) if isinstance(rw, dict) else []
    out["rewrites"] = rewrites
    out["fabricated_numbers"] = fabricated_numbers(rewrites)

    tick(6, "P5 Feedback Coach: writing feedback")
    _, fb, _ = run_prompt("final", "P5_feedback_coach", trace, role_title=out["role_title"],
                          score=score, band=out["band"], matches_json=rows_json)
    out["feedback"] = fb if isinstance(fb, dict) else {}
    return out


def run_v3(resume: str, job_description: str) -> dict:
    trace: list = []
    out = {"version": "v3", "trace": trace, "rejected": False}
    _, jd, _ = run_prompt("v3", "P2_jd_extractor", trace, job_description=job_description)
    reqs = (jd or {}).get("requirements", []) if isinstance(jd, dict) else []
    reqs = [r for r in reqs if isinstance(r, dict)]
    out["role_title"] = (jd or {}).get("role_title", "") if isinstance(jd, dict) else ""
    _, mt, _ = run_prompt("v3", "P3_evidence_matcher", trace,
                          requirements_json=json.dumps(reqs, ensure_ascii=False), resume=resume)
    matches = (mt or {}).get("matches", []) if isinstance(mt, dict) else []
    by_id = {m.get("id"): m for m in matches if isinstance(m, dict)}
    rows = []
    for r in reqs:  # v3: no evidence verification
        m = by_id.get(r.get("id"), {})
        st = str(m.get("status", "missing")).lower()
        st = "demonstrated" if st == "matched" else st if st in CREDIT else "missing"
        rows.append({"id": r.get("id"), "name": r.get("name"), "priority": r.get("priority", "required"),
                     "status": st, "evidence": m.get("evidence", ""),
                     "evidence_verified": st == "missing" or quote_found(m.get("evidence", ""), resume)})
    score = rubric_score(rows) if rows else None
    out.update(rows=rows, score=score)
    _, rw, _ = run_prompt("v3", "P4_bullet_rewriter", trace,
                          requirements_json=json.dumps(reqs, ensure_ascii=False), resume=resume)
    out["rewrites"] = (rw or {}).get("rewrites", []) if isinstance(rw, dict) else []
    out["fabricated_numbers"] = fabricated_numbers(out["rewrites"])
    _, fb, _ = run_prompt("v3", "P5_feedback_coach", trace, role_title=out["role_title"], score=score,
                          matches_json=json.dumps(rows, ensure_ascii=False))
    out["feedback"] = fb if isinstance(fb, dict) else {}
    return out


def run_v2(resume: str, job_description: str) -> dict:
    trace: list = []
    raw, obj, ok = run_prompt("v2", "structured_single", trace, resume=resume, job_description=job_description)
    obj = obj if isinstance(obj, dict) else {}
    score = obj.get("match_score")
    try:
        score = round(float(score))
    except Exception:
        score = None
    return {"version": "v2", "trace": trace, "raw": raw, "score": score,
            "matched": [str(s) for s in obj.get("matching_skills", [])],
            "missing": [str(s) for s in obj.get("missing_skills", [])],
            "rewrites": [{"original": "", "improved": b} for b in obj.get("rewritten_bullets", [])],
            "rejected": _looks_rejected(raw, score)}


def run_v1(resume: str, job_description: str) -> dict:
    trace: list = []
    raw, _, _ = run_prompt("v1", "baseline", trace, resume=resume, job_description=job_description)
    m = re.search(r"(\d{1,3})\s*(?:/|out of)\s*100", raw)
    score = int(m.group(1)) if m else None
    sec = re.search(r"Match(?:ing)?\s+Skills?\**:?\**(.*?)(?:\n\s*\n|\*\*Missing|Missing)", raw, re.S | re.I)
    matched = re.split(r"[,\n•*\-]+", sec.group(1)) if sec else []
    return {"version": "v1", "trace": trace, "raw": raw, "score": score,
            "matched": [s.strip(" :.") for s in matched if s.strip(" :.")],
            "rejected": _looks_rejected(raw, score)}


_REJECT = re.compile(r"not (?:a )?valid|cannot (?:evaluate|assess|compare)|unable to (?:evaluate|assess|compare)|"
                     r"(?:no|empty|missing) (?:job description|resume)|does not (?:appear to be|contain) a (?:resume|job)|"
                     r"not a resume|not a job description|insufficient information", re.I)


def _looks_rejected(raw: str, score) -> bool:
    return bool(_REJECT.search(raw or "")) and (score is None or score <= 10)


RUNNERS = {"v1": run_v1, "v2": run_v2, "v3": run_v3, "final": run_final}


def matched_names(result: dict) -> list:
    """Skills a version credited as matched (for the test checks)."""
    if "rows" in result:
        return [r["name"] for r in result["rows"] if r["status"] in ("demonstrated", "partial")]
    return result.get("matched", [])

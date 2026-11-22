"""Builds the Milestone 2 PDF (7 sections) and the supporting document
(research abstract) from: docs/team.json, prompts/, docs/diagrams/,
test-data/results/summary.json, test-data/outputs/ and docs/screenshots/.

Run AFTER `python code/evaluate.py` so the tables contain real results:
    python code/build_report.py
Outputs (in docs/):
    M2_<TeamID>_<ShortTitle>.pdf   and   <TeamName>_ResearchAbstract.pdf
PDF conversion uses Microsoft Edge (Windows) or Chrome in headless mode.
"""
from __future__ import annotations

import base64
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline  # noqa: E402

ROOT = pipeline.ROOT
DOCS = ROOT / "docs"
TEAM = json.loads((DOCS / "team.json").read_text(encoding="utf-8"))
SUMMARY_P = ROOT / "test-data" / "results" / "summary.json"
S = json.loads(SUMMARY_P.read_text(encoding="utf-8")) if SUMMARY_P.exists() else {}
CASES = json.loads((ROOT / "test-data" / "cases.json").read_text(encoding="utf-8"))
PENDING = '<span class="pending">PENDING - run <code>python code/evaluate.py</code> then rebuild</span>'
MODEL = (S.get("final") or {}).get("model", "gemini-3.5-flash")

e = html.escape


def pre(text: str) -> str:
    return f"<pre>{e(text)}</pre>"


def table(head, rows, cls=""):
    h = "".join(f"<th>{c}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>'


def svg(name: str) -> str:
    return (DOCS / "diagrams" / name).read_text(encoding="utf-8")


def img(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{data}"/>'


# ------------------------------------------------------------ prompt sheets
SHEETS = [
    ("P1_input_guard", "Step 1 of 5 (after PII redaction)",
     "Reject unusable inputs and detect prompt-injection text before any analysis.",
     {"resume": "Resume text after PII redaction", "job_description": "Job description text after PII redaction"},
     0, "JSON object: resume_is_valid, resume_reason, jd_is_valid, jd_reason, language, injection_detected, injection_text, proceed"),
    ("P2_jd_extractor", "Step 2 of 5",
     "Split the job description into atomic, normalised requirements marked required or preferred.",
     {"job_description": "Job description text (injection text removed)"},
     0, "JSON object: role_title, requirements[] {id, name, category, priority, jd_text} (max 15)"),
    ("P3_evidence_matcher", "Step 3 of 5 (followed by Python quote verification and rubric scoring)",
     "Decide demonstrated / partial / missing for every requirement with an exact supporting quote.",
     {"requirements_json": "JSON list of {id, name, priority} from P2", "resume": "Resume text (redacted, injection removed)"},
     1, "JSON object: matches[] {id, status, evidence, reason}"),
    ("P4_bullet_rewriter", "Step 4 of 5 (followed by Python invented-number check)",
     "Rewrite up to 5 resume lines toward the job without adding any new facts.",
     {"requirements_json": "Requirements from P2", "matches_json": "Verified match rows (id, name, priority, status, evidence)",
      "resume": "Resume text"},
     0, "JSON object: rewrites[] {original, improved, targets[], why}"),
    ("P5_feedback_coach", "Step 5 of 5",
     "Turn the verified match table and fixed score into specific gaps, actions and a verdict.",
     {"role_title": "Role title from P2", "score": "Rubric score 0-100 computed in Python",
      "band": "Strong / Good / Moderate / Low", "matches_json": "Verified match rows"},
     0, "JSON object: summary, strengths[], gaps[] {requirement, priority, action}, resume_edits[], next_steps_4_weeks[], verdict"),
]


def sample_run(prompt_name: str):
    for cid in ("T01", "T12", "T06"):
        p = ROOT / "test-data" / "outputs" / "final" / f"{cid}_r1.json"
        if p.exists():
            r = json.loads(p.read_text(encoding="utf-8"))
            for t in r.get("trace", []):
                if t["prompt"] == prompt_name:
                    return cid, t["raw"]
    return None, None


def prompt_sheets() -> str:
    out = []
    for i, (name, step, purpose, vars_, n_ex, fmt) in enumerate(SHEETS, 1):
        p = pipeline.load_prompt("final", name)
        meta = dict(line.split(": ", 1) for line in p["meta"].splitlines() if ": " in line)
        s = pipeline.SETTINGS["final"][name]
        settings = f"temperature {s['temperature']}, response_mime_type = application/json (JSON mode), other settings default"
        cid, raw = sample_run(name)
        if cid:
            case = next(c for c in CASES if c["id"] == cid)
            inp = f"Test {cid} ({case['title']}).\nRESUME:\n{case['resume']}\n\nJOB DESCRIPTION:\n{case['job_description']}"
            raw_show = raw if len(raw) < 1800 else raw[:1800] + "\n... (truncated; full output in test-data/outputs/final/" + cid + "_r1.json)"
            sample = f"<p><b>Real input</b> (PII is redacted by code before the prompt is filled):</p>{pre(inp)}<p><b>Actual output</b> ({MODEL}):</p>{pre(raw_show)}"
        else:
            sample = PENDING
        rows = [
            ("Prompt ID and name", f"{meta.get('id', 'P' + str(i))} - {meta.get('name', name)}"),
            ("Step in the workflow", step), ("Purpose", purpose),
            ("Tool and model", f"Google Gemini API ({MODEL}) via the google-genai Python SDK, called from a Streamlit app"),
            ("Settings", settings),
            ("Variables", "<br>".join(f"<code>{{{k}}}</code> - {e(v)}" for k, v in vars_.items())),
            ("Number of examples", f"{n_ex}" + (" (one worked example in a different domain: Figma / Excel / User Research)" if n_ex else " (zero-shot)")),
            ("Output format", e(fmt)),
        ]
        out.append(f'<div class="sheet"><h4>Prompt sheet {i}: {meta.get("id")} {meta.get("name")}</h4>'
                   + table(["Field", "Value"], rows, "kv")
                   + f"<p><b>Full system prompt</b></p>{pre(p['system'] or 'none')}"
                   + f"<p><b>Full user prompt template</b></p>{pre(p['user'])}"
                   + f"<p><b>Sample run</b></p>{sample}</div>")
    return "\n".join(out)


# ----------------------------------------------------------- iteration log
def result_text(v: str) -> str:
    m = S.get(v)
    if not m:
        return PENDING
    parts = [f"{m['passed']}/{m['total']} tests passed"]
    if m.get("score_range_mean") is not None:
        parts.append(f"same input scored with a spread of {m['score_range_mean']} points on average over 3 repeats (T01, T02, T06; ranges {m['score_ranges']})")
    parts.append("free-text output, score had to be parsed with regex" if v == "v1"
                 else f"strict JSON valid in {m['json_strict_valid']}/{m['json_calls']} calls")
    parts.append(f"{m['false_credit']} skills wrongly credited")
    if m["claimed_rows"]:
        parts.append(f"{m['unverified_quotes']}/{m['claimed_rows']} evidence quotes not found in the resume")
    if m["rewrites"]:
        parts.append(f"{m['fabricated_numbers']}/{m['rewrites']} rewritten bullets added numbers not in the original")
    parts.append(f"injection test T10 scored {m['injection_score']}" + (" (injection flagged)" if m["injection_flagged"] else ""))
    parts.append(f"invalid inputs rejected {m['invalid_rejected']}/{m['invalid_total']}")
    if m.get("errors"):
        parts.append(f"{m['errors']} API errors")
    return "; ".join(parts) + "."


ITER = [
    ("v1", "Milestone 1 baseline: one prompt, role 'resume reviewer', asks for score, matching/missing skills and suggestions. Free-text output, default temperature.",
     "Starting point (submitted in Milestone 1).", ["v1/baseline"]),
    ("v2", "Added recruiter role, an explicit scoring rubric (required 70 pts, preferred 30 pts, half credit for partial), 'only use evidence in the resume' and a JSON output schema. Still one prompt.",
     "v1 had no rubric, so a score could not be explained, and its free-text output had to be parsed with regex by the app.", ["v2/structured_single"]),
    ("v3", "Split the task into a 4-prompt chain: P2 extract requirements, P3 match each requirement with a quote, P4 rewrite bullets, P5 feedback. Score moved out of the LLM into Python (weights 2/1, credit 1/0.5/0).",
     "In v2 one prompt did extraction, judging, arithmetic and writing at once, so a wrong score could not be traced to a step and no claim could be checked against the resume.",
     ["v3/P2_jd_extractor", "v3/P3_evidence_matcher", "v3/P4_bullet_rewriter", "v3/P5_feedback_coach"]),
    ("v4 (final)", "Added P1 Input Guard (validity + injection), clear 'used vs only listed' definitions and synonym rules in P3, one worked example in P3, an exact-quote rule, the 'no new facts + [placeholder]' rule in P4, verdict rules in P5, JSON mode, temperatures 0.0-0.4, and Python checks (quote verification, invented-number check, PII redaction).",
     "v3 had no input validation or injection defence, no rule separating used skills from merely listed ones, and no check on evidence quotes or invented numbers (see the v3 result row for the measured effect).",
     ["final/P1_input_guard", "final/P2_jd_extractor", "final/P3_evidence_matcher", "final/P4_bullet_rewriter", "final/P5_feedback_coach"]),
]


def iteration_log() -> str:
    rows = [(v, e(what), e(why), result_text("final" if v.startswith("v4") else v)) for v, what, why, _ in ITER]
    out = [table(["Version", "What changed", "Why it was changed", "Result after the change (measured on 16 test cases)"], rows)]
    out.append("<h4>Full text of each version</h4>")
    for v, _, _, files in ITER:
        if v.startswith("v4"):
            out.append(f"<p><b>{v}</b>: the full text of all five final prompts is in the prompt sheets in Section 2(c) "
                       "and in <code>prompts/final/</code>.</p>")
            continue
        for f in files:
            out.append(f"<p><b>{v} - prompts/{f}.txt</b></p>" + pre((pipeline.PROMPTS / f"{f}.txt").read_text(encoding="utf-8")))
    return "\n".join(out)


# ---------------------------------------------------------------- modules
def module_rows():
    fin = S.get("final")
    llm_ok = bool(fin) and fin.get("errors", 1) == 0
    llm_status = "Working" if llm_ok else "Not verified yet"
    note = (f"Verified on 16 test cases ({fin['passed']}/16 passed)" if llm_ok else "Run evaluate.py with an API key")
    return [
        ("Resume Text Extraction", "Reads PDF, DOCX or TXT uploads into plain text (pypdf, python-docx)", "Working", "Scanned/image PDFs give no text (no OCR yet)"),
        ("PII Redaction", "Removes e-mails, phone numbers, LinkedIn/GitHub links and 12-digit IDs before text reaches the model", "Working", "Regex based; names and addresses are not removed"),
        ("Input Guard (P1)", "Rejects empty/unrelated inputs, detects language and prompt-injection text", llm_status, note),
        ("JD Requirement Extraction (P2)", "Turns the job description into up to 15 required/preferred requirements", llm_status, note),
        ("Evidence Matching (P3)", "Marks each requirement demonstrated / partial / missing with an exact resume quote", llm_status, note),
        ("Evidence Verification & Rubric Scoring", "Checks every quote is really in the resume, then computes a weighted 0-100 score and band", "Working", "Deterministic Python; tested offline"),
        ("Truthful Bullet Rewriter (P4)", "Rewrites up to 5 lines without new facts; Python flags any invented numbers", llm_status, note),
        ("Feedback Coach (P5)", "Gives strengths, gaps with actions, resume edits, 4-week plan and verdict", llm_status, note),
        ("Report Export", "Downloads the result as Markdown or JSON", "Working", ""),
        ("Prompt Comparison (v1 vs final)", "Runs the Milestone 1 baseline and the final workflow side by side in the app", llm_status, "Used for the reel's before/after"),
        ("Evaluation Harness", "Runs all versions on 16 test cases, caches outputs, computes metrics and the test table", "Working" if fin else "Not verified yet", "code/evaluate.py"),
    ]


def test_table() -> str:
    fin = S.get("final")
    if not fin:
        rows = [(c["id"], e(c["title"]), c["type"], e(c["expected_short"]), PENDING, "-") for c in CASES]
    else:
        rows = [(t["id"], e(t["title"]), t["type"], e(t["expected"]), e(t["actual"]),
                 "Pass" if t["pass"] else "<b>Fail</b><br><small>" + e("; ".join(t["why"])) + "</small>") for t in fin["tests"]]
    return table(["Test no.", "Input (short)", "Type", "Expected output", "Actual output (short)", "Pass / Fail"], rows)


def version_compare() -> str:
    if not S:
        return ""
    rows = []
    for v in ("v1", "v2", "v3", "final"):
        m = S.get(v)
        if not m:
            continue
        rows.append((v, f"{m['passed']}/{m['total']}", "n/a" if v == "v1" else f"{m['json_strict_valid']}/{m['json_calls']}",
                     m["score_range_mean"], m["false_credit"],
                     f"{m['unverified_quotes']}/{m['claimed_rows']}" if m["claimed_rows"] else "n/a",
                     f"{m['fabricated_numbers']}/{m['rewrites']}" if m["rewrites"] else "n/a",
                     m["injection_score"], f"{m['invalid_rejected']}/{m['invalid_total']}"))
    return ("<p><b>All versions on the same 16 inputs</b> (from <code>test-data/results/summary.json</code>):</p>" +
            table(["Version", "Tests passed", "Strict JSON", "Mean score spread (3 repeats)", "Wrongly credited skills",
                   "Quotes not in resume", "Invented numbers", "T10 injection score", "Invalid rejected"], rows))


def screenshots() -> str:
    shots = sorted((DOCS / "screenshots").glob("T*.png"))
    if not shots:
        return ('<p class="pending">ADD 2-3 screenshots: save them as docs/screenshots/T01.png, T10.png, T15.png '
                '(file name = test number) and rebuild.</p>')
    out = []
    for s in shots[:3]:
        cid = s.stem.split("_")[0]
        case = next((c for c in CASES if c["id"] == cid), None)
        cap = f"Screenshot - Test {cid}" + (f": {case['title']}" if case else "")
        out.append(f'<figure>{img(s)}<figcaption>{e(cap)}</figcaption></figure>')
    return "\n".join(out)


# ----------------------------------------------------------- abstract
def abstract_html() -> str:
    v1, fin = S.get("v1"), S.get("final")
    if v1 and fin:
        res = (f"On 16 test cases (7 normal, 6 edge, 3 invalid) the baseline prompt passed {v1['passed']}/16 checks and the final "
               f"workflow passed {fin['passed']}/16. The average score spread across three repeated runs fell from "
               f"{v1['score_range_mean']} to {fin['score_range_mean']} points. Wrongly credited skills fell from "
               f"{v1['false_credit']} to {fin['false_credit']}; the injected instruction in test T10 produced a score of "
               f"{v1['injection_score']} with the baseline and {fin['injection_score']} with the final workflow"
               f"{', where it was detected and removed' if fin['injection_flagged'] else ''}. Invalid inputs were rejected "
               f"{v1['invalid_rejected']}/3 times by the baseline and {fin['invalid_rejected']}/3 by the final workflow, and "
               f"{fin['json_strict_valid']}/{fin['json_calls']} final model outputs were valid JSON.")
    else:
        res = "[RESULTS PENDING - run python code/evaluate.py; numbers are filled in automatically.]"
    body = (
        "<p><b>Problem.</b> Students applying for internships receive resume feedback from AI tools that is often "
        "generic, inconsistent between runs and sometimes credits skills the resume does not show. We studied whether "
        "structured prompt engineering can make resume-to-job-description matching evidence-based and repeatable.</p>"
        f"<p><b>Method.</b> We compared four prompt versions on {MODEL}: (v1) the Milestone 1 single free-text prompt, "
        "(v2) a single prompt with a rubric and JSON schema, (v3) a four-step prompt chain with the score computed in code, "
        "and (v4) a five-step chain adding an input/injection guard, explicit 'used vs listed' definitions, a worked "
        "example, exact-quote evidence verified in Python, a no-new-facts rewriting rule and low temperatures. Each version "
        "ran on the same 16 made-up resume/job pairs with pre-written expected outcomes; three cases were repeated three "
        "times to measure consistency.</p>"
        f"<p><b>Results.</b> {res}</p>"
        f"<p><b>Conclusion.</b> {conclusion(v1, fin)}</p>")
    return body


def conclusion(v1, fin) -> str:
    if not (v1 and fin):
        return "[PENDING - written from the results.]"
    if fin["passed"] > v1["passed"]:
        return ("Splitting the task into narrow prompts, forcing quoted evidence and moving the arithmetic and fact checks "
                "into code made the feedback more explainable, more consistent and harder to manipulate than a single prompt. "
                "The remaining failures (Section 4) guide our Milestone 3 work.")
    return ("The structured workflow made every claim traceable to a quote, but it did not raise the pass rate over the "
            "baseline on this test set; the failures in Section 4 show where the prompts still need work in Milestone 3.")


def abstract_words() -> int:
    import re
    return len(re.sub(r"<[^>]+>", " ", abstract_html()).split())


# ----------------------------------------------------------------- pages
CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; color: #1b1b1b; line-height: 1.4; }
h1 { font-size: 22pt; margin: 0 0 6px; } h2 { font-size: 15pt; border-bottom: 2px solid #3367d6; padding-bottom: 3px; margin-top: 0; }
h3 { font-size: 12pt; margin: 14px 0 6px; } h4 { font-size: 11pt; margin: 12px 0 6px; }
.section { page-break-before: always; } .cover { text-align: left; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 10px; font-size: 9pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #bbb; padding: 4px 6px; vertical-align: top; text-align: left; }
th { background: #eef2fb; } table.kv td:first-child { width: 24%; font-weight: 600; background: #fafafa; }
pre { white-space: pre-wrap; word-wrap: break-word; background: #f6f8fa; border: 1px solid #ddd; padding: 6px 8px;
      font-family: Consolas, monospace; font-size: 8.3pt; margin: 4px 0 8px; }
code { font-family: Consolas, monospace; font-size: 9pt; }
.pending { color: #b00020; font-weight: 600; } svg { width: 100%; height: auto; border: 1px solid #ddd; margin: 4px 0; }
figure { margin: 8px 0; page-break-inside: avoid; } figure img { width: 100%; border: 1px solid #ccc; }
figcaption { font-size: 9pt; color: #444; text-align: center; } .sheet { page-break-before: always; }
.diagram { page-break-inside: avoid; margin-bottom: 10px; }
"""


def doc(title, body):
    return f'<!doctype html><html><head><meta charset="utf-8"><title>{e(title)}</title><style>{CSS}</style></head><body>{body}</body></html>'


def m2_html() -> str:
    T, L = TEAM, TEAM["links"]
    fin = S.get("final", {})
    n_versions = len(ITER)
    members = table(["Name", "Enrollment no.", "Role"], [(e(m["name"]), m["enrollment"], e(m["role"])) for m in T["members"]])
    cover = f"""
<div class="cover">
<h2>1. Cover page</h2>
<p style="color:#555">{e(T['course'])}</p>
<h1>{e(T['project_title'])}</h1>
<p style="font-size:12pt">Milestone 2 report</p>
{table(["Item", "Details"], [
    ("Team ID", e(T['team_id'])), ("Team name", e(T['team_name'])), ("Project title", e(T['project_title'])),
    ("Batch", e(T['batch'])), ("Faculty", e(T['faculty'])),
    ("Prototype link", e(L['prototype'])), ("Repository link", e(L['repository'])),
    ("Reel link", e(L['reel']) + f" (length: {e(str(L['reel_seconds']))} seconds)"),
    ("Counts", f"Final prompts: 5 · Test inputs: {len(CASES)} · Prompt versions: {n_versions}"),
    ("Main AI tool and model", f"Google Gemini API, {MODEL} (google-genai SDK) in a Streamlit web app"),
], "kv")}
<h3>Team members</h3>{members}
</div>"""

    design = f"""
<div class="section"><h2>2. Prompt and solution design</h2>
<h3>(a) Overview</h3>
<p><b>Problem and users.</b> College students and fresh graduates applying for internships and placements struggle to see how
well their resume fits a specific job, which skills are missing and how to present what they have actually done. Generic AI
reviewers give vague, run-to-run inconsistent feedback and can credit skills that the resume never shows. Our users are students,
and secondarily placement cells and career counsellors who review many resumes.</p>
<p><b>Input and output.</b> Input: a resume (PDF, DOCX, TXT or pasted text) and a job description (text). Output: a 0-100
match score from a fixed rubric with a band and verdict; a requirement-by-requirement table marked demonstrated / partial /
missing with an exact quote from the resume as evidence; up to five rewritten bullets that add no new facts; and specific
gaps, resume edits and a 4-week action plan, downloadable as Markdown or JSON.</p>
<p><b>Prompts and steps.</b> The final solution uses <b>5 prompts</b> plus deterministic Python steps (Figure 1). We split
the task because when one prompt extracts, judges, scores and writes at the same time, a wrong score cannot be traced to a
step and no claim can be checked (compare v2 and v4 in the iteration log). Each prompt has one narrow job and returns JSON, so code can check it before the next step: P1 Input Guard
(validity and prompt injection), P2 JD Requirement Extractor, P3 Evidence Matcher (status plus exact quote), P4 Truthful
Bullet Rewriter and P5 Feedback Coach. Between them, Python redacts personal data, verifies every evidence quote against the
resume, computes the weighted score (required = 2, preferred = 1; demonstrated = 1, partial = 0.5, missing or unverified
quote = 0) and flags numbers that appear in a rewritten bullet but not in the original.</p>
<p><b>Tool and model.</b> Google Gemini ({MODEL}) through the google-genai SDK. It follows instructions well, supports a
native JSON output mode (response_mime_type), has a free tier that students and evaluators can use, and is fast enough for
5 calls per analysis. The app is built in Streamlit and deployed on Streamlit Community Cloud so the evaluator can open it
without installing anything; the API key is stored in Streamlit secrets, never in the repository.</p>
<p><b>What changed since Milestone 1.</b> Milestone 1 had one free-text baseline prompt and an illustrative output. We have
now (1) built and deployed a working web app, (2) replaced the single prompt with a 5-prompt chain, (3) moved scoring out of
the model into a transparent rubric in code, (4) added evidence-quote verification, an input/injection guard, PII redaction
and an invented-number check, (5) written 16 test cases with expected results and an evaluation script that compares all
{n_versions} prompt versions on them.</p>
<h3>(b) Diagrams</h3>
<div class="diagram">{svg('1_prompt_workflow.svg')}</div>
<div class="diagram">{svg('2_task_decomposition.svg')}</div>
<div class="diagram">{svg('3_input_output_flow.svg')}</div>
<div class="diagram">{svg('4_system_architecture.svg')}</div>
<p>No agents or retrieval (RAG) are used, so no agent-loop or RAG diagram is included.</p>
<h3>(c) Prompt sheets</h3>
<p>Five prompt sheets follow, one per final prompt. Prompts are pasted as text; the same files are in <code>prompts/final/</code>.</p>
{prompt_sheets()}
</div>"""

    impl = f"""
<div class="section"><h2>3. Implementation</h2>
<h3>What is built</h3>
<p>A Streamlit web app (<code>code/app.py</code>) with three tabs: <b>Analyze</b> (upload or paste a resume, paste a job
description, run the 5-prompt workflow and see score, match table, feedback, rewritten bullets, the raw prompt trace and
download buttons), <b>Prompt experiment</b> (runs the Milestone 1 baseline and the final workflow on the same input side by
side) and <b>Prompts</b> (shows the final prompt files). The workflow lives in <code>code/pipeline.py</code>; prompts are
loaded from <code>prompts/final/*.txt</code> at run time, so the files in the repository are exactly what the app sends.
<code>code/evaluate.py</code> runs every prompt version on the 16 test cases and produces the tables in this report.</p>
<h3>Module status</h3>
{table(["Module", "What it does", "Status", "Notes"], [(e(a), e(b), c, e(d)) for a, b, c, d in module_rows()])}
<h3>Prompt iteration log</h3>
{iteration_log()}
</div>"""

    test = f"""
<div class="section"><h2>4. Demonstration and testing</h2>
<p>{len(CASES)} test inputs: {sum(c['type']=='Normal' for c in CASES)} normal, {sum(c['type']=='Edge' for c in CASES)} edge,
{sum(c['type']=='Invalid' for c in CASES)} invalid. All resumes and job descriptions are made up. Expected outputs were written
before running. Pass/Fail is decided by <code>code/evaluate.py</code> (score inside the expected range, required skills
credited, wrong skills not credited, invalid inputs rejected, injection flagged, feedback in English). Inputs are in
<code>test-data/cases.json</code>; every raw output is saved in <code>test-data/outputs/</code>.
{('Final workflow: <b>' + str(fin['passed']) + '/' + str(fin['total']) + ' passed</b>.') if fin else ''}</p>
{test_table()}
{version_compare()}
<h3>Screenshots of real runs</h3>
{screenshots()}
<h3>Known limitations and what we will try next</h3>
<ol>
<li><b>Score depends on how P2 splits the job description.</b> "Django or Flask" may become one or two requirements, which
changes the denominator. Next: merge "A or B" into one requirement in code and test P2 on 10 more real job posts.</li>
<li><b>Scanned or image-only PDFs give no text.</b> pypdf cannot read images. Next: add OCR (Tesseract) or ask the user to
paste text when extraction returns fewer than 50 characters.</li>
<li><b>Quote verification is fuzzy.</b> PDF extraction can break lines and hyphenate words, so a true quote can fail the 0.85
similarity check, and a near-paraphrase can pass. Next: normalise hyphenation and tune the threshold on the saved outputs.</li>
<li><b>Free-tier rate limits.</b> Five calls per analysis means about 10-30 seconds per run and a daily cap. Next: merge P4
and P5 into one call and cache P2 results for repeated job descriptions.</li>
</ol>
</div>"""

    repo_shot = DOCS / "screenshots" / "repo.png"
    repo = f"""
<div class="section"><h2>5. Repository</h2>
<p>Repository: {e(L['repository'])}</p>
{('<figure>' + img(repo_shot) + '<figcaption>Repository screenshot</figcaption></figure>') if repo_shot.exists() else '<p class="pending">ADD docs/screenshots/repo.png (screenshot of the GitHub repository page) and rebuild.</p>'}
<h3>What changed since Milestone 1</h3>
<ul>
<li>Added the working Streamlit app and the 5-prompt pipeline (<code>code/</code>), deployed on Streamlit Community Cloud.</li>
<li>Saved every prompt version: <code>prompts/v1</code> (Milestone 1 baseline), <code>v2</code>, <code>v3</code> and <code>final</code>.</li>
<li>Added 16 test cases and all saved model outputs and metrics in <code>test-data/</code>.</li>
<li>Added diagrams, this report and the research abstract in <code>docs/</code>; dated changes are in <code>CHANGELOG.md</code>.</li>
<li>No API keys in the repository: the key is read from Streamlit secrets or an environment variable; <code>.gitignore</code> blocks secrets files.</li>
</ul>
</div>"""

    support = f"""
<div class="section"><h2>6. Supporting document</h2>
<p>Type: <b>Research abstract</b> (uploaded separately as <code>{TEAM['file_team_name']}_ResearchAbstract.pdf</code>).</p>
<h3>Does Structured Prompt Engineering Make AI Resume Feedback Evidence-Based? A Comparison of Four Prompt Versions</h3>
<p><i>Team {e(T['team_name'])} - {', '.join(e(m['name']) for m in T['members'])}</i></p>
{abstract_html()}
<p><i>Keywords:</i> prompt engineering, prompt chaining, resume screening, hallucination control, prompt injection, LLM evaluation</p>
</div>"""

    contrib = f"""
<div class="section"><h2>7. Team contribution</h2>
{table(["Member name", "Enrollment no.", "Role", "Tasks done in Milestone 2", "Evidence", "Contribution (%)"],
       [(e(m['name']), m['enrollment'], e(m['role']), e(m['tasks']), e(m['evidence']), m['pct']) for m in T['members']]
       + [("<b>Total</b>", "", "", "", "", f"<b>{sum(m['pct'] for m in T['members'])}</b>")])}
<p>All members have read and agreed to this contribution table.</p>
</div>"""

    body = f"{cover}{design}{impl}{test}{repo}{support}{contrib}"
    return doc(f"M2_{T['team_id']}_{T['short_title']}", body)


def abstract_doc() -> str:
    T = TEAM
    body = (f"<p style='color:#555'>{e(T['course'])} · Team {e(T['team_name'])} ({e(T['team_id'])})</p>"
            "<h2>Research Abstract</h2>"
            "<h3>Does Structured Prompt Engineering Make AI Resume Feedback Evidence-Based? A Comparison of Four Prompt Versions</h3>"
            f"<p><i>{', '.join(e(m['name']) + ' (' + m['enrollment'] + ')' for m in T['members'])}</i></p>"
            f"{abstract_html()}<p><i>Keywords:</i> prompt engineering, prompt chaining, resume screening, hallucination control, "
            "prompt injection, LLM evaluation</p>" + version_compare())
    return doc(f"{T['file_team_name']}_ResearchAbstract", body)


def to_pdf(html_path: Path, pdf_path: Path):
    candidates = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                  r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  shutil.which("google-chrome") or "", shutil.which("chromium") or "", shutil.which("msedge") or ""]
    exe = next((c for c in candidates if c and Path(c).exists()), None)
    if not exe:
        print("No Edge/Chrome found: open the .html file in a browser and Print -> Save as PDF.")
        return
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", html_path.as_uri()], check=False, timeout=120,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("wrote", pdf_path, f"({pdf_path.stat().st_size // 1024} KB)" if pdf_path.exists() else "(FAILED)")


def main():
    T = TEAM
    m2_name = f"M2_{T['team_id']}_{T['short_title']}"
    ab_name = f"{T['file_team_name']}_ResearchAbstract"
    for name, content in ((m2_name, m2_html()), (ab_name, abstract_doc())):
        h = DOCS / f"{name}.html"
        h.write_text(content, encoding="utf-8")
        to_pdf(h, DOCS / f"{name}.pdf")
    print(f"abstract body: {abstract_words()} words (target 150-250)")
    if not S:
        print("NOTE: no evaluation results yet - tables show PENDING. Run code/evaluate.py first.")


if __name__ == "__main__":
    main()

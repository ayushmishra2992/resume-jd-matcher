"""Draws the four Milestone 2 diagrams as SVG files in docs/diagrams/.
They describe exactly what code/pipeline.py and code/app.py do.
Run: python code/make_diagrams.py
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "docs" / "diagrams"

FILL = {"llm": "#e8f0fe", "code": "#eef7ee", "io": "#fff6e5", "ext": "#f3e8fd", "bad": "#fdecec", "plain": "#ffffff"}
STROKE = {"llm": "#3367d6", "code": "#2e7d32", "io": "#c77700", "ext": "#7b1fa2", "bad": "#c62828", "plain": "#555"}


class D:
    def __init__(self, w, h, title):
        self.w, self.h, self.parts = w, h, []
        self.text(w / 2, 26, title, size=17, weight="bold")

    def text(self, x, y, s, size=12, weight="normal", anchor="middle", color="#222"):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
                          f'text-anchor="{anchor}" fill="{color}">{escape(s)}</text>')

    def box(self, x, y, w, h, lines, kind="plain", rx=8):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{FILL[kind]}" '
                          f'stroke="{STROKE[kind]}" stroke-width="1.6"/>')
        lines = [lines] if isinstance(lines, str) else lines
        lh = 15
        y0 = y + h / 2 - (len(lines) - 1) * lh / 2 + 4
        for i, ln in enumerate(lines):
            self.text(x + w / 2, y0 + i * lh, ln, size=12 if i else 13, weight="bold" if i == 0 else "normal")
        return (x, y, w, h)

    def arrow(self, x1, y1, x2, y2, label=None, dashed=False):
        d = ' stroke-dasharray="5,4"' if dashed else ""
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#444" stroke-width="1.5" '
                          f'marker-end="url(#a)"{d}/>')
        if label:
            self.text((x1 + x2) / 2 + 4, (y1 + y2) / 2 - 5, label, size=11, anchor="start", color="#555")

    def legend(self, y):
        x = 20
        for kind, name in (("llm", "LLM prompt (Gemini)"), ("code", "Python code (deterministic)"),
                           ("io", "Input / output"), ("bad", "Stop / error path")):
            self.parts.append(f'<rect x="{x}" y="{y}" width="14" height="14" fill="{FILL[kind]}" stroke="{STROKE[kind]}"/>')
            self.text(x + 20, y + 11, name, size=11, anchor="start")
            x += 190

    def save(self, name):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" '
               f'height="{self.h}" font-family="Segoe UI, Arial, sans-serif">'
               '<defs><marker id="a" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
               '<path d="M0,0 L10,4 L0,8 z" fill="#444"/></marker></defs>'
               f'<rect width="100%" height="100%" fill="#fff"/>{"".join(self.parts)}</svg>')
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_text(svg, encoding="utf-8")


def prompt_workflow():
    d = D(1000, 520, "Figure 1 - Prompt workflow (final version, 5 prompts)")
    W, H = 170, 62
    row1 = [("io", ["Inputs", "resume + job description"]), ("code", ["PII redaction", "email, phone, links"]),
            ("llm", ["P1 Input Guard", "valid? injection? T=0.0"]), ("llm", ["P2 JD Extractor", "requirements JSON, T=0.2"])]
    xs = [20, 270, 520, 790]
    for (k, t), x in zip(row1, xs):
        d.box(x, 70, W, H, t, k)
    for i in range(3):
        d.arrow(xs[i] + W, 101, xs[i + 1], 101)
    d.box(520, 190, W, 54, ["Stop: show reason", "invalid / empty input"], "bad")
    d.arrow(605, 132, 605, 190, "proceed = false")
    d.text(505, 212, "if P1 flags injection, that text", size=11, color="#7b1fa2", anchor="end")
    d.text(505, 227, "is removed and analysis continues", size=11, color="#7b1fa2", anchor="end")
    row2 = [("llm", ["P3 Evidence Matcher", "status + exact quote, T=0.2"]),
            ("code", ["Verify quotes + score", "fuzzy match >= 0.85, rubric"]),
            ("llm", ["P4 Bullet Rewriter", "no new facts, T=0.4"]),
            ("code", ["Number check", "flag invented numbers"])]
    xs2 = [790, 540, 290, 40]
    for (k, t), x in zip(row2, xs2):
        d.box(x, 300, W, H, t, k)
    d.arrow(875, 132, 875, 300, "requirements")
    for i in range(3):
        d.arrow(xs2[i], 331, xs2[i + 1] + W, 331)
    d.box(40, 420, W, H, ["P5 Feedback Coach", "plan + verdict, T=0.4"], "llm")
    d.arrow(125, 362, 125, 420)
    d.box(330, 420, 300, H, ["Report in app", "score, match table, bullets, plan, download"], "io")
    d.arrow(210, 451, 330, 451)
    d.text(840, 440, "Score = sum(weight x credit) / sum(weight)", size=11, color="#2e7d32")
    d.text(840, 457, "required = 2, preferred = 1", size=11, color="#2e7d32")
    d.text(840, 474, "demonstrated 1, partial 0.5, missing/unverified 0", size=11, color="#2e7d32")
    d.legend(500)
    d.save("1_prompt_workflow.svg")


def task_decomposition():
    d = D(1000, 380, "Figure 2 - Task decomposition")
    d.box(330, 50, 340, 60, ["Goal: honest resume-to-job match", "with evidence and an action plan"], "io")
    subs = [("llm", ["1. Check inputs", "P1 Input Guard"], ["usable resume?", "usable JD?", "injection?"]),
            ("llm", ["2. Understand the job", "P2 JD Extractor"], ["split skills", "required vs preferred", "normalise names"]),
            ("llm", ["3. Find evidence", "P3 Evidence Matcher"], ["used vs listed", "exact quote", "synonyms"]),
            ("code", ["4. Score fairly", "Python rubric"], ["verify quotes", "weights 2 / 1", "band + verdict"]),
            ("llm", ["5. Improve resume", "P4 Bullet Rewriter"], ["action verbs", "JD wording", "[placeholders]"]),
            ("llm", ["6. Advise", "P5 Feedback Coach"], ["gaps -> actions", "4-week plan", "English only"])]
    x = 15
    for k, title, leaves in subs:
        d.box(x, 160, 152, 58, title, k)
        d.arrow(500, 110, x + 76, 160)
        for j, lf in enumerate(leaves):
            d.box(x + 3, 240 + j * 40, 146, 30, [lf], "plain", rx=5)
        x += 163
    d.save("2_task_decomposition.svg")


def io_flow():
    d = D(1000, 360, "Figure 3 - Input-output flow")
    d.box(20, 60, 200, 70, ["Resume", "PDF / DOCX / TXT or pasted text"], "io")
    d.box(20, 170, 200, 70, ["Job description", "pasted text"], "io")
    d.box(270, 110, 170, 70, ["Text extraction", "pypdf, python-docx"], "code")
    d.arrow(220, 95, 270, 135)
    d.arrow(220, 205, 270, 160)
    d.box(480, 50, 220, 52, ["Guard result (JSON)", "valid flags, language, injection"], "llm")
    d.box(480, 112, 220, 52, ["Requirements (JSON)", "id, name, category, priority"], "llm")
    d.box(480, 174, 220, 52, ["Matches (JSON)", "status, evidence quote, reason"], "llm")
    d.box(480, 236, 220, 52, ["Verified rows + score", "0-100, band, unverified count"], "code")
    for y in (76, 138, 200, 262):
        d.arrow(440, 145, 480, y)
    outs = [["Match score + verdict"], ["Requirement match table"], ["Rewritten bullets"],
            ["Gaps, actions, 4-week plan"], ["Download .md / .json"]]
    for i, o in enumerate(outs):
        d.box(760, 50 + i * 52, 220, 40, o, "io")
        d.arrow(700, 76 + min(i, 3) * 62, 760, 70 + i * 52)
    d.text(500, 335, "Every model output is JSON; Python checks it before the next step uses it.", size=12, color="#555")
    d.save("3_input_output_flow.svg")


def architecture():
    d = D(1000, 420, "Figure 4 - System architecture")
    d.box(20, 160, 150, 70, ["User / evaluator", "web browser"], "io")
    d.parts.append('<rect x="220" y="50" width="520" height="340" rx="12" fill="#fafafa" stroke="#888" stroke-dasharray="6,4"/>')
    d.text(480, 72, "Streamlit Community Cloud (code/app.py)", size=13, weight="bold")
    d.box(240, 90, 220, 60, ["UI (app.py)", "Analyze, Experiment, Prompts tabs"], "code")
    d.box(500, 90, 220, 60, ["extract.py", "PDF / DOCX / TXT to text"], "code")
    d.box(240, 175, 480, 70, ["pipeline.py", "redact -> P1 -> P2 -> P3 -> verify + score -> P4 -> number check -> P5"], "code")
    d.box(240, 270, 220, 60, ["prompts/final/*.txt", "P1-P5 templates loaded at run"], "io")
    d.box(500, 270, 220, 60, ["llm.py", "google-genai client, retries, JSON parse"], "code")
    d.box(240, 340, 480, 36, ["st.secrets: GEMINI_API_KEY (never in the repo)"], "bad")
    d.box(800, 260, 180, 80, ["Google Gemini API", "gemini-3.5-flash", "(free tier)"], "ext")
    d.box(800, 90, 180, 70, ["code/evaluate.py", "16 test cases, v1-v4", "-> test-data/results"], "code")
    d.arrow(170, 195, 240, 120, "HTTPS")
    d.arrow(350, 150, 350, 175)
    d.arrow(610, 150, 610, 175)
    d.arrow(350, 270, 350, 245)
    d.arrow(610, 245, 610, 270)
    d.arrow(720, 300, 800, 300, "HTTPS")
    d.arrow(890, 160, 890, 260, "same pipeline", dashed=True)
    d.save("4_system_architecture.svg")


if __name__ == "__main__":
    prompt_workflow()
    task_decomposition()
    io_flow()
    architecture()
    print("diagrams written to", OUT)

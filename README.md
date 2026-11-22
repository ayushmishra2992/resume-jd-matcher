# Prompt-Engineered AI Resume–Job Description Matcher

**Team +one** · SCSE4041 Prompt Engineering · Mini Project (Milestone 2)

**Prototype:** FILL IN – https://&lt;your-app&gt;.streamlit.app

An AI assistant that compares a student's resume with a job description. A 5-prompt workflow on Google Gemini:

1. **P1 Input Guard** – rejects empty/unrelated inputs and detects prompt-injection text.
2. **P2 JD Requirement Extractor** – splits the job description into required/preferred requirements.
3. **P3 Evidence Matcher** – marks each requirement *demonstrated / partial / missing* with an **exact quote** from the resume.
4. *(Python)* – verifies every quote is really in the resume and computes a fixed **rubric score** (required = 2, preferred = 1; demonstrated = 1, partial = 0.5, missing/unverified = 0).
5. **P4 Truthful Bullet Rewriter** – improves up to 5 bullets **without adding facts**; Python flags any invented numbers.
6. **P5 Feedback Coach** – gaps with concrete actions, resume edits, 4-week plan and a verdict.

Personal details (e-mail, phone, profile links, ID numbers) are redacted before anything is sent to the model.

## Run it

```bash
pip install -r requirements.txt
```

Get a free API key at https://aistudio.google.com/apikey, then copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and paste the key (this file is git-ignored), or set the `GEMINI_API_KEY` environment variable.

```bash
streamlit run code/app.py
```

**Deploy (Streamlit Community Cloud):** New app → this repo → main file `code/app.py` → *Advanced settings → Secrets*: `GEMINI_API_KEY = "..."`.

## Evaluate and build the report

```bash
python code/test_offline.py          # deterministic modules, no key needed
python code/evaluate.py              # all 4 prompt versions x 16 test cases (resumable)
python code/build_report.py          # builds docs/M2_<TeamID>_ResumeJDMatcher.pdf and the research abstract
```

## Repository structure

| Path | Contents |
|---|---|
| `prompts/v1/` | Milestone 1 baseline prompt |
| `prompts/v2/` | Single prompt with rubric + JSON |
| `prompts/v3/` | First 4-prompt chain |
| `prompts/final/` | Final prompts P1–P5 (loaded by the app at run time) |
| `code/` | `app.py` (UI), `pipeline.py` (workflow), `llm.py` (Gemini client), `extract.py`, `evaluate.py`, `build_report.py`, `make_diagrams.py`, `test_offline.py` |
| `test-data/` | `cases.json` (16 made-up test inputs), `outputs/` (saved model outputs), `results/` (metrics, test table) |
| `docs/` | Diagrams, screenshots, Milestone 2 PDF, research abstract, reel script |
| `CHANGELOG.md` | Dated changes since Milestone 1 |

## Team

| Enrollment | Name | Main task |
|---|---|---|
| S24CSEU0356 | Ayush Mishra (lead) | Streamlit app, pipeline, verification and scoring, deployment |
| S24CSEU0370 | Riya Katiyar | Prompts P1–P3 and their versions |
| S24CSEU0347 | Riya Maurya | Test cases, evaluation runs, test table |
| S24CSEU0390 | Samridhi Agrawal | Prompts P4–P5, diagrams, research abstract, reel |

No API keys or passwords are stored in this repository. All test resumes are made up.

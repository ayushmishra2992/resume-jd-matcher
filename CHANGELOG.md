# Changelog

All dates are 2026. Milestone 1 (proposal + baseline prompt) was submitted on 9 October.

## 19 November
- Added the Streamlit web app (`code/app.py`) with Analyze, Prompt experiment and Prompts tabs.
- Replaced the single Milestone 1 prompt with a 5-prompt workflow (`prompts/final/P1`–`P5`) in `code/pipeline.py`.
- Moved scoring out of the model into a fixed rubric in Python; added evidence-quote verification and an invented-number check.
- Added PII redaction (e-mail, phone, profile links, ID numbers) before model calls.
- Saved all prompt versions: `prompts/v1` (Milestone 1 baseline), `v2` (rubric + JSON), `v3` (first chain), `final` (v4).
- Added 16 test cases (7 normal, 6 edge, 3 invalid) in `test-data/cases.json` and the evaluation harness `code/evaluate.py`.
- Added offline tests for the non-LLM modules (`code/test_offline.py`).
- Added diagram generator and four diagrams in `docs/diagrams/`, and the report builder `code/build_report.py`.

## 21 November
- Gemini 2.5 Flash returned 404 "no longer available to new users" for the project key; switched the model to `gemini-3.5-flash` (`DEFAULT_MODEL` in `code/llm.py`, `GEMINI_MODEL` in the secrets file, diagram label, submission guide Q9). A single test call returned "connection ok".
- The first evaluation run (all calls failed with 404) was discarded; results were regenerated with `gemini-3.5-flash`.

<!-- Add a dated line for each later step, e.g.:
## 20 November
- Ran evaluation on all versions; results in test-data/results/.
- Deployed to Streamlit Community Cloud.
## 21 November
- Recorded reel; added screenshots; built the Milestone 2 PDF.
-->

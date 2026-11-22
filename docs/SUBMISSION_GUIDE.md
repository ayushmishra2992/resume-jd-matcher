# Milestone 2 – what's left to do and the form answers

Deadline: **Sunday 22 November 2026, 11:59 PM**. Team leader submits once.

## Step-by-step

1. **Get a free Gemini key**: https://aistudio.google.com/apikey (Google login). Never commit it.
2. **Install and run locally**
   ```
   pip install -r requirements.txt
   copy .streamlit\secrets.toml.example .streamlit\secrets.toml   (then paste your key inside)
   streamlit run code/app.py
   ```
3. **Run the evaluation** (≈230 calls; at ~10 requests/min this takes ~40 min. If you hit the daily limit, run the same command again tomorrow or with another teammate's key — finished runs are cached):
   ```
   $env:GEMINI_API_KEY="your-key"      (PowerShell)
   python code/evaluate.py
   ```
   Check `test-data/results/results.md`. **Read the failures** and, if your observations differ from the limitation list in `code/build_report.py`, edit that list.
4. **Push to GitHub** (public repo). Ideally each member commits their own part (prompts, test data, docs) so the commit history is evidence for Section 7.
5. **Deploy**: https://share.streamlit.io → New app → repo → main file `code/app.py` → Advanced → Secrets: `GEMINI_API_KEY = "..."`. Open the app link in an **incognito window** to be sure it works without login.
6. **Screenshots**: run tests T01, T10 and T15 in the deployed app, save as `docs/screenshots/T01.png`, `T10.png`, `T15.png`; screenshot the GitHub repo page as `docs/screenshots/repo.png`.
7. **Record the reel** with `docs/REEL_SCRIPT.md` (90–150 s), upload, set "Anyone with the link".
8. **Fill `docs/team.json`**: Team ID, batch, faculty, the three links, reel seconds. Check the contribution table with the whole team.
9. **Build the PDFs**: `python code/build_report.py` → `docs/M2_<TeamID>_ResumeJDMatcher.pdf` and `docs/PlusOne_ResearchAbstract.pdf`. Open both; check there is no red "PENDING" or "FILL IN" text left. Commit and push them.

## Form answers

| Q | Answer |
|---|---|
| 1 Team ID | (from Milestone 1) |
| 2 Team name | +one |
| 3 Project title | Prompt-Engineered AI Resume-Job Description Matcher |
| 4–5 Leader | Ayush Mishra, S24CSEU0356 |
| 6 Batch | (your WhatsApp batch group) |
| 7 Enrollments | S24CSEU0356<br>S24CSEU0370<br>S24CSEU0347<br>S24CSEU0390 |
| 8 Project type | Custom web app + Prompt chain/workflow (pick the closest ≤2 options) |
| 9 Main AI tool and model | Gemini 3.5 Flash via Google Gemini API (google-genai SDK) in a Streamlit web app |
| 10 Number of prompts | **5** |
| 11 Prototype link | Streamlit app URL |
| 12 Repository link | GitHub URL |
| 13 Reel link | Drive / unlisted YouTube |
| 14 Reel length | exact seconds |
| 15 Supporting doc type | Research abstract |
| 16 Upload | PlusOne_ResearchAbstract.pdf |
| 17 Number of test inputs | **16** |
| 18 Number of prompt versions | **4** (v1, v2, v3, v4/final) |
| 19 Prototype status | "All modules working" only if every row of the module table in the PDF says Working |
| 20 Working modules | Copy the names marked Working from the module table, one per line (Resume Text Extraction, PII Redaction, Input Guard (P1), JD Requirement Extraction (P2), Evidence Matching (P3), Evidence Verification & Rubric Scoring, Truthful Bullet Rewriter (P4), Feedback Coach (P5), Report Export, Prompt Comparison (v1 vs final), Evaluation Harness) |
| 21 Upload | M2_<TeamID>_ResumeJDMatcher.pdf |
| 22 Main tasks | S24CSEU0356 – Ayush Mishra – Streamlit app, pipeline, verification and scoring, deployment<br>S24CSEU0370 – Riya Katiyar – Prompts P1–P3 and their versions<br>S24CSEU0347 – Riya Maurya – Test cases, evaluation runs, test table<br>S24CSEU0390 – Samridhi Agrawal – Prompts P4–P5, diagrams, research abstract, reel |
| 23 Note for evaluator | No login needed. Open the link, pick a sample in the sidebar (e.g. T01) → Load sample → Analyze match. The "Prompt experiment" tab compares the Milestone 1 prompt with the final workflow. |
| 24 Confirmation | Tick after all four members agree to Section 7 |

If you change the team roles, update `docs/team.json`, the README table and Q22 so they all match.

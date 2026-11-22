# Reel script (target 120 s, must be 90–150 s)

Screen recording of the **deployed app** with a teammate's voice-over (Samridhi). Record with OBS / Xbox Game Bar (Win + G) / phone. Upload to Drive or unlisted YouTube, "Anyone with the link can view". Write down the **exact length in seconds** for the form (Q14) and the cover page.

| Time | Part | On screen | Voice-over |
|---|---|---|---|
| 0–12 s | 1. Problem | App title, then a resume and a job post side by side | "Students applying for internships don't know how well their resume fits a job, and AI reviewers often give vague scores or credit skills you never showed. We built an evidence-based resume–job matcher." |
| 12–50 s | 2. Prompt experiment | **Prompt experiment** tab. Load sample **T10** (prompt injection) or **T08** (Java vs JavaScript). Click *Run both*. Point at v1 output, then final output | "On the left is our Milestone 1 prompt: one free-text instruction. Here it [say what v1 actually did, e.g. gave 100 because the resume told it to / credited JavaScript for Java]. On the right is our final 5-prompt workflow: an input guard caught the injection, each skill needs an exact quote from the resume, and the score comes from a fixed rubric, so it gives [actual score]." |
| 50–105 s | 3. Working demo | **Analyze** tab. Upload a PDF resume (or load **T01**), paste the JD, click *Analyze match*. Show score + verdict, match table with quotes, Improved bullets tab (point at a [placeholder]), Feedback tab, download button | "Now a real run. We upload a resume and paste the job. Prompt 1 checks the inputs, Prompt 2 extracts the requirements, Prompt 3 finds proof in the resume, our code verifies every quote and calculates the score. Prompt 4 rewrites bullets without inventing numbers — it leaves placeholders instead — and Prompt 5 gives a four-week action plan." |
| 105–120 s | 4. Progress and next steps | Test table from the PDF / results.md | "Done: 5 prompts, 4 prompt versions, 16 test cases, [X] passing. For Milestone 3 we'll fix how 'A or B' requirements are scored, add OCR for scanned PDFs and collect feedback from our placement cell." |

Tips: Zoom the browser to 110–125 % so text is readable on a phone. Use real runs only (mock-up screens get 0).

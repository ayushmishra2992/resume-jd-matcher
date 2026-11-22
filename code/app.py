"""Streamlit front end for the Prompt-Engineered AI Resume-JD Matcher.

Run locally:   streamlit run code/app.py
Deploy:        Streamlit Community Cloud, main file = code/app.py,
               add GEMINI_API_KEY under App settings -> Secrets.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm  # noqa: E402
import pipeline  # noqa: E402
from extract import extract_text  # noqa: E402

st.set_page_config(page_title="Resume-JD Matcher | +one", page_icon="📄", layout="wide")

CASES = json.loads((pipeline.ROOT / "test-data" / "cases.json").read_text(encoding="utf-8"))
STATUS_LABEL = {"demonstrated": "✅ Demonstrated", "partial": "🟡 Partial", "missing": "❌ Missing",
                "unverified": "⚠️ Unverified quote"}

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("📄 Resume-JD Matcher")
    st.caption("Team +one · SCSE4041 Prompt Engineering")
    key_ok = bool(llm.get_api_key())
    if not key_ok:
        user_key = st.text_input("Gemini API key", type="password",
                                 help="Free key from aistudio.google.com/apikey. Used only for this browser session.")
        if user_key:
            st.session_state["user_api_key"] = user_key
            key_ok = True
    st.write(f"Model: `{llm.get_model()}`")
    st.write("API key: " + ("configured ✅" if key_ok else "missing ❌"))
    st.divider()
    st.subheader("Try a sample")
    labels = ["(none)"] + [f"{c['id']} · {c['type']} · {c['title']}" for c in CASES]
    pick = st.selectbox("Load a test case", labels, index=0)
    if st.button("Load sample", use_container_width=True) and pick != "(none)":
        c = CASES[labels.index(pick) - 1]
        st.session_state["resume_text"] = c["resume"]
        st.session_state["jd_text"] = c["job_description"]
        st.rerun()
    st.divider()
    st.caption("Privacy: e-mails, phone numbers, profile links and ID numbers are redacted before any text "
               "is sent to the model. Use sample or consent-based resumes only.")


@st.cache_data(show_spinner=False, max_entries=50)
def cached_final(resume: str, jd: str) -> dict:
    return pipeline.run_final(resume, jd)


@st.cache_data(show_spinner=False, max_entries=50)
def cached_v1(resume: str, jd: str) -> dict:
    return pipeline.run_v1(resume, jd)


def to_markdown(r: dict) -> str:
    fb = r.get("feedback", {})
    md = [f"# Resume-JD Match Report: {r.get('role_title', '')}", "",
          f"**Match score:** {r['score']}/100 ({r['band']}) · **Verdict:** {fb.get('verdict', '')}", "",
          fb.get("summary", ""), "", "## Requirement match", "",
          "| Requirement | Priority | Status | Evidence from resume |", "|---|---|---|---|"]
    for row in r["rows"]:
        md.append(f"| {row['name']} | {row['priority']} | {row['status']} | {row['evidence'] or '-'} |")
    md += ["", "## Gaps and actions", ""] + [f"- **{g.get('requirement')}** ({g.get('priority')}): {g.get('action')}"
                                            for g in fb.get("gaps", [])]
    md += ["", "## Improved bullets", ""] + [f"- Before: {w.get('original')}\n  After: {w.get('improved')}"
                                            for w in r.get("rewrites", [])]
    md += ["", "## Next 4 weeks", ""] + [f"- {s}" for s in fb.get("next_steps_4_weeks", [])]
    return "\n".join(md)


def show_result(r: dict):
    if r.get("rejected"):
        g = r.get("guard", {})
        st.error("**Input rejected by P1 Input Guard.** Please check your inputs.")
        if g.get("resume_reason"):
            st.write(f"Resume: {g['resume_reason']}")
        if g.get("jd_reason"):
            st.write(f"Job description: {g['jd_reason']}")
        return
    g = r.get("guard", {})
    if g.get("injection_detected"):
        st.warning(f"⚠️ Possible prompt injection found and removed: “{g.get('injection_text', '')}”")
    if g.get("language") == "mixed":
        st.info("Mixed-language resume detected. Feedback is given in English.")
    if r.get("redactions"):
        st.caption(f"🔒 {r['redactions']} personal detail(s) redacted before analysis.")

    fb = r.get("feedback", {})
    c1, c2, c3 = st.columns(3)
    c1.metric("Match score (rubric)", f"{r['score']}/100", r["band"])
    c2.metric("Verdict", fb.get("verdict", "-"))
    c3.metric("Requirements checked", len(r["rows"]))
    st.markdown(f"**Role:** {r.get('role_title', '')}")
    if fb.get("summary"):
        st.write(fb["summary"])

    t1, t2, t3, t4 = st.tabs(["Requirement match", "Feedback & next steps", "Improved bullets", "Prompt trace"])
    with t1:
        st.dataframe([{"Requirement": x["name"], "Priority": x["priority"],
                       "Status": STATUS_LABEL.get(x["status"], x["status"]),
                       "Evidence (verified quote from resume)": x["evidence"] or "-", "Reason": x.get("reason", "")}
                      for x in r["rows"]], use_container_width=True, hide_index=True)
        if r.get("unverified"):
            st.warning(f"{r['unverified']} claim(s) had an evidence quote that is not in the resume, "
                       "so they earned no credit.")
        st.caption("Score = Σ weight × credit / Σ weight · required = 2, preferred = 1 · "
                   "demonstrated = 1, partial = 0.5, missing/unverified = 0")
    with t2:
        if fb.get("strengths"):
            st.subheader("Strengths")
            for s in fb["strengths"]:
                st.markdown(f"- {s}")
        if fb.get("gaps"):
            st.subheader("Gaps and actions")
            for gp in fb["gaps"]:
                st.markdown(f"- **{gp.get('requirement')}** ({gp.get('priority')}): {gp.get('action')}")
        if fb.get("resume_edits"):
            st.subheader("Resume edits")
            for s in fb["resume_edits"]:
                st.markdown(f"- {s}")
        if fb.get("next_steps_4_weeks"):
            st.subheader("Next 4 weeks")
            for s in fb["next_steps_4_weeks"]:
                st.markdown(f"- {s}")
    with t3:
        if r.get("fabricated_numbers"):
            st.warning("Some rewrites contain numbers that are not in your original line. Use them only if true: "
                       + "; ".join(", ".join(f["new_numbers"]) for f in r["fabricated_numbers"]))
        for w in r.get("rewrites", []):
            st.markdown(f"**Before:** {w.get('original', '')}")
            st.markdown(f"**After:** {w.get('improved', '')}")
            if w.get("why"):
                st.caption(w["why"])
            st.divider()
        st.caption("Text in [square brackets] is a placeholder — fill it only with true facts.")
    with t4:
        for t in r.get("trace", []):
            with st.expander(f"{t['prompt']} · JSON valid: {t['json_ok']}"):
                st.code(t["raw"], language="json")

    st.download_button("⬇️ Download report (Markdown)", to_markdown(r), "match_report.md")
    st.download_button("⬇️ Download raw result (JSON)", json.dumps(r, indent=2, ensure_ascii=False), "match_result.json")


# ------------------------------------------------------------------- main
st.title("Prompt-Engineered AI Resume–Job Description Matcher")
st.write("Paste or upload a resume and a job description. A 5-prompt workflow extracts the job's requirements, "
         "finds **quoted evidence** in the resume, scores the match with a fixed rubric, rewrites bullets "
         "**without inventing facts**, and gives an action plan.")

tab_a, tab_b, tab_c = st.tabs(["🔍 Analyze", "🧪 Prompt experiment (v1 vs final)", "📜 Prompts"])

with tab_a:
    col1, col2 = st.columns(2)
    with col1:
        up = st.file_uploader("Upload resume (PDF, DOCX or TXT)", type=["pdf", "docx", "txt"])
        if up is not None and st.session_state.get("_last_upload") != up.name:
            try:
                st.session_state["resume_text"] = extract_text(up.name, up.getvalue())
                st.session_state["_last_upload"] = up.name
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not read file: {e}")
        resume = st.text_area("Resume text", key="resume_text", height=320)
    with col2:
        jd = st.text_area("Job description", key="jd_text", height=390)

    if st.button("Analyze match", type="primary", disabled=not key_ok):
        with st.spinner("Running P1 Guard → P2 Extract → P3 Match → verify & score → P4 Rewrite → P5 Feedback…"):
            try:
                st.session_state["last_result"] = cached_final(resume, jd)
            except llm.LLMError as e:
                st.error(f"Model call failed: {e}")
    if "last_result" in st.session_state:
        show_result(st.session_state["last_result"])

with tab_b:
    st.write("Runs the **Milestone 1 baseline prompt (v1)** and the **final workflow** on the same input so you can "
             "see what prompt engineering changed. Uses the resume and JD from the Analyze tab.")
    if st.button("Run both", disabled=not key_ok):
        with st.spinner("Running v1 and final…"):
            try:
                st.session_state["cmp"] = (cached_v1(resume, jd), cached_final(resume, jd))
            except llm.LLMError as e:
                st.error(f"Model call failed: {e}")
    if "cmp" in st.session_state:
        v1, fin = st.session_state["cmp"]
        a, b = st.columns(2)
        with a:
            st.subheader("v1 · baseline single prompt")
            st.metric("Score", v1.get("score", "-"))
            st.markdown(v1.get("raw", ""))
        with b:
            st.subheader("final · 5-prompt workflow")
            if fin.get("rejected"):
                st.error("Rejected by Input Guard")
            else:
                st.metric("Score", fin["score"], fin["band"])
                st.dataframe([{"Requirement": x["name"], "Status": STATUS_LABEL.get(x["status"]),
                               "Evidence": x["evidence"] or "-"} for x in fin["rows"]],
                             hide_index=True, use_container_width=True)

with tab_c:
    for f in sorted((pipeline.PROMPTS / "final").glob("*.txt")):
        with st.expander(f.stem):
            st.code(f.read_text(encoding="utf-8"), language="markdown")

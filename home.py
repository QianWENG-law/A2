"""
Australian Trade Mark Registrability Pre-Check (LAWS90286 Assignment 2)

Steps: 1 interpret application -> 2 ss 39/42 -> 3 s 41 -> 4 s 43 -> 5 s 44
       -> 6 reviewer reflection (re-run flagged steps) -> 7 final report.
Steps 3 and 5 use self-consistency (asked N times, majority vote).
"""

import json
from collections import Counter
from datetime import date

import streamlit as st
from openai import OpenAI

from sidebar import render_credentials_sidebar
from law_notes import LAW_NOTES

MODEL = "gpt-4o-mini"
RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"]
RISK_ICON = {"LOW": "🟢", "MEDIUM": "🟠", "HIGH": "🔴"}
DISCLAIMER = (
    "Preliminary information only, not legal advice. The IP Australia register is not searched: "
    "s 44 only compares the earlier marks you enter."
)
SYSTEM_PROMPT = (
    "You are an experienced Australian trade marks attorney assisting with a pre-filing "
    "assessment under the Trade Marks Act 1995 (Cth). Apply ONLY the legal framework in the "
    "LAW NOTES. Be specific and honest about uncertainty. Reply with a single valid JSON object."
)


# ---------------------------------------------------------------- AI helpers
def call_ai(client, task, payload, law_key=None, temperature=0.2, label=""):
    law = f"LAW NOTES:\n{LAW_NOTES[law_key]}\n\n" if law_key else ""
    response = client.chat.completions.create(
        model=MODEL,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"{law}TASK:\n{task}\n\nINPUT (JSON):\n{json.dumps(payload, indent=2)}"},
        ],
    )
    text = response.choices[0].message.content
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = {"error": "Invalid JSON", "raw": text}
    st.session_state["call_log"].append({"task": task.splitlines()[0] + label, "output": result})
    return result


def normalise_risk(value):
    value = str(value or "").upper()
    return value if value in RISK_LEVELS else "MEDIUM"


def self_consistency(run_once, n, vote_key=None):
    """Ask n times at a higher temperature and keep the majority risk rating."""
    if n <= 1:
        return run_once(0.2, "")
    samples = [run_once(0.8, f" [sample {i + 1}/{n}]") for i in range(n)]
    risks = [normalise_risk(s.get("risk")) for s in samples]
    votes = Counter(risks)
    top = max(votes.values())
    majority = max((r for r, c in votes.items() if c == top), key=RISK_LEVELS.index)  # ties -> higher risk

    chosen = dict(next(s for s, r in zip(samples, risks) if r == majority))
    chosen["risk"] = majority
    chosen["consistency"] = {
        "samples": n,
        "risk_votes": dict(votes),
        "agreement": round(top / n, 2),
        "confidence": "high" if top == n else ("medium" if top / n >= 0.6 else "low"),
    }
    if vote_key:
        chosen["consistency"][f"{vote_key}_votes"] = dict(Counter(str(s.get(vote_key)) for s in samples))
    return chosen


# ---------------------------------------------------------------- Steps
def step1_interpret(client, app):
    task = """Step 1: Interpret the trade mark application.
Return JSON with keys:
- "mark_summary": one sentence describing the mark and its use
- "mark_meaning": ordinary meaning of the words (translate foreign words) and whether an ordinary Australian consumer of these goods/services would understand it
- "nice_classes": list of {"class": int, "reason": str}
- "target_consumers": who buys these goods/services and how
- "notes": anything unclear"""
    return call_ai(client, task, app, "classification")


def step2_s39_s42(client, app, s1):
    task = """Step 2: Assess sections 39 and 42 (prohibited signs; scandalous; contrary to law).
Return JSON with keys: "s39_issue" (bool), "s39_reasoning", "s42_issue" (bool), "s42_reasoning",
"risk" ("LOW" | "MEDIUM" | "HIGH"), "suggestion"."""
    return call_ai(client, task, {"application": app, "step1": s1}, "s39_s42")


def step3_s41(client, app, s1, n):
    task = """Step 3: Assess section 41 (capacity to distinguish).
Work through: (a) ordinary signification of each word to the relevant Australian audience;
(b) whether it directly describes the goods/services; (c) whether other traders, without improper
motive, would want to use it (Clark Equipment); (d) whether the mark is inherently adapted to
distinguish; (e) whether evidence of use under s 41(4)-(5) would help.
Return JSON with keys: "ordinary_signification", "descriptive_analysis", "other_traders_test",
"inherent_adaptation" ("fully" | "to some extent" | "not at all"), "evidence_of_use_relevant",
"authorities_applied" (only cases from the LAW NOTES), "risk" ("LOW" | "MEDIUM" | "HIGH"), "suggestion"."""
    payload = {"application": app, "step1": s1}
    return self_consistency(
        lambda t, label: call_ai(client, task, payload, "s41", t, label), n, "inherent_adaptation"
    )


def step4_s43(client, app, s1):
    task = """Step 4: Assess section 43 (deceptive or confusing connotation).
Return JSON with keys: "connotations" (list), "likely_to_deceive" (bool), "reasoning",
"risk" ("LOW" | "MEDIUM" | "HIGH"), "suggestion"."""
    return call_ai(client, task, {"application": app, "step1": s1}, "s43")


def step5_s44(client, app, s1, earlier_marks, n):
    if not earlier_marks:
        task = """Step 5: No earlier marks were supplied, so section 44 cannot be assessed.
Prepare a search plan for IP Australia's Australian Trade Mark Search.
Return JSON with keys: "search_terms" (list), "classes_to_search" (list of int),
"what_to_look_for", "risk": "MEDIUM", "note" (explain the limitation)."""
        return [call_ai(client, task, {"application": app, "step1": s1}, "s44")]

    task = """Step 5: Assess section 44 against ONE earlier trade mark.
Compare: (a) whether the goods/services are the same, similar or closely related;
(b) whether the marks are substantially identical (side-by-side); (c) whether they are deceptively
similar (imperfect recollection; sound, look and idea; circumstances of purchase); (d) conclusion.
Return JSON with keys: "earlier_mark", "goods_comparison", "substantially_identical" (bool),
"deceptively_similar" (bool), "reasoning", "authorities_applied" (only cases from the LAW NOTES),
"risk" ("LOW" | "MEDIUM" | "HIGH"), "suggestion"."""
    results = []
    for earlier in earlier_marks:
        payload = {"application": app, "step1": s1, "earlier_mark": earlier}
        results.append(
            self_consistency(
                lambda t, label, p=payload: call_ai(client, task, p, "s44", t, label), n, "deceptively_similar"
            )
        )
    return results


def step6_review(client, app, analysis):
    task = """Step 6: Act as a senior reviewing partner. Check steps 1-5 for legal errors, misapplied
tests, inconsistency, risk ratings that do not match the reasoning, and missing issues. Where a step
has a "consistency" record, low agreement means the answers varied: treat it with extra care.
Return JSON with keys: "overall_quality", "steps_to_redo" (any of "step3_s41", "step4_s43",
"step5_s44" with a real error; empty list if none), "comments" (step -> fixing instruction),
"other_observations"."""
    return call_ai(client, task, {"application": app, "analysis": analysis})


def redo_step(client, app, s1, step, previous, comment, earlier_marks):
    law_key = {"step3_s41": "s41", "step4_s43": "s43", "step5_s44": "s44"}[step]
    task = f"""Revise your earlier analysis for {step} in light of the reviewer's comment.
Keep the same JSON structure (for s44 return {{"results": [...]}}, one object per earlier mark).
Reviewer's comment: {comment}"""
    payload = {"application": app, "step1": s1, "previous_answer": previous, "earlier_marks": earlier_marks}
    revised = call_ai(client, task, payload, law_key)
    if step == "step5_s44":
        return revised.get("results", previous)
    if "consistency" in previous:
        revised["consistency_before_review"] = previous["consistency"]
    return revised


def step7_report(client, app, analysis, review):
    task = """Step 7: Write the final registrability report for the applicant (a non-lawyer).
Return JSON with keys: "overall_risk" ("LOW" | "MEDIUM" | "HIGH"),
"headline" (one sentence: is this mark likely to be registered?),
"report_markdown" with headings ## Summary, ## Classes, ## Ground-by-ground assessment,
## Recommendations, ## Limitations. Use plain English and section numbers; do not invent cases.
Where a step has a "consistency" record, say how many assessments agreed (e.g. "2 of 3 rated this HIGH")."""
    return call_ai(client, task, {"application": app, "analysis": analysis, "review": review})


# ---------------------------------------------------------------- UI helpers
def parse_earlier_marks(text):
    marks = []
    for line in text.splitlines():
        if line.strip():
            parts = [p.strip() for p in line.split("|")] + ["not stated", "not stated"]
            marks.append({"mark": parts[0], "goods_services": parts[1], "owner": parts[2]})
    return marks


def risk_badge(label, result):
    items = result if isinstance(result, list) else [result]
    risk = max((normalise_risk(r.get("risk")) for r in items), key=RISK_LEVELS.index)
    st.markdown(f"**{label}:** {RISK_ICON[risk]} {risk}")
    for r in items:
        c = r.get("consistency") or r.get("consistency_before_review")
        if c:
            name = f"{r.get('earlier_mark', '')}: " if isinstance(result, list) else ""
            votes = ", ".join(f"{k} ×{v}" for k, v in c["risk_votes"].items())
            note = " — revised after review" if "consistency_before_review" in r else ""
            st.caption(f"{name}{int(c['agreement'] * 100)}% agreement ({votes}){note}")


# ---------------------------------------------------------------- Page
st.set_page_config(page_title="Trade Mark Pre-Check", page_icon="™️")

api_key = render_credentials_sidebar()
with st.sidebar:
    use_reflection = st.checkbox("Reviewer reflection (Step 6)", value=True)
    n_samples = st.slider("Times to ask s 41 and s 44", 1, 5, 3)

st.title("Australian Trade Mark Pre-Check")
st.caption(DISCLAIMER)

with st.form("application"):
    mark = st.text_input("Trade mark", placeholder="e.g. ORO")
    mark_type = st.selectbox("Type of mark", ["Word mark", "Word + logo"])
    logo = st.text_input("Logo description (optional)")
    applicant = st.text_input("Applicant (optional)")
    goods = st.text_area("Goods and/or services", placeholder="e.g. Coffee beans and roasted coffee")
    use = st.selectbox(
        "Prior use in Australia", ["Not yet used", "Used for less than 2 years", "Used for 2+ years"]
    )
    earlier_text = st.text_area(
        "Earlier trade marks (optional, one per line: MARK | goods/services | owner)",
        placeholder="BOTOX | pharmaceutical preparations for treating wrinkles | Allergan Inc",
    )
    submitted = st.form_submit_button("Run pre-check", type="primary")

if submitted:
    if not api_key:
        st.error("Please enter your OpenAI API key in the sidebar.")
        st.stop()
    if not mark.strip() or not goods.strip():
        st.error("Please enter the trade mark and the goods/services.")
        st.stop()

    client = OpenAI(api_key=api_key)
    st.session_state["call_log"] = []
    application = {
        "mark": mark.strip(),
        "mark_type": mark_type,
        "logo_description": logo or "none",
        "applicant": applicant or "not stated",
        "goods_services": goods.strip(),
        "prior_use_in_australia": use,
    }
    earlier_marks = parse_earlier_marks(earlier_text)

    try:
        with st.status("Running the assessment...", expanded=True) as status:
            st.write("Step 1 — interpreting the application")
            s1 = step1_interpret(client, application)
            st.write("Step 2 — ss 39 and 42")
            s2 = step2_s39_s42(client, application, s1)
            st.write(f"Step 3 — s 41 (asked {n_samples}×)")
            s3 = step3_s41(client, application, s1, n_samples)
            st.write("Step 4 — s 43")
            s4 = step4_s43(client, application, s1)
            st.write(f"Step 5 — s 44 (asked {n_samples}× per earlier mark)")
            s5 = step5_s44(client, application, s1, earlier_marks, n_samples)

            analysis = {"step1_interpretation": s1, "step2_s39_s42": s2, "step3_s41": s3,
                        "step4_s43": s4, "step5_s44": s5}
            first_draft = json.loads(json.dumps(analysis))

            review = {"note": "Reflection switched off."}
            if use_reflection:
                st.write("Step 6 — reviewer reflection")
                review = step6_review(client, application, analysis)
                for step in review.get("steps_to_redo") or []:
                    if step in ("step3_s41", "step4_s43", "step5_s44"):
                        st.write(f"↻ Re-running {step}")
                        comment = (review.get("comments") or {}).get(step, "Re-check this step.")
                        analysis[step] = redo_step(client, application, s1, step, analysis[step],
                                                   comment, earlier_marks)

            st.write("Step 7 — writing the report")
            report = step7_report(client, application, analysis, review)
            status.update(label=f"Done — {len(st.session_state['call_log'])} AI calls", state="complete")
    except Exception as exc:
        st.error(f"The assessment could not be completed: {exc}")
        st.stop()

    st.session_state["result"] = {"application": application, "analysis": analysis,
                                  "first_draft": first_draft, "review": review, "report": report}

# ---------------------------------------------------------------- Output
if "result" in st.session_state:
    res = st.session_state["result"]
    analysis, report = res["analysis"], res["report"]
    overall = normalise_risk(report.get("overall_risk"))

    st.divider()
    st.subheader(f"Overall risk of refusal: {RISK_ICON[overall]} {overall}")
    st.markdown(f"**{report.get('headline', '')}**")
    risk_badge("s 39 / s 42", analysis["step2_s39_s42"])
    risk_badge("s 41", analysis["step3_s41"])
    risk_badge("s 43", analysis["step4_s43"])
    risk_badge("s 44", analysis["step5_s44"])

    tab_report, tab_steps, tab_review, tab_log = st.tabs(["Report", "Steps", "Reviewer", "AI call log"])
    with tab_report:
        report_md = report.get("report_markdown", "No report generated.")
        st.markdown(report_md)
        st.download_button(
            "Download report (.md)",
            f"# Trade Mark Pre-Check: {res['application']['mark']}\n\nDate: {date.today()}\n\n"
            f"> {DISCLAIMER}\n\n**Overall risk:** {overall}\n\n{report_md}\n",
            file_name=f"precheck_{res['application']['mark'].replace(' ', '_')}.md",
        )
    with tab_steps:
        for name, value in analysis.items():
            with st.expander(name):
                st.json(value)
    with tab_review:
        st.json(res["review"])
        changed = [k for k in analysis if analysis[k] != res["first_draft"][k]]
        st.markdown("**Changed after review:** " + (", ".join(changed) or "none"))
        for k in changed:
            with st.expander(f"First draft of {k}"):
                st.json(res["first_draft"][k])
    with tab_log:
        log = st.session_state.get("call_log", [])
        st.write(f"Total AI calls: **{len(log)}**")
        for i, entry in enumerate(log, 1):
            with st.expander(f"Call {i}: {entry['task']}"):
                st.json(entry["output"])

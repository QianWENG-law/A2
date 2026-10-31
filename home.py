
"""
Australian Trade Mark Registrability Pre-Check
LAWS90286 Legal AI - Assignment 2

A pre-filing self-check for people who want to register a trade mark in
Australia. The tool breaks the registrability assessment under the
Trade Marks Act 1995 (Cth) into discrete steps, calls the AI once per step,
reviews its own work (reflection loop) and produces a report.

Pipeline (AI calls in each run: at least 6; about 11 with default settings):
  Step 1  Interpret the application and identify Nice classes
  Step 2  s 39 / s 42  prohibited signs, scandalous matter, contrary to law
  Step 3  s 41         inherent capacity to distinguish  [self-consistency vote]
  Step 4  s 43         deceptive or confusing connotation
  Step 5  s 44         conflict with earlier marks (one assessment per earlier mark,
                       each with a self-consistency vote; or a search-strategy
                       call if none are supplied)
  Self-consistency: the evaluative steps (s 41, s 44) are asked N times
  independently (default 3) and the majority risk rating is used; the
  agreement rate is reported as a confidence score.
  Step 6  Reflection   a reviewer checks steps 1-5 for errors; flagged steps
                       are re-run once with the reviewer's comments
  Step 7  Report       final registrability report (downloadable)
"""

import json
from collections import Counter
from datetime import date

import streamlit as st
from openai import OpenAI

from credentials_sidebar import render_credentials_sidebar
from law_notes import LAW_NOTES

st.set_page_config(page_title="Trade Mark Pre-Check (AU)", page_icon="™️", layout="wide")

DISCLAIMER = (
    "This tool is a study project and gives general, preliminary information only. "
    "It is not legal advice. It does not search the IP Australia register, so it can "
    "only compare your mark with earlier marks that you enter yourself."
)

SYSTEM_PROMPT = (
    "You are an experienced Australian trade marks attorney assisting with a "
    "pre-filing assessment under the Trade Marks Act 1995 (Cth). Apply ONLY the "
    "legal framework provided in the LAW NOTES. Be careful, specific and honest "
    "about uncertainty. Always reply with a single valid JSON object."
)

RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"]
RISK_ICON = {"LOW": "🟢", "MEDIUM": "🟠", "HIGH": "🔴"}


# --------------------------------------------------------------------------
# AI helper
# --------------------------------------------------------------------------
def call_ai(
    client: OpenAI,
    model: str,
    task: str,
    payload: dict,
    law_key: str | None = None,
    temperature: float = 0.2,
    label: str = "",
) -> dict:
    """One AI call that returns JSON. Every call is logged so the user can see it."""
    law = LAW_NOTES.get(law_key, "") if law_key else ""
    user_msg = (
        f"LAW NOTES:\n{law}\n\n" if law else ""
    ) + f"TASK:\n{task}\n\nINPUT (JSON):\n{json.dumps(payload, indent=2)}"

    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    text = response.choices[0].message.content
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = {"error": "Model did not return valid JSON", "raw": text}

    st.session_state["call_log"].append({"task": task.splitlines()[0] + label, "output": result})
    return result


def normalise_risk(value) -> str:
    value = str(value or "").upper()
    return value if value in RISK_LEVELS else "MEDIUM"


def self_consistency(run_once, n: int, vote_key: str | None = None) -> dict:
    """
    Self-consistency: ask the same question n times (independently, at a higher
    temperature so the answers can differ), then take the majority risk rating.

    run_once(temperature, label) -> dict   makes ONE AI call
    vote_key                               an extra field to tally (e.g. "deceptively_similar")

    Returns the answer that matches the majority, plus a "consistency" record
    showing all the votes and the agreement rate (used as a confidence score).
    """
    if n <= 1:
        return run_once(0.2, "")

    samples = [run_once(0.8, f" [sample {i + 1}/{n}]") for i in range(n)]
    risks = [normalise_risk(s.get("risk")) for s in samples]
    votes = Counter(risks)
    top = max(votes.values())
    # Tie-break conservatively: if two ratings are equally common, pick the higher risk.
    majority = max((r for r, c in votes.items() if c == top), key=RISK_LEVELS.index)

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


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------
def step1_interpret(client, model, app):
    task = """Step 1: Interpret the trade mark application.
Return JSON with keys:
- "mark_summary": one sentence describing the mark and what it is used for
- "mark_meaning": any ordinary meaning of the mark's words (including translation of foreign words) and whether an ordinary Australian consumer of these goods/services would understand that meaning
- "nice_classes": list of objects {"class": int, "reason": str}
- "target_consumers": who buys these goods/services and how (careful purchase or impulse purchase)
- "notes": anything unclear in the application"""
    return call_ai(client, model, task, app, "classification")


def step2_s39_s42(client, model, app, s1):
    task = """Step 2: Assess sections 39 and 42 (prohibited signs; scandalous; contrary to law).
Return JSON with keys:
- "s39_issue": true/false, "s39_reasoning": str
- "s42_issue": true/false, "s42_reasoning": str
- "risk": "LOW" | "MEDIUM" | "HIGH"
- "suggestion": how the applicant could reduce any risk (or "None needed")"""
    return call_ai(client, model, task, {"application": app, "step1": s1}, "s39_s42")


def step3_s41(client, model, app, s1, n_samples=1):
    task = """Step 3: Assess section 41 (capacity to distinguish).
Work through: (a) the ordinary signification of each word to the relevant Australian audience;
(b) whether it directly describes the goods/services (kind, quality, purpose, geographic origin etc.);
(c) whether other traders, without improper motive, would legitimately want to use it (Clark Equipment);
(d) conclusion on whether the mark is inherently adapted to distinguish (fully / to some extent / not at all);
(e) whether evidence of use under s 41(4)-(5) would help.
Return JSON with keys:
- "ordinary_signification": str
- "descriptive_analysis": str
- "other_traders_test": str
- "inherent_adaptation": "fully" | "to some extent" | "not at all"
- "evidence_of_use_relevant": str
- "authorities_applied": list of case names you relied on (only from the LAW NOTES)
- "risk": "LOW" | "MEDIUM" | "HIGH"
- "suggestion": str"""
    return self_consistency(
        lambda temp, label: call_ai(client, model, task, {"application": app, "step1": s1}, "s41", temp, label),
        n_samples,
        vote_key="inherent_adaptation",
    )


def step4_s43(client, model, app, s1):
    task = """Step 4: Assess section 43 (deceptive or confusing connotation).
Identify any connotation of the mark (geographic origin, ingredient, quality, official approval etc.)
and whether use for these goods/services would be likely to deceive or confuse.
Return JSON with keys:
- "connotations": list of str
- "likely_to_deceive": true/false
- "reasoning": str
- "risk": "LOW" | "MEDIUM" | "HIGH"
- "suggestion": str (e.g. a limitation of the goods)"""
    return call_ai(client, model, task, {"application": app, "step1": s1}, "s43")


def step5_s44(client, model, app, s1, earlier_marks, n_samples=1):
    """One AI call per earlier mark. If none are supplied, one call producing a search plan."""
    results = []
    if not earlier_marks:
        task = """Step 5: No earlier marks were supplied, so section 44 cannot be assessed.
Prepare a search plan the applicant should run on IP Australia's Australian Trade Mark Search.
Return JSON with keys:
- "search_terms": list of str (exact mark, phonetic variants, translations, key components)
- "classes_to_search": list of int (including related classes)
- "what_to_look_for": str
- "risk": "MEDIUM"
- "note": str explaining the limitation"""
        results.append(call_ai(client, model, task, {"application": app, "step1": s1}, "s44"))
        return results

    for earlier in earlier_marks:
        task = """Step 5: Assess section 44 against ONE earlier trade mark.
Compare: (a) are the goods/services the same, similar or closely related;
(b) are the marks substantially identical (side-by-side);
(c) are they deceptively similar (imperfect recollection; sound, look and idea; circumstances of purchase);
(d) conclusion.
Return JSON with keys:
- "earlier_mark": str
- "goods_comparison": str
- "substantially_identical": true/false
- "deceptively_similar": true/false
- "reasoning": str
- "authorities_applied": list of case names (only from the LAW NOTES)
- "risk": "LOW" | "MEDIUM" | "HIGH"
- "suggestion": str"""
        payload = {"application": app, "step1": s1, "earlier_mark": earlier}
        results.append(
            self_consistency(
                lambda temp, label, payload=payload: call_ai(client, model, task, payload, "s44", temp, label),
                n_samples,
                vote_key="deceptively_similar",
            )
        )
    return results


def step6_review(client, model, app, analysis):
    task = """Step 6: Act as a senior reviewing partner. Check the analysis of steps 1-5 for:
legal errors, misapplication of the tests in the LAW NOTES, internal inconsistency,
risk ratings that do not match the reasoning, and missing issues.
Where a step has a "consistency" record, LOW agreement means the model gave different answers when asked
the same question several times: treat that step with extra care and say so.
Return JSON with keys:
- "overall_quality": str
- "steps_to_redo": list containing any of "step3_s41", "step4_s43", "step5_s44" that contain a real error (empty list if none)
- "comments": object mapping each step in steps_to_redo to a specific instruction for fixing it
- "other_observations": str"""
    return call_ai(client, model, task, {"application": app, "analysis": analysis})


def redo_step(client, model, app, s1, step_name, previous, comment, earlier_marks):
    """Re-run a flagged step once, giving the model the reviewer's comment."""
    law_key = {"step3_s41": "s41", "step4_s43": "s43", "step5_s44": "s44"}[step_name]
    task = f"""Revise your earlier analysis for {step_name} in light of the reviewer's comment.
Keep EXACTLY the same JSON structure as the previous answer (for s44, return {{"results": [ ... ]}} with one object per earlier mark).
Reviewer's comment: {comment}"""
    payload = {"application": app, "step1": s1, "previous_answer": previous, "earlier_marks": earlier_marks}
    revised = call_ai(client, model, task, payload, law_key)
    if step_name == "step5_s44":
        return revised.get("results", previous) if isinstance(revised, dict) else previous
    if isinstance(previous, dict) and "consistency" in previous:
        revised["consistency_before_review"] = previous["consistency"]
    return revised


def step7_report(client, model, app, analysis, review):
    task = """Step 7: Write the final registrability report for the applicant (a non-lawyer).
Return JSON with keys:
- "overall_risk": "LOW" | "MEDIUM" | "HIGH"
- "headline": one sentence answer to "Is this mark likely to be registered?"
- "report_markdown": a clear report in Markdown with these headings:
  ## Summary, ## Classes, ## Ground-by-ground assessment (s 39/42, s 41, s 43, s 44),
  ## Recommendations, ## Limitations of this assessment
  Use plain English, refer to the section numbers, and do not invent cases that are not in the analysis.
  Where a step has a "consistency" record, state how many of the repeated assessments agreed
  (e.g. "2 of 3 assessments rated this HIGH") and explain that low agreement means the result is uncertain."""
    return call_ai(client, model, task, {"application": app, "analysis": analysis, "review": review})


# --------------------------------------------------------------------------
# UI helpers
# --------------------------------------------------------------------------
def parse_earlier_marks(text: str) -> list[dict]:
    """Each line: MARK | goods/services | owner (owner optional)."""
    marks = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split("|")]
        marks.append(
            {
                "mark": parts[0],
                "goods_services": parts[1] if len(parts) > 1 else "not stated",
                "owner": parts[2] if len(parts) > 2 else "not stated",
            }
        )
    return marks


def risk_badge(label: str, result) -> None:
    items = result if isinstance(result, list) else [result]
    risks = [normalise_risk(r.get("risk")) for r in items] or ["MEDIUM"]
    risk = max(risks, key=RISK_LEVELS.index)
    st.markdown(f"**{label}:** {RISK_ICON[risk]} {risk}")
    for r in items:
        c = r.get("consistency") or r.get("consistency_before_review")
        if c:
            name = f"{r.get('earlier_mark', '')}: " if isinstance(result, list) else ""
            votes = ", ".join(f"{k} ×{v}" for k, v in c["risk_votes"].items())
            note = " — revised after review" if "consistency_before_review" in r else ""
            st.caption(
                f"{name}{int(c['agreement'] * 100)}% agreement ({votes}) — {c['confidence']} confidence{note}"
            )


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------
api_key = render_credentials_sidebar()
with st.sidebar:
    st.divider()
    model = st.selectbox("Model", ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"], index=0)
    use_reflection = st.checkbox("Run reviewer reflection loop (Step 6)", value=True)
    n_samples = st.slider(
        "Self-consistency: times to ask s 41 and s 44",
        min_value=1, max_value=5, value=3,
        help="The evaluative steps (s 41, s 44) are asked several times independently and the "
        "majority answer is used. The agreement rate is shown as a confidence score. "
        "More samples = more reliable but slower and more API cost.",
    )

st.title("™️ Australian Trade Mark Registrability Pre-Check")
st.write(
    "Planning to apply for a trade mark in Australia? Describe your mark and your goods or "
    "services, and this tool checks it step by step against the main grounds for rejection "
    "in the *Trade Marks Act 1995* (Cth): ss 39, 41, 42, 43 and 44."
)
st.info(DISCLAIMER)

with st.form("application"):
    col1, col2 = st.columns(2)
    with col1:
        mark = st.text_input("Trade mark (the word(s) you want to register)", placeholder="e.g. ORO")
        mark_type = st.selectbox("Type of mark", ["Word mark", "Word + logo (describe logo below)"])
        logo = st.text_input("Logo / stylisation description (optional)")
        applicant = st.text_input("Applicant (optional)", placeholder="e.g. Modena Trading Pty Ltd")
    with col2:
        goods = st.text_area(
            "Goods and/or services the mark will be used for",
            placeholder="e.g. Coffee beans and roasted coffee sold to cafes and restaurants",
            height=110,
        )
        use = st.selectbox(
            "Has the mark already been used in Australia?",
            ["Not yet used", "Used for less than 2 years", "Used for 2+ years"],
        )
    earlier_text = st.text_area(
        "Earlier trade marks you know of (optional) — one per line: MARK | goods/services | owner",
        placeholder="BOTOX | pharmaceutical preparations for treating wrinkles | Allergan Inc",
        height=90,
    )
    submitted = st.form_submit_button("Run pre-check", type="primary")

if submitted:
    if not api_key:
        st.error("Please enter your OpenAI API key in the sidebar first.")
        st.stop()
    if not mark.strip() or not goods.strip():
        st.error("Please enter both the trade mark and the goods/services.")
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
            st.write("Step 1 — interpreting the application and classes")
            s1 = step1_interpret(client, model, application)
            st.write("Step 2 — s 39 / s 42 prohibited signs and scandalous matter")
            s2 = step2_s39_s42(client, model, application, s1)
            st.write(f"Step 3 — s 41 capacity to distinguish (asked {n_samples}×)")
            s3 = step3_s41(client, model, application, s1, n_samples)
            st.write("Step 4 — s 43 deceptive connotation")
            s4 = step4_s43(client, model, application, s1)
            st.write(f"Step 5 — s 44 earlier marks ({len(earlier_marks) or 'none supplied'}; each asked {n_samples}×)")
            s5 = step5_s44(client, model, application, s1, earlier_marks, n_samples)

            analysis = {
                "step1_interpretation": s1,
                "step2_s39_s42": s2,
                "step3_s41": s3,
                "step4_s43": s4,
                "step5_s44": s5,
            }
            first_draft = json.loads(json.dumps(analysis))  # copy, to show what changed

            review = {"note": "Reflection step switched off by user."}
            if use_reflection:
                st.write("Step 6 — reviewer checking the analysis (reflection)")
                review = step6_review(client, model, application, analysis)
                for step_name in review.get("steps_to_redo", []) or []:
                    if step_name in ("step3_s41", "step4_s43", "step5_s44"):
                        comment = (review.get("comments") or {}).get(step_name, "Re-check this step.")
                        st.write(f"↻ Re-running {step_name} with reviewer comments")
                        analysis[step_name] = redo_step(
                            client, model, application, s1, step_name,
                            analysis[step_name], comment, earlier_marks,
                        )

            st.write("Step 7 — writing the final report")
            report = step7_report(client, model, application, analysis, review)
            status.update(label=f"Done — {len(st.session_state['call_log'])} AI calls made", state="complete")
    except Exception as exc:  # e.g. invalid API key, network error
        st.error(f"The assessment could not be completed: {exc}")
        st.stop()

    st.session_state["result"] = {
        "application": application,
        "analysis": analysis,
        "first_draft": first_draft,
        "review": review,
        "report": report,
    }

# ---------------------------- Output --------------------------------------
if "result" in st.session_state:
    res = st.session_state["result"]
    analysis, report = res["analysis"], res["report"]
    overall = normalise_risk(report.get("overall_risk"))

    st.divider()
    st.subheader(f"Overall risk of refusal: {RISK_ICON[overall]} {overall}")
    st.markdown(f"**{report.get('headline', '')}**")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        risk_badge("s 39 / s 42", analysis["step2_s39_s42"])
    with c2:
        risk_badge("s 41", analysis["step3_s41"])
    with c3:
        risk_badge("s 43", analysis["step4_s43"])
    with c4:
        risk_badge("s 44", analysis["step5_s44"])

    tab_report, tab_steps, tab_review, tab_log = st.tabs(
        ["📄 Report", "🔎 Step-by-step analysis", "🧐 Reviewer (reflection)", "🧾 AI call log"]
    )
    with tab_report:
        report_md = report.get("report_markdown", "No report generated.")
        st.markdown(report_md)
        download = (
            f"# Trade Mark Pre-Check: {res['application']['mark']}\n\n"
            f"Date: {date.today().isoformat()}\n\n> {DISCLAIMER}\n\n"
            f"**Overall risk:** {overall}\n\n{report_md}\n"
        )
        st.download_button(
            "Download report (.md)", download,
            file_name=f"trade_mark_precheck_{res['application']['mark'].replace(' ', '_')}.md",
        )
    with tab_steps:
        for name, value in analysis.items():
            with st.expander(name, expanded=False):
                st.json(value)
    with tab_review:
        st.json(res["review"])
        redone = [k for k in analysis if analysis[k] != res["first_draft"][k]]
        if redone:
            st.markdown("**Steps changed after review:** " + ", ".join(redone))
            for k in redone:
                with st.expander(f"First draft of {k} (before review)"):
                    st.json(res["first_draft"][k])
        else:
            st.markdown("No steps were changed after review.")
    with tab_log:
        log = st.session_state.get("call_log", [])
        st.write(f"Total AI calls in this run: **{len(log)}**")
        for i, entry in enumerate(log, 1):
            with st.expander(f"Call {i}: {entry['task']}"):
                st.json(entry["output"])

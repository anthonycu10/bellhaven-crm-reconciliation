
import json
from collections import Counter

import streamlit as st

from review.db import get_review_items, record_decision


st.set_page_config(
    page_title="Bellhaven Reconciliation",
    page_icon="🏥",
    layout="wide",
)

# Styling only: these rules affect appearance, not data or decisions.
st.markdown(
    """
    <style>
    /* Global palette and typography */
    .stApp { background: #f5f7fb; color: #18263a; }
    [data-testid="stAppViewContainer"] > .main {
        background: #f5f7fb;
    }
    .block-container {
        max-width: 1260px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }
    h1, h2, h3, h4 { color: #162b45 !important; letter-spacing: -0.025em; }
    [data-testid="stSidebar"] { background: #edf2f7; }
    [data-testid="stSidebar"] * { color: #19314b; }

    /* Executive overview cards */
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e2e9f0;
        border-radius: 15px;
        padding: 18px 19px;
        box-shadow: 0 3px 12px rgba(26, 48, 70, .045);
    }
    [data-testid="stMetricLabel"] { color: #64748b; font-size: .9rem; }
    [data-testid="stMetricValue"] { color: #142c45; font-weight: 750; }

    /* Native Streamlit controls (no behavior changes) */
    div[data-baseweb="select"] > div {
        background: #ffffff;
        border-color: #d9e3ee;
        border-radius: 10px;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea {
        background: #ffffff;
        border-radius: 10px;
    }
    .stButton > button {
        border-radius: 10px;
        font-weight: 650;
        min-height: 43px;
    }
    .stButton > button[kind="primary"] {
        background: #087f75;
        border-color: #087f75;
        color: white;
    }
    .stButton > button[kind="primary"]:hover {
        background: #086c64;
        border-color: #086c64;
    }
    [data-testid="stExpander"] {
        background: #ffffff;
        border: 1px solid #e2e9f0;
        border-radius: 12px;
    }
    [data-testid="stCode"] { border-radius: 10px; }
    [data-testid="stAlert"] { border-radius: 11px; }

    /* Decorative guidance blocks; no review data is embedded here */
    .bh-hero {
        background: linear-gradient(115deg, #142f4a 0%, #1c5161 100%);
        border-radius: 19px;
        padding: 29px 34px 27px;
        color: #ffffff;
        margin-bottom: 18px;
    }
    .bh-overline { color: #a7e8e0; font-size: .72rem; font-weight: 750;
        letter-spacing: .15em; text-transform: uppercase; margin-bottom: 8px; }
    .bh-hero h1 { color: #ffffff !important; font-size: 2.05rem;
        margin: 0 0 6px 0; line-height: 1.2; }
    .bh-hero p { color: #dce8ed; margin: 0; font-size: .96rem; }
    .bh-step {
        min-height: 118px;
        background: #ffffff;
        border: 1px solid #e2e9f0;
        border-radius: 14px;
        padding: 16px 17px;
        margin-bottom: 8px;
    }
    .bh-step-id { display: inline-block; background: #e5f5f2; color: #08766f;
        font-size: .7rem; font-weight: 800; padding: 3px 8px;
        border-radius: 6px; margin-bottom: 8px; }
    .bh-step-title { color: #192e45; font-weight: 740;
        font-size: .96rem; margin-bottom: 4px; }
    .bh-step-copy { color: #66788c; font-size: .84rem; line-height: 1.4; }
    .bh-small-note { color: #66788c; font-size: .86rem; margin: 1px 0 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="bh-hero">
      <div class="bh-overline">Bellhaven · Data operations</div>
      <h1>CRM Reconciliation</h1>
      <p>Review website-to-CRM discrepancies, evaluate match evidence,
      and record human decisions in one place.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.info(
    "Review-only mode: decisions are saved to SQLite. "
    "This dashboard does not modify CRM records."
)

st.markdown("### How to review a finding")
step1, step2, step3 = st.columns(3)
with step1:
    st.markdown(
        """<div class="bh-step"><span class="bh-step-id">STEP 01</span>
        <div class="bh-step-title">Find an issue</div>
        <div class="bh-step-copy">Filter by status and category, then select
        a community from the review queue.</div></div>""",
        unsafe_allow_html=True,
    )
with step2:
    st.markdown(
        """<div class="bh-step"><span class="bh-step-id">STEP 02</span>
        <div class="bh-step-title">Check the evidence</div>
        <div class="bh-step-copy">Compare CRM and website values. Review
        matching scores and other candidates before deciding.</div></div>""",
        unsafe_allow_html=True,
    )
with step3:
    st.markdown(
        """<div class="bh-step"><span class="bh-step-id">STEP 03</span>
        <div class="bh-step-title">Record your decision</div>
        <div class="bh-step-copy">Enter your name and reasoning, then approve
        or reject. Approval never automatically changes CRM.</div></div>""",
        unsafe_allow_html=True,
    )


CATEGORY_LABELS = {
    "match_needs_update": "Field discrepancies",
    "ambiguous_match": "Ambiguous identity",
    "potential_wrong_parent": "Parent hierarchy",
    "website_only": "Missing CRM account",
    "crm_only": "CRM account absent from website",
}

ISSUE_LABELS = {
    "field_update_review": "Field correction",
    "care_type_review": "Care-type investigation",
    "identity_review": "Identity investigation",
    "account_creation_review": "Account creation investigation",
    "parent_review": "Parent hierarchy investigation",
    "crm_only_review": "CRM-only investigation",
}


def decode_json(value):
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def display_value(value):
    value = decode_json(value)

    if value is None or value == "":
        return "Not available"

    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2)

    return str(value)


def show_evidence(item):
    evidence = decode_json(item["evidence_json"]) or {}

    st.markdown("#### Matching evidence")
    st.caption(
        "Match score measures similarity; score gap indicates separation "
        "from the next candidate. Confirm identity using the source records."
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Match score",
        evidence.get("score")
        if evidence.get("score") is not None
        else "N/A",
    )

    col2.metric(
        "Score gap",
        evidence.get("score_gap")
        if evidence.get("score_gap") is not None
        else "N/A",
    )

    col3.metric(
        "Candidate count",
        evidence.get("candidate_count", "N/A"),
    )

    if evidence.get("recommended_action"):
        st.write(
            "**Recommended action:**",
            evidence["recommended_action"],
        )

    field_comparison = evidence.get("field_comparison")

    if field_comparison:
        st.markdown("#### Field comparison")
        st.json(field_comparison)

    candidates = evidence.get("top_candidates") or []

    if candidates:
        st.markdown("#### Candidate CRM accounts")

        for index, candidate in enumerate(candidates[:5], 1):
            st.write(
                f"{index}. "
                f"{candidate.get('crm_name', 'Unknown')} "
                f"— score {candidate.get('score', 'N/A')} "
                f"— ID {candidate.get('crm_account_id', 'N/A')}"
            )

    website = evidence.get("website_record")

    if website:
        with st.expander("Original website record"):
            st.json(website)

    comparisons = evidence.get("candidate_comparisons")

    if comparisons:
        with st.expander("Detailed candidate comparisons"):
            st.json(comparisons)


def show_item(item):
    issue_label = ISSUE_LABELS.get(
        item["issue_type"],
        item["issue_type"],
    )

    st.caption("SELECTED REVIEW ITEM")
    st.markdown(f"### {item['website_name']}")
    st.write("**Issue:**", issue_label)
    st.write("**Status:**", item["status"])
    st.write("**CRM account:**", item["crm_name"] or "Not established")
    st.write("**CRM ID:**", item["crm_account_id"] or "N/A")

    if item.get("website_detail_url"):
        st.markdown(
            f"[Open website community page]"
            f"({item['website_detail_url']})"
        )

    st.divider()

    if item["field_name"]:
        st.markdown("#### Proposed discrepancy")
        st.caption("Compare the currently stored CRM value with the website proposal.")

        left, right = st.columns(2)

        with left:
            st.write("**Current CRM value**")
            st.code(display_value(item["old_value"]))

        with right:
            st.write("**Proposed website value**")
            st.code(display_value(item["proposed_value"]))

        if decode_json(item["proposed_value"]) is None:
            st.warning(
                "No executable replacement value is available. "
                "This item requires investigation."
            )

    else:
        st.warning(
            "This is an investigation task, not a "
            "pre-authorized CRM modification."
        )

    show_evidence(item)

    st.divider()

    if item["status"] not in ("pending", "needs_re_review"):
        st.info(
            f"This item has already been reviewed: {item['status']}."
        )
        return

    st.markdown("#### Human review decision")
    st.caption("Only approve when the underlying evidence supports the proposal.")

    st.caption(
        "Approve means accepting this review proposal or "
        "investigation outcome for tracking. "
        "It does not execute a CRM change."
    )

    reviewer = st.text_input(
        "Reviewer name",
        key=f"reviewer_{item['id']}",
    )

    reason = st.text_area(
        "Decision notes",
        key=f"reason_{item['id']}",
        placeholder=(
            "Explain the evidence supporting your decision."
        ),
    )

    approve_col, reject_col = st.columns(2)

    with approve_col:
        approve = st.button(
            "Approve review item",
            key=f"approve_{item['id']}",
            type="primary",
            use_container_width=True,
        )

    with reject_col:
        reject = st.button(
            "Reject review item",
            key=f"reject_{item['id']}",
            use_container_width=True,
        )

    if approve or reject:
        if not reviewer.strip():
            st.error("Please enter a reviewer name.")
            return

        if not reason.strip():
            st.error(
                "Please enter decision notes explaining "
                "your review."
            )
            return

        decision = "approved" if approve else "rejected"

        try:
            record_decision(
                review_item_id=item["id"],
                decision=decision,
                reviewer=reviewer,
                reason=reason,
            )

            st.success(
                f"Review item #{item['id']} marked {decision}."
            )
            st.rerun()

        except ValueError as exc:
            st.error(str(exc))


# ---------------------------------------------------------
# Dashboard metrics
# ---------------------------------------------------------

all_items = get_review_items()
counts = Counter(item["status"] for item in all_items)

st.markdown("### Reconciliation overview")
st.caption("Current review-queue status from SQLite. Counts update as decisions are recorded.")
m1, m2, m3, m4 = st.columns(4)

m1.metric("Total review items", len(all_items))
m2.metric("Pending", counts["pending"])
m3.metric("Approved", counts["approved"])
m4.metric("Rejected", counts["rejected"])

if counts["needs_re_review"]:
    st.warning(
        f"{counts['needs_re_review']} item(s) require "
        "re-review because their source evidence changed."
    )

st.divider()

# ---------------------------------------------------------
# Filters
# ---------------------------------------------------------

st.subheader("Review queue")
st.caption("Use the filters to narrow the queue. All findings remain available under **All**.")

filter_col1, filter_col2 = st.columns(2)

with filter_col1:
    status_filter = st.selectbox(
        "Filter by status",
        [
            "Pending / Needs re-review",
            "All",
            "Approved",
            "Rejected",
            "Applied",
            "Failed",
        ],
    )

with filter_col2:
    category_filter = st.selectbox(
        "Filter by category",
        ["All"] + sorted(CATEGORY_LABELS.values()),
    )

filtered = all_items

if status_filter == "Pending / Needs re-review":
    filtered = [
        item for item in filtered
        if item["status"] in ("pending", "needs_re_review")
    ]
elif status_filter != "All":
    filtered = [
        item for item in filtered
        if item["status"] == status_filter.lower()
    ]

if category_filter != "All":
    filtered = [
        item for item in filtered
        if CATEGORY_LABELS.get(item["review_category"])
        == category_filter
    ]

st.write(f"**Showing {len(filtered)} review items**")

if not filtered:
    st.info("No review items match these filters.")
    st.stop()

# ---------------------------------------------------------
# Review item selection
# ---------------------------------------------------------

def item_label(item):
    return (
        f"#{item['id']} | {item['website_name']} "
        f"| {ISSUE_LABELS.get(item['issue_type'], item['issue_type'])} "
        f"| {item['status']}"
    )


selected_id = st.selectbox(
    "Select an item to review",
    options=[item["id"] for item in filtered],
    format_func=lambda item_id: item_label(
        next(
            item for item in filtered
            if item["id"] == item_id
        )
    ),
)

selected_item = next(
    item for item in filtered
    if item["id"] == selected_id
)

st.divider()
show_item(selected_item)


import os
import streamlit as st

from crm.executor import evaluate_item
from crm.client import CRMClient
from crm.write_executor import execute_item, load_approved_item
from review.db import get_connection


st.set_page_config(
    page_title="Apply Approved Changes",
    page_icon="🔒",
    layout="wide",
)

st.title("Apply Approved CRM Changes")

st.caption(
    "Only explicitly approved field corrections can be "
    "applied. Investigation items are not executable."
)

with get_connection() as conn:
    rows = conn.execute(
        """
        SELECT *
        FROM review_items
        WHERE status = 'approved'
          AND issue_type = 'field_update_review'
        ORDER BY id
        """
    ).fetchall()

items = [dict(row) for row in rows]

if not items:
    st.info("No approved field corrections are awaiting execution.")
    st.stop()

item_by_id = {item["id"]: item for item in items}

selected_id = st.selectbox(
    "Select an approved change",
    options=list(item_by_id),
    format_func=lambda item_id: (
        f"#{item_id} | "
        f"{item_by_id[item_id]['website_name']} | "
        f"{item_by_id[item_id]['field_name']}"
    ),
)

item = item_by_id[selected_id]

st.subheader(item["website_name"])
st.write("**CRM account:**", item["crm_name"])
st.write("**Account ID:**", item["crm_account_id"])
st.write("**Field:**", item["field_name"])

left, right = st.columns(2)

with left:
    st.write("**Reviewed CRM value**")
    st.code(str(item["old_value"]))

with right:
    st.write("**Proposed value**")
    st.code(str(item["proposed_value"]))

if item.get("website_detail_url"):
    st.link_button(
        "View website evidence",
        item["website_detail_url"],
    )

st.divider()

try:
    approved_item = load_approved_item(selected_id)
    validation = evaluate_item(
        approved_item,
        CRMClient(),
    )
except Exception as exc:
    st.error(f"Validation failed: {exc}")
    st.stop()

if validation["status"] != "ready":
    st.error(
        "This change is not executable: "
        + validation.get("reason", "Validation failed.")
    )
    st.stop()

st.success("Approval and current CRM values validated.")

st.write(
    "**Current live CRM value:**",
    validation["current_value"],
)

st.write(
    "**Proposed CRM value:**",
    validation["proposed_value"],
)

st.divider()

if st.button("Run dry run", use_container_width=True):
    try:
        execute_item(selected_id, execute=False)
        st.success(
            "Dry run completed. "
            "No CRM modification was performed."
        )
    except Exception as exc:
        st.error(str(exc))

writes_enabled = (
    os.getenv("ENABLE_CRM_WRITES") == "true"
)

if not writes_enabled:
    st.warning(
        "Live CRM writes are disabled. "
        "Set ENABLE_CRM_WRITES=true to enable them."
    )

confirm = st.checkbox(
    "I confirm this approved change should be "
    "written to the live CRM."
)

if st.button(
    "Apply approved change to CRM",
    type="primary",
    disabled=not (writes_enabled and confirm),
    use_container_width=True,
):
    try:
        # Recheck approval immediately before execution.
        load_approved_item(selected_id)

        execute_item(selected_id, execute=True)

        with get_connection() as conn:
            result = conn.execute(
                "SELECT status FROM review_items WHERE id = ?",
                (selected_id,),
            ).fetchone()

        if result and result["status"] == "applied":
            st.success(
                "CRM update verified and marked applied."
            )
            st.rerun()
        else:
            st.error(
                "CRM update was not confirmed as applied. "
                "Check the audit log before retrying."
            )

    except Exception as exc:
        st.error(
            f"CRM execution failed: {exc}. "
            "Check the audit log and live CRM record "
            "before retrying."
        )

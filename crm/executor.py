
"""
Read-only preview of approved CRM field changes.

No PATCH or POST operations are performed.
"""

import json

from crm.client import CRMClient
from review.db import get_connection


ALLOWED_FIELDS = {
    "phone",
    "billing_zip",
    "billing_street",
    "billing_city",
    "billing_state",
}

NON_EXECUTABLE_TYPES = {
    "identity_review",
    "account_creation_review",
    "care_type_review",
    "parent_review",
    "crm_only_review",
}


def decode(value):
    if value is None:
        return None
    return json.loads(value)


def get_approved_items():
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM review_items
            WHERE status = 'approved'
            ORDER BY id
            """
        ).fetchall()

    return [dict(row) for row in rows]


def evaluate_item(item, client):
    result = {
        "review_item_id": item["id"],
        "website_name": item["website_name"],
        "crm_account_id": item["crm_account_id"],
        "field_name": item["field_name"],
        "status": "skipped",
        "reason": None,
    }

    if item["issue_type"] in NON_EXECUTABLE_TYPES:
        result["reason"] = (
            "Investigation-only item; CRM write prohibited."
        )
        return result

    if item["issue_type"] != "field_update_review":
        result["reason"] = "Unsupported issue type."
        return result

    field = item["field_name"]

    if field not in ALLOWED_FIELDS:
        result["reason"] = "Field is not in the write allowlist."
        return result

    account_id = item["crm_account_id"]

    if not account_id:
        result["reason"] = "No established CRM account."
        return result

    old_value = decode(item["old_value"])
    proposed_value = decode(item["proposed_value"])

    if not isinstance(proposed_value, str):
        result["reason"] = (
            "Proposed value is missing or invalid."
        )
        return result

    if not proposed_value.strip():
        result["reason"] = "Proposed value is empty."
        return result

    account = client.get_account(account_id)
    current_value = account.get(field)

    result["current_value"] = current_value
    result["reviewed_old_value"] = old_value
    result["proposed_value"] = proposed_value
    result["updated_at"] = account.get("updated_at")

    if current_value != old_value:
        result["status"] = "blocked"
        result["reason"] = (
            "CRM value changed since the review snapshot."
        )
        return result

    if current_value == proposed_value:
        result["status"] = "skipped"
        result["reason"] = (
            "CRM already contains the proposed value."
        )
        return result

    if item["status"] != "approved":
        result["status"] = "eligible"
        result["reason"] = (
            "Technical checks passed, but human approval "
            "is required before execution."
        )
        return result

    result["status"] = "ready"
    result["reason"] = (
        "Approved field update passed read-only checks."
    )
    return result

def preview_approved_changes():
    items = get_approved_items()

    print(f"\nApproved review items: {len(items)}")

    if not items:
        print("No approved items to preview.")
        return []

    client = CRMClient()
    results = []

    for item in items:
        try:
            result = evaluate_item(item, client)
        except Exception as exc:
            result = {
                "review_item_id": item["id"],
                "website_name": item["website_name"],
                "status": "error",
                "reason": str(exc),
            }

        results.append(result)

        print("\n" + "-" * 60)
        print(json.dumps(result, indent=2))

    print("\n" + "=" * 60)
    print("DRY RUN COMPLETE — NO CRM WRITES PERFORMED")

    return results


if __name__ == "__main__":
    preview_approved_changes()

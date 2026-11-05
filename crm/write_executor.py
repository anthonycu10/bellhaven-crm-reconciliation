
import argparse
import json
import os
import sqlite3

from crm.client import CRMClient
from crm.executor import evaluate_item
from review.db import get_connection, utc_now


def load_approved_item(item_id):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM review_items
            WHERE id = ?
            """,
            (item_id,),
        ).fetchone()

        if row is None:
            raise ValueError("Review item not found.")

        item = dict(row)

        decision = conn.execute(
            """
            SELECT decision
            FROM review_decisions
            WHERE review_item_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (item_id,),
        ).fetchone()

    if item["status"] != "approved":
        raise ValueError("Item is not approved.")

    if decision is None or decision["decision"] != "approved":
        raise ValueError("No valid human approval found.")

    if item["issue_type"] != "field_update_review":
        raise ValueError("Investigation-only item cannot execute.")

    return item


def log_attempt(item, validation, dry_run, result, response):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO write_attempts (
                review_item_id,
                attempted_at,
                dry_run,
                crm_account_id,
                field_name,
                old_value,
                proposed_value,
                result,
                response_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["id"],
                utc_now(),
                int(dry_run),
                item["crm_account_id"],
                item["field_name"],
                item["old_value"],
                item["proposed_value"],
                result,
                json.dumps(response),
            ),
        )


def execute_item(item_id, execute=False):
    item = load_approved_item(item_id)
    client = CRMClient()

    validation = evaluate_item(item, client)

    if validation["status"] != "ready":
        print("BLOCKED:", validation["reason"])
        return

    payload = {
        item["field_name"]: validation["proposed_value"]
    }

    print("\nCRM UPDATE")
    print("Account:", item["crm_account_id"])
    print("Field:", item["field_name"])
    print("Current:", validation["current_value"])
    print("Proposed:", validation["proposed_value"])

    if not execute:
        log_attempt(
            item,
            validation,
            True,
            "dry_run_ready",
            {"payload": payload},
        )
        print("\nDRY RUN — no CRM write performed.")
        return

    if os.getenv("ENABLE_CRM_WRITES") != "true":
        raise RuntimeError(
            "Live execution disabled. "
            "ENABLE_CRM_WRITES=true is required."
        )

    # One final check immediately before PATCH.
    latest = client.get_account(item["crm_account_id"])

    if latest.get(item["field_name"]) != validation["current_value"]:
        log_attempt(
            item,
            validation,
            False,
            "blocked_stale",
            {"latest": latest},
        )
        print("BLOCKED: CRM changed before PATCH.")
        return

    try:
        response = client.patch_account(
            item["crm_account_id"],
            payload,
        )

        verified = client.get_account(item["crm_account_id"])

        if verified.get(item["field_name"]) != payload[item["field_name"]]:
            log_attempt(
                item,
                validation,
                False,
                "verification_failed",
                {
                    "patch_response": response,
                    "verified": verified,
                },
            )
            print("FAILED: PATCH not verified.")
            return

        # Mark applied and record the audit in one transaction.
        with get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE review_items
                SET status = 'applied',
                    applied_at = ?
                WHERE id = ?
                  AND status = 'approved'
                """,
                (utc_now(), item_id),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Review item is no longer approved. "
                    "Manual reconciliation required."
                )

            conn.execute(
                """
                INSERT INTO write_attempts (
                    review_item_id,
                    attempted_at,
                    dry_run,
                    crm_account_id,
                    field_name,
                    old_value,
                    proposed_value,
                    result,
                    response_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    utc_now(),
                    0,
                    item["crm_account_id"],
                    item["field_name"],
                    item["old_value"],
                    item["proposed_value"],
                    "applied",
                    json.dumps({
                        "patch_response": response,
                        "verified": verified,
                    }),
                ),
            )

        print("SUCCESS: CRM update verified and recorded.")

    except Exception as exc:
        # A network error does not necessarily mean PATCH failed.
        # Check the live CRM before deciding what happened.
        try:
            latest = client.get_account(item["crm_account_id"])
            actual_value = latest.get(item["field_name"])

            if actual_value == payload[item["field_name"]]:
                result = "applied_after_error"
                details = {
                    "error": str(exc),
                    "verified": latest,
                }

                # Record successful verification and status together.
                with get_connection() as conn:
                    conn.execute(
                        """
                        UPDATE review_items
                        SET status = 'applied',
                            applied_at = ?
                        WHERE id = ?
                          AND status = 'approved'
                        """,
                        (utc_now(), item_id),
                    )

                    conn.execute(
                        """
                        INSERT INTO write_attempts (
                            review_item_id, attempted_at, dry_run,
                            crm_account_id, field_name, old_value,
                            proposed_value, result, response_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item["id"], utc_now(), 0,
                            item["crm_account_id"], item["field_name"],
                            item["old_value"], item["proposed_value"],
                            result, json.dumps(details),
                        ),
                    )

                print("SUCCESS: CRM value verified after an error.")
                return

            result = "error_not_applied"

        except Exception as verification_error:
            result = "outcome_unknown"
            details = {
                "patch_error": str(exc),
                "verification_error": str(verification_error),
            }
        else:
            details = {
                "patch_error": str(exc),
                "actual_value": actual_value,
            }

        log_attempt(
            item,
            validation,
            False,
            result,
            details,
        )

        if result == "outcome_unknown":
            raise RuntimeError(
                "CRM write outcome is unknown. "
                "Inspect the live CRM and audit log before retrying."
            ) from exc

        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--item-id", type=int, required=True)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Enable live PATCH (requires environment opt-in).",
    )

    args = parser.parse_args()
    execute_item(args.item_id, execute=args.execute)

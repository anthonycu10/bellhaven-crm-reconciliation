
"""
Build a persistent review queue from classified matching results.

Read-only with respect to CRM.
Uses SQLite to store proposals and review tasks.
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

from review.db import (
    get_connection,
    initialize_database,
    utc_now,
)


ROOT = Path(__file__).resolve().parents[1]

CLASSIFIED_PATH = ROOT / "data/processed/classified_results.json"
WEBSITE_PATH = ROOT / "data/bellhaven_communities.json"

CRM_FIELDS = {
    "name": "name",
    "street": "billing_street",
    "city": "billing_city",
    "state": "billing_state",
    "zip": "billing_zip",
    "phone": "phone",
    "care_type": "care_type",
    "parent_id": "parent_id",
}

EXPECTED_PARENT_ID = "0015QAPLGS3FVYEEEM"


def canonical_json(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )


def digest(value):
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_crm_records():
    import os

    # Prefer the exact CRM snapshot selected by the daily pipeline.
    selected = os.environ.get("BELLHAVEN_CRM_SNAPSHOT")

    if selected:
        path = Path(selected)

        if not path.is_file():
            raise FileNotFoundError(
                f"Selected CRM snapshot does not exist: {path}"
            )
    else:
        # Preserve existing standalone behavior:
        # use the most recently modified CRM snapshot.
        files = sorted(
            (ROOT / "data").glob("crm_accounts_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not files:
            raise FileNotFoundError("No CRM snapshot found.")

        path = files[0]

    data = load_json(path)

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get(
            "accounts",
            data.get("records"),
        )
    else:
        records = None

    if not isinstance(records, list):
        raise ValueError(
            f"CRM snapshot must contain an account list: {path}"
        )

    print(f"Using CRM snapshot: {path.name}")

    return records


def load_website_records():
    data = load_json(WEBSITE_PATH)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("communities", "records"):
            if isinstance(data.get(key), list):
                return data[key]

    raise ValueError(
        "Website JSON must contain a community list."
    )


def get_comparison(result, account_id):
    for comparison in result.get(
        "all_candidate_comparisons", []
    ):
        if comparison.get("crm_account_id") == account_id:
            return comparison

    return {}


def get_field_evidence(result, field_name):
    candidate = result.get("best_candidate") or {}

    comparison = get_comparison(
        result,
        candidate.get("crm_account_id"),
    )

    for field in comparison.get("field_comparisons", []):
        if field.get("field") == field_name:
            return field

    return (
        comparison.get("supporting_evidence", {})
        .get(field_name)
        or candidate.get("supporting_evidence", {})
        .get(field_name, {})
    )


def make_issue(
    result,
    issue_type,
    field_name=None,
    old_value=None,
    proposed_value=None,
    evidence=None,
):
    candidate = result.get("best_candidate") or {}

    website_url = result.get("website_detail_url") or ""
    account_id = candidate.get("crm_account_id") or None

    # Identity investigations and website-only tasks are
    # tied to the website community, not a tentative account.
    if issue_type in ("identity_review", "account_creation_review"):
        account_id_for_key = None
    else:
        account_id_for_key = account_id

    issue_key = digest({
        "website_url": website_url,
        "account_id": account_id_for_key,
        "issue_type": issue_type,
        "field_name": field_name,
    })

    evidence = evidence or {}

    source_hash = digest({
        "old_value": old_value,
        "proposed_value": proposed_value,
        "evidence": evidence,
    })

    return {
        "issue_key": issue_key,
        "source_hash": source_hash,
        "website_name": result.get("website_name") or "",
        "website_detail_url": website_url,
        "crm_account_id": account_id,
        "crm_name": candidate.get("crm_name"),
        "review_category": result.get("review_category"),
        "issue_type": issue_type,
        "field_name": field_name,
        "old_value": canonical_json(old_value),
        "proposed_value": canonical_json(proposed_value),
        "evidence_json": canonical_json(evidence),
    }


def build_issues(result, crm_by_id, website_by_url):
    category = result.get("review_category")
    candidate = result.get("best_candidate") or {}

    account_id = candidate.get("crm_account_id")
    crm = crm_by_id.get(account_id, {})

    website = website_by_url.get(
        result.get("website_detail_url"), {}
    )

    base_evidence = {
        "category": category,
        "review_flag": result.get("review_flag"),
        "score": candidate.get("score"),
        "score_gap": result.get("score_gap"),
        "candidate_count": result.get(
            "review_candidate_count"
        ),
        "recommended_action": result.get(
            "recommended_action"
        ),
        "top_candidates": result.get(
            "top_candidates", []
        ),
    }

    if category == "confirmed_match":
        return []

    if category == "website_only":
        return [
            make_issue(
                result,
                "account_creation_review",
                evidence={
                    **base_evidence,
                    "website_record": website,
                },
            )
        ]

    if category == "ambiguous_match":
        return [
            make_issue(
                result,
                "identity_review",
                evidence={
                    **base_evidence,
                    "website_record": website,
                    "candidate_comparisons": result.get(
                        "all_candidate_comparisons", []
                    ),
                },
            )
        ]

    issues = []

    if category == "potential_wrong_parent":
        issues.append(
            make_issue(
                result,
                "parent_review",
                field_name="parent_id",
                old_value=crm.get("parent_id"),
                proposed_value=EXPECTED_PARENT_ID,
                evidence={
                    **base_evidence,
                    "current_parent_name": crm.get(
                        "parent_name"
                    ),
                    "expected_parent_id": EXPECTED_PARENT_ID,
                },
            )
        )

    for field_name in result.get("field_issues", []):
        crm_field = CRM_FIELDS.get(field_name)

        if not crm_field:
            continue

        field_evidence = get_field_evidence(
            result, field_name
        )

        # Care-type terminology is not a safe automatic
        # overwrite. Keep it as a review-only task.
        if field_name == "care_type":
            issue_type = "care_type_review"
            proposed = None
        else:
            issue_type = "field_update_review"

            website_field_map = {
                "name": "name",
                "street": "street_address",
                "city": "detail_city",
                "state": "detail_state",
                "zip": "zip_code",
                "phone": "phone",
            }

            website_key = website_field_map.get(field_name)
            proposed = (
                website.get(website_key)
                if website_key
                else None
            )

        issues.append(
            make_issue(
                result,
                issue_type,
                field_name=crm_field,
                old_value=crm.get(crm_field),
                proposed_value=proposed,
                evidence={
                    **base_evidence,
                    "field_comparison": field_evidence,
                    "website_record": website,
                    "requires_manual_verification": True,
                },
            )
        )

    return issues


def upsert_issue(conn, issue):
    now = utc_now()

    existing = conn.execute(
        """
        SELECT id, source_hash, status
        FROM review_items
        WHERE issue_key = ?
        """,
        (issue["issue_key"],),
    ).fetchone()

    if existing is None:
        conn.execute(
            """
            INSERT INTO review_items (
                issue_key,
                source_hash,
                website_name,
                website_detail_url,
                crm_account_id,
                crm_name,
                review_category,
                issue_type,
                field_name,
                old_value,
                proposed_value,
                evidence_json,
                status,
                first_seen_at,
                last_seen_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                'pending', ?, ?
            )
            """,
            (
                issue["issue_key"],
                issue["source_hash"],
                issue["website_name"],
                issue["website_detail_url"],
                issue["crm_account_id"],
                issue["crm_name"],
                issue["review_category"],
                issue["issue_type"],
                issue["field_name"],
                issue["old_value"],
                issue["proposed_value"],
                issue["evidence_json"],
                now,
                now,
            ),
        )
        return "inserted"

    if existing["source_hash"] == issue["source_hash"]:
        conn.execute(
            """
            UPDATE review_items
            SET last_seen_at = ?
            WHERE id = ?
            """,
            (now, existing["id"]),
        )
        return "unchanged"

    # Source evidence changed. Previous approval is no
    # longer sufficient; require another human review.
    conn.execute(
        """
        UPDATE review_items
        SET source_hash = ?,
            website_name = ?,
            website_detail_url = ?,
            crm_account_id = ?,
            crm_name = ?,
            review_category = ?,
            issue_type = ?,
            field_name = ?,
            old_value = ?,
            proposed_value = ?,
            evidence_json = ?,
            status = 'needs_re_review',
            last_seen_at = ?,
            decided_at = NULL,
            applied_at = NULL
        WHERE id = ?
        """,
        (
            issue["source_hash"],
            issue["website_name"],
            issue["website_detail_url"],
            issue["crm_account_id"],
            issue["crm_name"],
            issue["review_category"],
            issue["issue_type"],
            issue["field_name"],
            issue["old_value"],
            issue["proposed_value"],
            issue["evidence_json"],
            now,
            existing["id"],
        ),
    )

    return "changed"


def build_crm_only_issues():
    """
    Convert CRM-only findings into review tasks.

    These are investigation tasks only.
    No automatic deactivation or deletion.
    """
    path = ROOT / "data/processed/crm_only_results.json"

    if not path.exists():
        raise FileNotFoundError(
            "Run python -m analysis.find_crm_only first."
        )

    results = load_json(path)
    issues = []

    for item in results:
        if item["category"] != "crm_only_review":
            continue

        account = item["account"]
        account_id = item["account_id"]

        issue_key = digest({
            "account_id": account_id,
            "issue_type": "crm_only_review",
        })

        evidence = {
            "reason": (
                "CRM account belongs to the Bellhaven parent "
                "but has no credible website match."
            ),
            "account": account,
            "recommended_action": (
                "Investigate whether the community was closed, "
                "renamed, sold, or removed from the website."
            ),
        }

        issues.append({
            "issue_key": issue_key,
            "source_hash": digest(evidence),
            "website_name": item["name"],
            "website_detail_url": "",
            "crm_account_id": account_id,
            "crm_name": item["name"],
            "review_category": "crm_only",
            "issue_type": "crm_only_review",
            "field_name": None,
            "old_value": canonical_json(
                account.get("status")
            ),
            "proposed_value": canonical_json(None),
            "evidence_json": canonical_json(evidence),
        })

    return issues

def populate_queue():
    initialize_database()

    classified = load_json(CLASSIFIED_PATH)
    crm_records = load_crm_records()
    website_records = load_website_records()

    crm_by_id = {
        record["account_id"]: record
        for record in crm_records
    }

    website_by_url = {
        record["detail_url"]: record
        for record in website_records
        if record.get("detail_url")
    }

    counts = Counter()
    issue_types = Counter()


    with get_connection() as conn:
        for result in classified["community_results"]:
            issues = build_issues(
                result,
                crm_by_id,
                website_by_url,
            )

            for issue in issues:
                action = upsert_issue(conn, issue)
                counts[action] += 1
                issue_types[issue["issue_type"]] += 1

        # Include CRM accounts absent from the website.
        for issue in build_crm_only_issues():
            action = upsert_issue(conn, issue)
            counts[action] += 1
            issue_types[issue["issue_type"]] += 1


    print("\nQUEUE SYNC RESULTS")
    print("=" * 45)

    for action in ("inserted", "unchanged", "changed"):
        print(f"{action}: {counts[action]}")

    print("\nISSUE TYPES")
    for issue_type, count in sorted(issue_types.items()):
        print(f"{issue_type}: {count}")

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM review_items
            GROUP BY status
            ORDER BY status
            """
        ).fetchall()

    print("\nDATABASE STATUS COUNTS")
    for row in rows:
        print(f"{row['status']}: {row['count']}")


if __name__ == "__main__":
    populate_queue()

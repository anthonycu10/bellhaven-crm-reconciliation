
import json
from collections import Counter
from pathlib import Path

from review.queue import (
    CLASSIFIED_PATH,
    EXPECTED_PARENT_ID,
    ROOT,
    load_crm_records,
)

OUTPUT_PATH = ROOT / "data/processed/crm_only_results.json"


def main():
    with open(CLASSIFIED_PATH, encoding="utf-8") as f:
        classified = json.load(f)

    accounts = load_crm_records()
    communities = classified["community_results"]

    confirmed_ids = set()
    candidate_ids = set()

    for community in communities:
        best = community.get("best_candidate") or {}

        if (
            community.get("identity_established")
            and best.get("crm_account_id")
        ):
            confirmed_ids.add(best["crm_account_id"])

        # Protect every plausible website candidate from
        # being incorrectly called a definite CRM-only record.
        for candidate in community.get(
            "all_candidate_comparisons", []
        ):
            if candidate.get("score", 0) >= 65:
                candidate_ids.add(candidate["crm_account_id"])

    bellhaven_accounts = [
        account
        for account in accounts
        if account.get("parent_id") == EXPECTED_PARENT_ID
    ]

    results = []

    for account in bellhaven_accounts:
        account_id = account["account_id"]

        if account_id in confirmed_ids:
            category = "matched_to_website"
        elif account_id in candidate_ids:
            category = "possible_website_match"
        else:
            category = "crm_only_review"

        results.append({
            "account_id": account_id,
            "name": account.get("name"),
            "parent_id": account.get("parent_id"),
            "status": account.get("status"),
            "category": category,
            "account": account,
        })

    counts = Counter(
        item["category"] for item in results
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            results,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print("CRM REVERSE RECONCILIATION")
    print("=" * 55)
    print("Direct Bellhaven child accounts:", len(results))

    for category, count in sorted(counts.items()):
        print(f"{category}: {count}")

    print("\nCRM-ONLY INVESTIGATION CANDIDATES")

    for item in results:
        if item["category"] == "crm_only_review":
            print(
                item["account_id"],
                "|",
                item["name"],
                "|",
                item["status"],
            )

    print("\nSaved:", OUTPUT_PATH)
    print(
        "\nNo CRM records were modified. "
        "CRM-only means investigate, not deactivate."
    )


if __name__ == "__main__":
    main()

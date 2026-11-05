import json
from pathlib import Path

from matching.classify import get_candidate_comparison


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CLASSIFIED_FILE = (
    PROJECT_ROOT / "data" / "processed" / "classified_results.json"
)

CRM_FILE = (
    PROJECT_ROOT / "data" / "crm_accounts_20261104_005621.json"
)


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main():
    classified = load_json(CLASSIFIED_FILE)
    crm_records = load_json(CRM_FILE)

    crm_by_id = {
        record["account_id"]: record
        for record in crm_records
    }

    categories_to_inspect = {
        "match_needs_update",
        "ambiguous_match",
        "potential_wrong_parent",
    }

    for result in classified["community_results"]:
        if result["review_category"] not in categories_to_inspect:
            continue

        print("\n" + "=" * 100)
        print("WEBSITE:", result["website_name"])
        print("CATEGORY:", result["review_category"])
        print("REVIEW FLAG:", result.get("review_flag"))
        print("SCORE GAP:", result.get("score_gap"))
        print("CANDIDATE COUNT:", result.get("review_candidate_count"))
        print("IDENTITY ESTABLISHED:", result.get("identity_established"))
        print("FIELD ISSUES:", result.get("field_issues"))
        print("ISSUE FLAGS:", result.get("issue_flags"))

        best = result.get("best_candidate") or {}
        best_id = best.get("crm_account_id")

        print("\nBEST CRM CANDIDATE")
        print("Name:", best.get("crm_name"))
        print("ID:", best_id)
        print("Score:", best.get("score"))
        print("Classification:", best.get("classification"))

        crm_record = crm_by_id.get(best_id, {})
        print("Parent:", crm_record.get("parent_name"))
        print("Parent ID:", crm_record.get("parent_id"))

        comparison = get_candidate_comparison(result, best_id)

        print("\nBEST CANDIDATE FIELD COMPARISONS")
        for field in comparison.get("field_comparisons", []):
            print(
                f"  {field.get('field'):<12} "
                f"website={str(field.get('website_value')):<35} "
                f"CRM={str(field.get('crm_value')):<35} "
                f"status={field.get('status'):<15} "
                f"similarity={field.get('similarity')}"
            )

        print("\nBEST CANDIDATE SUPPORTING EVIDENCE")
        for field, evidence in best.get(
            "supporting_evidence", {}
        ).items():
            print(f"  {field}: {evidence}")

        print("\nTOP CANDIDATES")
        for candidate in result.get("top_candidates", []):
            candidate_id = candidate.get("crm_account_id")
            candidate_comparison = get_candidate_comparison(
                result,
                candidate_id
            )
            candidate_crm = crm_by_id.get(candidate_id, {})

            print(
                f"\n  {candidate.get('crm_name')} "
                f"| ID: {candidate_id} "
                f"| score: {candidate.get('score')} "
                f"| parent: {candidate_crm.get('parent_name')}"
            )

            for field in candidate_comparison.get(
                "field_comparisons", []
            ):
                print(
                    f"    {field.get('field'):<12} "
                    f"status={field.get('status'):<15} "
                    f"similarity={field.get('similarity')}"
                )


if __name__ == "__main__":
    main()
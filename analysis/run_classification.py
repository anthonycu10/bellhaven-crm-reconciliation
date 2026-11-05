import os
import json
from pathlib import Path
from collections import Counter

from matching.classify import classify_all


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MATCHING_FILE = (
    PROJECT_ROOT / "data" / "processed" / "matching_results.json"
)

CRM_FILE = Path(
    os.environ.get(
        "BELLHAVEN_CRM_SNAPSHOT",
        str(
            PROJECT_ROOT
            / "data"
            / "crm_accounts_20261104_005621.json"
        ),
    )
)

OUTPUT_FILE = (
    PROJECT_ROOT / "data" / "processed" / "classified_results.json"
)


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main():
    matching_results = load_json(MATCHING_FILE)
    crm_records = load_json(CRM_FILE)

    classified_results = classify_all(
        matching_results,
        crm_records
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            classified_results,
            file,
            indent=2,
            ensure_ascii=False
        )

    categories = Counter(
        result["review_category"]
        for result in classified_results["community_results"]
    )

    print("\n========== CLASSIFICATION SUMMARY ==========")

    print("Website communities:", len(
        classified_results["community_results"]
    ))

    for category, count in sorted(categories.items()):
        print(f"{category}: {count}")

    print("\n========== INDIVIDUAL RESULTS ==========")

    for result in classified_results["community_results"]:
        candidate = result.get("best_candidate") or {}

        print(
            f"{result['website_name']:<48} "
            f"{result['review_category']:<24} "
            f"{candidate.get('crm_name', 'No candidate')}"
        )

    print("\nSaved to:", OUTPUT_FILE)


if __name__ == "__main__":
    main()

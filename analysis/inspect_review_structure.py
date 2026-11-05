
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CLASSIFIED_PATH = (
    PROJECT_ROOT / "data" / "processed" / "classified_results.json"
)

with open(CLASSIFIED_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

print("=" * 70)
print("TOP-LEVEL STRUCTURE")
print("=" * 70)

print("Top-level keys:", list(data.keys()))

results = data["community_results"]

print("Number of communities:", len(results))

print("\n" + "=" * 70)
print("FIRST COMMUNITY STRUCTURE")
print("=" * 70)

first = results[0]

print("Community keys:", list(first.keys()))

for key in [
    "website_record",
    "best_candidate",
    "all_candidate_comparisons",
    "field_issues",
    "review_category",
    "issue_flags",
    "recommended_action",
]:
    print(f"\n--- {key} ---")

    value = first.get(key, "KEY NOT FOUND")

    if key == "all_candidate_comparisons":
        if isinstance(value, list):
            value = value[:1]

    print(json.dumps(value, indent=2)[:4000])

print("\n" + "=" * 70)
print("CATEGORY COUNTS")
print("=" * 70)

from collections import Counter

counts = Counter(
    item.get("review_category")
    for item in results
)

for category, count in sorted(counts.items()):
    print(f"{category}: {count}")

print("\nTOTAL:", sum(counts.values()))

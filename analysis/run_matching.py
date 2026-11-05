import os
import json
from collections import Counter
from pathlib import Path

from matching.matcher import match_all


# --------------------------------------------------
# 1. Define file paths
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"

WEBSITE_FILE = DATA_DIR / "bellhaven_communities.json"
CRM_FILE = Path(
    os.environ.get(
        "BELLHAVEN_CRM_SNAPSHOT",
        str(DATA_DIR / "crm_accounts_20261104_005621.json"),
    )
)

OUTPUT_FILE = PROCESSED_DIR / "matching_results.json"


# --------------------------------------------------
# 2. Load source data
# --------------------------------------------------

def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"Could not find file: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


website_records = load_json(WEBSITE_FILE)
crm_accounts = load_json(CRM_FILE)

print("SOURCE DATA")
print("-" * 50)
print(f"Website communities: {len(website_records)}")
print(f"CRM accounts: {len(crm_accounts)}")


# --------------------------------------------------
# 3. Run matching
# --------------------------------------------------

report = match_all(website_records, crm_accounts)


# --------------------------------------------------
# 4. Save complete matching results
# --------------------------------------------------

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

with OUTPUT_FILE.open("w", encoding="utf-8") as file:
    json.dump(report, file, indent=2, ensure_ascii=False)

print("\nRESULTS SAVED")
print("-" * 50)
print(f"Output: {OUTPUT_FILE}")


# --------------------------------------------------
# 5. Summarize results
# --------------------------------------------------

community_results = report["community_results"]

review_flags = Counter(
    result["review_flag"]
    for result in community_results
)

print("\nMATCHING SUMMARY")
print("-" * 50)
print(f"Website communities: {report['website_count']}")
print(f"CRM accounts: {report['crm_count']}")
print(f"Total comparisons: {report['comparison_count']}")
print(f"Account collisions: {len(report['account_collisions'])}")

print("\nReview flag breakdown:")

for flag, count in review_flags.most_common():
    print(f"  {flag}: {count}")


# --------------------------------------------------
# 6. Display each community's best candidate
# --------------------------------------------------

print("\nCOMMUNITY MATCH RESULTS")
print("-" * 70)

for result in community_results:
    website_name = result.get("website_name", "Unknown")
    best = result.get("best_candidate")

    print(f"\nWebsite: {website_name}")
    print(f"Review flag: {result['review_flag']}")

    if best:
        print(f"CRM candidate: {best['crm_name']}")
        print(f"CRM ID: {best['crm_account_id']}")
        print(f"Score: {best['score']}")
        print(f"Evidence coverage: {best['evidence_coverage']}%")
    else:
        print("CRM candidate: None")


# --------------------------------------------------
# 7. Display account collisions
# --------------------------------------------------

if report["account_collisions"]:
    print("\nACCOUNT COLLISIONS")
    print("-" * 50)

    for collision in report["account_collisions"]:
        print(collision)

else:
    print("\nNo account collisions detected.")
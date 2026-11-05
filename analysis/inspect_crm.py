import json
from pathlib import Path

# --------------------------------------------------
# 1. Locate the project and CRM data file
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CRM_FILE = PROJECT_ROOT / "data" / "crm_accounts_20261104_005621.json"


# --------------------------------------------------
# 2. Load CRM accounts
# --------------------------------------------------

with open(CRM_FILE, "r", encoding="utf-8") as file:
    crm_accounts = json.load(file)


# --------------------------------------------------
# 3. Inspect the data
# --------------------------------------------------

print("=" * 50)
print("CRM DATA INSPECTION")
print("=" * 50)

print(f"Total CRM accounts: {len(crm_accounts)}")

print("\nFields available:")

for field in crm_accounts[0].keys():
    print(f"- {field}")


# --------------------------------------------------
# 4. Check account IDs
# --------------------------------------------------

account_ids = [
    account.get("account_id")
    for account in crm_accounts
]

missing_ids = [
    account for account in crm_accounts
    if not account.get("account_id")
]

duplicate_ids = (
    len(account_ids) - len(set(account_ids))
)

print("\nData validation:")

print(f"Accounts missing IDs: {len(missing_ids)}")
print(f"Duplicate account IDs: {duplicate_ids}")


# --------------------------------------------------
# 5. Inspect parent relationships
# --------------------------------------------------

accounts_with_parent = [
    account for account in crm_accounts
    if account.get("parent_id")
]

accounts_without_parent = [
    account for account in crm_accounts
    if not account.get("parent_id")
]

print("\nHierarchy overview:")

print(f"Accounts with a parent: {len(accounts_with_parent)}")
print(f"Accounts without a parent: {len(accounts_without_parent)}")

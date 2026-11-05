import json
from pathlib import Path
from collections import defaultdict


# --------------------------------------------------
# 1. Load CRM accounts
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CRM_FILE = PROJECT_ROOT / "data" / "crm_accounts_20261104_005621.json"

with open(CRM_FILE, "r", encoding="utf-8") as file:
    crm_accounts = json.load(file)

print(f"Loaded {len(crm_accounts)} CRM accounts.")

# --------------------------------------------------
# 2. Build account index
# the key is 'acccount_id'
# the value is the entire record 
# --------------------------------------------------

accounts_by_id = {
    account["account_id"]: account
    for account in crm_accounts
}

# --------------------------------------------------
# 3. Group child accounts by parent ID
# --------------------------------------------------

children_by_parent = defaultdict(list)

for account in crm_accounts:

    parent_id = account.get("parent_id")

    if parent_id:
        children_by_parent[parent_id].append(account)

# --------------------------------------------------
# 4. Summarize parent organizations
# --------------------------------------------------

print("\n" + "=" * 60)
print("PARENT ORGANIZATION SUMMARY")
print("=" * 60)

for parent_id, children in sorted(
    children_by_parent.items(),
    key=lambda item: item[0]
):

    parent_name = children[0].get("parent_name") or "Unknown"

    print(f"\nParent: {parent_name}")
    print(f"Parent ID: {parent_id}")
    print(f"Number of child accounts: {len(children)}")

# --------------------------------------------------
# 5. Inspect accounts without a parent
# --------------------------------------------------

root_accounts = [
    account for account in crm_accounts
    if not account.get("parent_id")
]

print("\n" + "=" * 60)
print("ACCOUNTS WITHOUT A PARENT")
print("=" * 60)

for account in root_accounts:

    account_id = account["account_id"]
    account_name = account["name"]

    child_count = len(children_by_parent.get(account_id, []))

    print(
        f"{account_name} | "
        f"ID: {account_id} | "
        f"Children: {child_count}"
    )

# --------------------------------------------------
# 6. Find unresolved parent references
# what if an account references a 'parent_id' that DNE?
# --------------------------------------------------

unresolved_parents = []

for account in crm_accounts:

    parent_id = account.get("parent_id")

    if parent_id and parent_id not in accounts_by_id:
        unresolved_parents.append(account)

print("\n" + "=" * 60)
print("UNRESOLVED PARENT REFERENCES")
print("=" * 60)

print(f"Accounts with missing parent records: {len(unresolved_parents)}")

for account in unresolved_parents:
    print(
        account["name"],
        "| Parent:",
        account.get("parent_name"),
        "| Parent ID:",
        account.get("parent_id")
    )
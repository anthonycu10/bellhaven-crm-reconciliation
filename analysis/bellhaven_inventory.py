# have identified the parent ID of Bellhaven == 0015QAPLGS3FVYEEEM

import json
from pathlib import Path


# ==================================================
# 1. CONFIGURATION
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CRM_FILE = PROJECT_ROOT / "data" / "crm_accounts_20261104_005621.json"

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

OUTPUT_FILE = OUTPUT_DIR / "bellhaven_inventory.json"

BELHAVEN_PARENT_ID = "0015QAPLGS3FVYEEEM"


# ==================================================
# 2. LOAD CRM DATA
# ==================================================

with open(CRM_FILE, "r", encoding="utf-8") as file:
    crm_accounts = json.load(file)

print(f"Loaded {len(crm_accounts)} CRM accounts.")


# ==================================================
# 3. BUILD ACCOUNT INDEX
# ==================================================

accounts_by_id = {
    account["account_id"]: account
    for account in crm_accounts
}


# ==================================================
# 4. FIND BELHAVEN PARENT ACCOUNT
# ==================================================

bellhaven_parent = accounts_by_id.get(BELHAVEN_PARENT_ID)

if not bellhaven_parent:
    raise ValueError("Bellhaven parent account was not found.")

print(f"\nBellhaven parent: {bellhaven_parent['name']}")


# ==================================================
# 5. IDENTIFY DIRECT CHILD ACCOUNTS
# ==================================================

# 29 children 
bellhaven_children = [
    account
    for account in crm_accounts
    if account.get("parent_id") == BELHAVEN_PARENT_ID
]

print(f"Direct Bellhaven child accounts: {len(bellhaven_children)}")


# ==================================================
# 6. FIND ALL ACCOUNTS WITH BELLHAVEN IN THEIR NAME
# ==================================================

# eg. Bellhaven Meadows of Findlay
bellhaven_name_candidates = [
    account
    for account in crm_accounts
    if "bellhaven" in account.get("name", "").casefold()
]

print(
    "Accounts with Bellhaven in their name:",
    len(bellhaven_name_candidates)
)


# ==================================================
# 7. IDENTIFY POTENTIAL HIERARCHY ISSUES
# ==================================================

# Bellhaven-named accounts not assigned to Bellhaven's parent.
potential_wrong_parent = [
    account
    for account in bellhaven_name_candidates
    if account["account_id"] != BELHAVEN_PARENT_ID
    and account.get("parent_id") != BELHAVEN_PARENT_ID
    and account.get("parent_id")
]

# Bellhaven-named accounts with no parent.
potential_unassigned = [
    account
    for account in bellhaven_name_candidates
    if account["account_id"] != BELHAVEN_PARENT_ID
    and not account.get("parent_id")
]


# ==================================================
# 8. PRINT INVENTORY
# ==================================================

print("\n" + "=" * 60)
print("BELHAVEN CHILD ACCOUNTS")
print("=" * 60)

for account in bellhaven_children:
    print(
        f"{account['name']} | "
        f"{account['billing_city']}, "
        f"{account['billing_state']} | "
        f"{account['status']} | "
        f"{account['account_id']}"
    )


print("\n" + "=" * 60)
print("BELLHAVEN-NAMED ACCOUNTS UNDER OTHER PARENTS")
print("=" * 60)

for account in potential_wrong_parent:
    print(
        f"{account['name']} | "
        f"Parent: {account.get('parent_name')} | "
        f"Parent ID: {account.get('parent_id')}"
    )


print("\n" + "=" * 60)
print("BELLHAVEN-NAMED ACCOUNTS WITHOUT A PARENT")
print("=" * 60)

for account in potential_unassigned:
    print(
        f"{account['name']} | "
        f"{account['billing_city']}, "
        f"{account['billing_state']} | "
        f"{account['account_id']}"
    )


# ==================================================
# 9. SAVE INVENTORY
# ==================================================

inventory = {
    "bellhaven_parent": bellhaven_parent,
    "direct_children": bellhaven_children,
    "bellhaven_name_candidates": bellhaven_name_candidates,
    "potential_wrong_parent": potential_wrong_parent,
    "potential_unassigned": potential_unassigned,
    "crm_total_accounts": len(crm_accounts)
}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
    json.dump(inventory, file, indent=4, ensure_ascii=False)

print("\n" + "=" * 60)
print("INVENTORY SAVED")
print("=" * 60)

print(f"Output: {OUTPUT_FILE}")

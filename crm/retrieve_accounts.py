import requests
import json
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Retrieve API token
CRM_API_TOKEN = os.getenv("CRM_API_TOKEN")

if not CRM_API_TOKEN:
    raise ValueError("CRM_API_TOKEN was not found.")

from pathlib import Path
from datetime import datetime, timezone

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

BASE_URL = "https://analyst-assessment-production.up.railway.app"

# Replace this with the exact GET path shown in Swagger.
ACCOUNTS_ENDPOINT = "/api/v1/accounts"

CRM_ACCOUNTS_URL = BASE_URL + ACCOUNTS_ENDPOINT

PAGE_SIZE = 100
REQUEST_TIMEOUT = 20
REQUEST_DELAY = 0.3

OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)

# --------------------------------------------------
# API SESSION
# --------------------------------------------------

session = requests.Session()

session.headers.update({
    "Accept": "application/json",
    "Authorization": f"Bearer {CRM_API_TOKEN}"
})

# --------------------------------------------------
# RETRIEVE ONE PAGE
# --------------------------------------------------

def get_accounts_page(page, page_size):

    # Query parameters 
    params = {
        "page": page,
        "page_size": page_size
    }

    response = session.get(
        CRM_ACCOUNTS_URL,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    print("Request URL:", response.url)
    # Raise an error if the API returns 4xx or 5xx.
    response.raise_for_status()

    return response.json()

# --------------------------------------------------
# EXTRACT ACCOUNT RECORDS
# --------------------------------------------------

def extract_accounts(data):

    # Case 1: API returns a list directly.
    if isinstance(data, list):
        return data

    # Case 2: API returns a dictionary.
    if isinstance(data, dict):

        possible_keys = [
            "items",
            "accounts",
            "results",
            "data"
        ]

        for key in possible_keys:

            if key not in data:
                continue

            value = data[key]

            if isinstance(value, list):
                return value

            if isinstance(value, dict):
                return extract_accounts(value)

    raise ValueError(
        "Could not identify the account list in the API response. "
        "Inspect the response JSON and update extract_accounts()."
    )

    # --------------------------------------------------
# RETRIEVE ALL CRM ACCOUNTS
# --------------------------------------------------

def get_all_accounts():

    all_accounts = []

    page = 1

    while True:

        print(f"Retrieving CRM page {page}...")

        # Retrieve one page
        response_data = get_accounts_page(
            page=page,
            page_size=PAGE_SIZE
        )

        # Extract account records
        page_accounts = extract_accounts(response_data)

        print(f"  Retrieved {len(page_accounts)} accounts")

        # Stop if the page is empty
        if not page_accounts:
            break

        all_accounts.extend(page_accounts)

        # Stop when the API returns fewer records than requested.
        if len(page_accounts) < PAGE_SIZE:
            break

        page += 1

        time.sleep(REQUEST_DELAY)

    print("--------------------------------")
    print(f"Total accounts retrieved: {len(all_accounts)}")

    return all_accounts

# --------------------------------------------------
# VALIDATE RETRIEVED ACCOUNTS
# --------------------------------------------------

def validate_accounts(accounts):

    if not accounts:
        raise ValueError("No CRM accounts were retrieved.")

    # Check that every account has an account_id.
    missing_ids = [
        account for account in accounts
        if not account.get("account_id")
    ]

    if missing_ids:
        raise ValueError(
            f"{len(missing_ids)} accounts are missing an account_id."
        )

    # Check for duplicate account IDs.
    account_ids = [
        str(account["account_id"])
        for account in accounts
    ]

    if len(account_ids) != len(set(account_ids)):
        raise ValueError(
            "Duplicate account IDs detected in retrieved data."
        )

    print("CRM data validation passed.")
    print(f"Unique account IDs: {len(account_ids)}")

# --------------------------------------------------
# SAVE CRM SNAPSHOT
# --------------------------------------------------

def save_accounts(accounts):

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S"
    )

    output_file = OUTPUT_DIR / (
        f"crm_accounts_{timestamp}.json"
    )

    with open(output_file, "w", encoding="utf-8") as file:

        json.dump(
            accounts,
            file,
            indent=4,
            ensure_ascii=False
        )

    print(f"Saved CRM snapshot: {output_file}")

    return output_file

# --------------------------------------------------
# MAIN EXECUTION
# --------------------------------------------------

def main():

    print("Starting Bellhaven CRM data retrieval...")
    print("--------------------------------")

    try:

        # 1. Retrieve all accounts
        accounts = get_all_accounts()

        # print("\n--- FIRST CRM ACCOUNT ---")
        # print(json.dumps(accounts[0], indent=4))

        # print("\n--- AVAILABLE FIELDS ---")
        # print(accounts[0].keys())

        # print("\n--- SECOND CRM ACCOUNT ---")
        # print(json.dumps(accounts[1], indent=4))

        # 2. Validate the retrieved data
        validate_accounts(accounts)

        # 3. Save the raw snapshot
        save_accounts(accounts)

        print("--------------------------------")
        print("CRM retrieval completed successfully.")

    except requests.exceptions.RequestException as error:

        print("API request failed:")
        print(error)

        raise

    except Exception as error:

        print("CRM retrieval failed:")
        print(error)

        raise


if __name__ == "__main__":
    main()
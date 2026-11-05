
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = (
    "https://analyst-assessment-production.up.railway.app/api/v1"
)

ACCOUNT_ID = "001L3LGR6W69J8DYYV"

# Uses the token already stored in your .env.
# Adjust the environment variable name if necessary.
TOKEN = os.getenv("CRM_API_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "CRM_API_TOKEN is missing from .env. "
        "Use your existing token variable name."
    )

response = requests.get(
    f"{BASE_URL}/accounts/{ACCOUNT_ID}",
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json",
    },
    timeout=20,
)

print("HTTP STATUS:", response.status_code)

response.raise_for_status()

account = response.json()

print("\nACCOUNT RESPONSE:")
print(json.dumps(account, indent=2))

print("\nTOP-LEVEL KEYS:")
print(list(account.keys()))


import os

import requests
from dotenv import load_dotenv


load_dotenv()

BASE_URL = (
    "https://analyst-assessment-production.up.railway.app/api/v1"
)


class CRMClient:
    def __init__(self):
        token = os.getenv("CRM_API_TOKEN")

        if not token:
            raise RuntimeError(
                "CRM_API_TOKEN is missing from .env"
            )

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })

    def get_account(self, account_id):
        response = self.session.get(
            f"{BASE_URL}/accounts/{account_id}",
            timeout=20,
        )
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise ValueError(
                "Unexpected CRM account response."
            )

        if data.get("account_id") != account_id:
            raise ValueError(
                "CRM returned a different account ID."
            )

        return data
    
    def patch_account(self, account_id, changes):
        """
        Send a single-field CRM PATCH.

        Caller must enforce human approval and verify the
        updated value with a fresh GET after this request.
        """
        if not isinstance(changes, dict) or len(changes) != 1:
            raise ValueError(
                "PATCH requires exactly one field change."
            )

        allowed_fields = {
            "phone",
            "billing_street",
            "billing_city",
            "billing_state",
            "billing_zip",
        }

        field, value = next(iter(changes.items()))

        if field not in allowed_fields:
            raise ValueError(
                f"Field {field} is not allowed for PATCH."
            )

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "PATCH value must be a nonempty string."
            )

        response = self.session.patch(
            f"{BASE_URL}/accounts/{account_id}",
            json=changes,
            timeout=20,
        )

        response.raise_for_status()

        # A successful PATCH may legitimately return no body.
        if not response.content:
            return {
                "status_code": response.status_code,
                "message": "PATCH accepted; verification required",
            }

        try:
            return response.json()
        except ValueError:
            return {
                "status_code": response.status_code,
                "message": "Non-JSON response; verification required",
            }

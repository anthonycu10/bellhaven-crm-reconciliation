
from crm.client import CRMClient
from crm.executor import evaluate_item
from review.db import get_connection


with get_connection() as conn:
    row = conn.execute(
        """
        SELECT *
        FROM review_items
        WHERE website_name = 'Bellhaven of Goshen'
          AND issue_type = 'field_update_review'
        LIMIT 1
        """
    ).fetchone()

if row is None:
    raise RuntimeError("Goshen review item not found.")

item = dict(row)

print("Testing read-only validation for:", item["website_name"])
print("Stored decision status:", item["status"])

result = evaluate_item(item, CRMClient())

print("\nDRY-RUN RESULT")
for key, value in result.items():
    print(f"{key}: {value}")

print("\nNo CRM writes were performed.")

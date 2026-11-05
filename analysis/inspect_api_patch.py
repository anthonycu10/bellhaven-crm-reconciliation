
import json
import requests

BASE_URL = (
    "https://analyst-assessment-production.up.railway.app"
)

response = requests.get(
    f"{BASE_URL}/api/openapi.json",
    timeout=20,
)
response.raise_for_status()

schema = response.json()

path = "/api/v1/accounts/{account_id}"
patch = schema["paths"][path]["patch"]

print("=" * 70)
print("PATCH ENDPOINT")
print("=" * 70)

print(json.dumps(patch, indent=2))

print("\n" + "=" * 70)
print("COMPONENT SCHEMAS")
print("=" * 70)

for name, component in schema.get(
    "components", {}
).get("schemas", {}).items():

    if any(
        term in name.lower()
        for term in ("account", "update", "patch")
    ):
        print(f"\nSCHEMA: {name}")
        print(json.dumps(component, indent=2))

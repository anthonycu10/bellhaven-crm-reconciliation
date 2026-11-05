# using this file, we can check that the structures of both files are what we need to input into the matcher function 
# Bellhaven Communities: 34 community records
# CRM: 121 accoutns recrods 
# use both .json files in both sources

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

FILES_TO_INSPECT = [
    "bellhaven_communities.json",
    "crm_accounts_20261104_005621.json",
]


def inspect_file(filename):
    path = DATA_DIR / filename

    print("\n" + "=" * 60)
    print(f"FILE: {filename}")
    print("=" * 60)

    if not path.exists():
        print("File not found.")
        return

    # Load the file based on its extension.
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))

    elif path.suffix == ".csv":
        import pandas as pd
        data = pd.read_csv(path, dtype=str).to_dict(orient="records")

    else:
        print(f"Unsupported file extension: {path.suffix}")
        return

    print(f"Data type: {type(data).__name__}")

    if isinstance(data, list):
        print(f"Record count: {len(data)}")

        if data:
            print(f"First record keys: {list(data[0].keys())}")
            print("\nFirst record preview:")

            # Print a limited preview rather than the entire record.
            for key, value in data[0].items():
                print(f"  {key}: {value}")

    elif isinstance(data, dict):
        print(f"Top-level keys: {list(data.keys())}")

        for key, value in data.items():
            if isinstance(value, list):
                print(f"  {key}: {len(value)} records")


for filename in FILES_TO_INSPECT:
    inspect_file(filename)
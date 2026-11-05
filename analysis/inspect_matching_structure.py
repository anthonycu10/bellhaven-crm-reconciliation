
import json
from pathlib import Path


# Locate the project directory relative to this script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

MATCHING_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "matching_results.json"
)


def summarize(value, depth=0):
    """
    Print the structure of a value without dumping
    the entire matching results file.
    """

    if isinstance(value, dict):
        summary = {}

        for key, item in value.items():
            if depth >= 2:
                if isinstance(item, dict):
                    summary[key] = {
                        "type": "dict",
                        "keys": list(item.keys())
                    }
                elif isinstance(item, list):
                    summary[key] = {
                        "type": "list",
                        "length": len(item)
                    }
                else:
                    summary[key] = item
            else:
                summary[key] = summarize(item, depth + 1)

        return summary

    elif isinstance(value, list):
        result = {
            "type": "list",
            "length": len(value)
        }

        if value:
            result["first_item"] = summarize(
                value[0],
                depth + 1
            )

        return result

    else:
        return value


def main():

    if not MATCHING_FILE.exists():
        raise FileNotFoundError(
            f"Could not find: {MATCHING_FILE}"
        )

    with MATCHING_FILE.open("r", encoding="utf-8") as file:
        results = json.load(file)

    print("\n========== TOP-LEVEL STRUCTURE ==========")

    print(json.dumps(
        summarize(results),
        indent=2
    ))

    print("\n========== FIRST COMMUNITY RESULT ==========")

    communities = results.get("community_results", [])

    if communities:
        first = communities[0]

        print(json.dumps(
            summarize(first),
            indent=2
        ))
    else:
        print("No community_results found.")

    print("\n========== COUNTS ==========")

    print("Website locations:", results.get("website_count"))
    print("CRM accounts:", results.get("crm_count"))
    print("Comparisons:", results.get("comparison_count"))
    print("Account collisions:", len(
        results.get("account_collisions", [])
    ))


if __name__ == "__main__":
    main()

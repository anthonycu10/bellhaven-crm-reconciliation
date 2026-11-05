
import json
import os
import subprocess
import sys
from pathlib import Path

from crm.retrieve_accounts import (
    get_all_accounts,
    save_accounts,
    validate_accounts,
)
from scraper.config import EXPECTED_COMMUNITY_COUNT
from scraper.detail import scrape_detail_page
from scraper.directory import scrape_directory
from scraper.config import REQUEST_DELAY

import time


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"


def run_module(module, env):
    print(f"\n{'=' * 60}", flush=True)
    print(f"RUNNING: {module}", flush=True)
    print(f"{'=' * 60}", flush=True)

    subprocess.run(
        [sys.executable, "-m", module],
        cwd=ROOT,
        env=env,
        check=True,
    )


def write_json_atomic(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temporary.open("w", encoding="utf-8") as f:
        json.dump(
            records,
            f,
            indent=2,
            ensure_ascii=False,
        )

    temporary.replace(path)


def refresh_website():
    print("\nSTAGE 1: WEBSITE SCRAPING", flush=True)

    directory = scrape_directory()

    if len(directory) != EXPECTED_COMMUNITY_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_COMMUNITY_COUNT} "
            f"locations, found {len(directory)}."
        )

    records = []

    for index, community in enumerate(
        directory, start=1
    ):
        print(
            f"[{index}/{len(directory)}] "
            f"{community['name']}",
            flush=True,
        )

        details = scrape_detail_page(
            community["detail_url"]
        )

        record = {**community, **details}

        required = (
            "street_address",
            "zip_code",
            "detail_city",
            "detail_state",
        )

        missing = [
            field
            for field in required
            if not record.get(field)
        ]

        if missing:
            raise RuntimeError(
                f"Incomplete website record: "
                f"{community['name']}; missing {missing}"
            )

        records.append(record)
        time.sleep(REQUEST_DELAY)

    urls = [record["detail_url"] for record in records]

    if len(urls) != len(set(urls)):
        raise RuntimeError(
            "Duplicate website detail URLs detected."
        )

    write_json_atomic(
        DATA_DIR / "bellhaven_communities.json",
        records,
    )

    print(
        f"Website snapshot saved: {len(records)} locations",
        flush=True,
    )


def refresh_crm():
    print("\nSTAGE 2: CRM EXTRACTION", flush=True)

    accounts = get_all_accounts()
    validate_accounts(accounts)

    path = save_accounts(accounts)

    print(f"CRM snapshot saved: {path}", flush=True)

    return Path(path).resolve()


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # No CRM writes are performed by this pipeline.
    refresh_website()

    crm_path = refresh_crm()

    env = os.environ.copy()
    env["BELLHAVEN_CRM_SNAPSHOT"] = str(crm_path)

    run_module("analysis.run_matching", env)
    run_module("analysis.run_classification", env)
    run_module("analysis.find_crm_only", env)
    run_module("review.queue", env)

    print("\n" + "=" * 60)
    print("DAILY RECONCILIATION COMPLETE")
    print("No CRM writes performed.")
    print("=" * 60)


if __name__ == "__main__":
    main()

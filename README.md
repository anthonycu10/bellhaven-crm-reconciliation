
# Bellhaven CRM Reconciliation

## Overview

A Python-based reconciliation workflow that compares Bellhaven's
public community directory against CRM account records, identifies
data discrepancies, and provides a human-reviewed process for
approving CRM corrections.

## Features

- Scrapes community names, addresses, and care offerings
- Retrieves CRM accounts through the authenticated API
- Uses normalized addresses and weighted fuzzy matching
- Identifies field discrepancies, ambiguous matches, parent
  hierarchy issues, website-only locations, and CRM-only accounts
- Provides a Streamlit dashboard for reviewing evidence
- Records reviewer decisions in SQLite
- Supports explicitly approved, single-field CRM updates
- Rechecks live CRM values before applying corrections
- Logs write attempts and verifies updates after PATCH
- Supports repeatable daily reconciliation runs

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install requests python-dotenv rapidfuzz streamlit pandas
```

Create a `.env` file:

```env
CRM_API_TOKEN=your_token_here
ENABLE_CRM_WRITES=false
```

Never commit the actual API token.

## Running the reconciliation

```bash
python main.py
```

This refreshes the website and CRM snapshots, performs matching
and classification, identifies CRM-only records, and synchronizes
the review queue.

The daily pipeline does not modify CRM records.

## Reviewing discrepancies

```bash
streamlit run app.py
```

The dashboard displays proposed discrepancies, supporting evidence,
CRM candidates, and current versus proposed field values.

Reviewers can approve or reject items and provide decision notes.

The sidebar contains a separate "Apply Approved Changes" page.

## Applying approved changes

Only approved field corrections are eligible for execution.
Investigation-only items cannot be written automatically.

The executor checks:

1. An explicit human approval exists.
2. The proposed field is permitted.
3. The current CRM value still matches the reviewed value.
4. The update is explicitly requested.
5. The updated CRM value can be verified afterward.

Dry run:

```bash
python -m crm.write_executor --item-id 4
```

Live execution requires both an explicit execution action and
ENABLE_CRM_WRITES=true.

Live PATCH behavior has not been verified end-to-end against the
assessment API. No production changes were made during testing.

## Matching approach

Records are compared using normalized names, addresses, ZIP codes,
cities, and states.

Weighted scoring prioritizes street address and ZIP code.
Conservative identity checks prevent uncertain matches from
becoming automatic CRM updates.

Ambiguous matches, potential parent discrepancies, care-type
differences, and missing accounts are routed for human investigation.

## Daily scheduling

A sample cron configuration is provided in:

`scheduler/cron.example`

The job can run daily without human intervention. CRM modifications
remain separate from the scheduled reconciliation.

## Safety

Review proposals use stable issue identifiers and source hashes.

Repeated runs with unchanged inputs preserve existing reviewer
decisions instead of creating duplicate proposals.

Changed evidence can require renewed human review.

CRM updates are never triggered automatically by the daily pipeline.

## Validation

The pipeline was tested with:

- 34 website communities
- 121 CRM accounts
- 4,114 matching comparisons
- 44 review items
- 0 new review proposals on an unchanged rerun

Streamlit approval controls and dry-run validation were tested.

## Known limitations

- Live CRM PATCH behavior remains unverified.
- Ambiguous entity matches require human investigation.
- Care-type discrepancies are review-only.
- Website and CRM data quality affect matching confidence.
- The sample cron schedule must be configured on the host machine.
```

from collections import defaultdict

from matching.scoring import score_pair


# ---------------------------------------------------------
# 1. Matching configuration
# ---------------------------------------------------------

TOP_CANDIDATES_TO_KEEP = 5

# If the top two viable candidates are within this many
# points, flag the result for additional review.
AMBIGUOUS_SCORE_GAP = 5

# Used to count candidates worth reviewing.
MIN_REVIEW_SCORE = 65


# ---------------------------------------------------------
# 2. Validate input datasets
# ---------------------------------------------------------

def validate_inputs(website_records, crm_accounts):
    """
    Validate the two input datasets before matching.

    We require:
        - Non-empty website records
        - Non-empty CRM accounts
        - A name on each website record
        - A unique account_id on every CRM record
    """

    if not website_records:
        raise ValueError("No website communities were supplied.")

    if not crm_accounts:
        raise ValueError("No CRM accounts were supplied.")

    missing_website_names = [
        index
        for index, record in enumerate(website_records)
        if not record.get("name")
    ]

    if missing_website_names:
        raise ValueError(
            "Website records are missing names at indexes: "
            f"{missing_website_names}"
        )

    missing_account_ids = [
        index
        for index, account in enumerate(crm_accounts)
        if not account.get("account_id")
    ]

    if missing_account_ids:
        raise ValueError(
            "CRM records are missing account IDs at indexes: "
            f"{missing_account_ids}"
        )

    account_ids = [
        str(account["account_id"])
        for account in crm_accounts
    ]

    if len(account_ids) != len(set(account_ids)):
        raise ValueError("Duplicate CRM account IDs detected.")

    print("Input validation passed.")
    print(f"Website communities: {len(website_records)}")
    print(f"CRM accounts: {len(crm_accounts)}")


# ---------------------------------------------------------
# 3. Create a compact candidate summary
# ---------------------------------------------------------

def summarize_candidate(result):
    """
    Extract the most useful candidate information.

    The full field-level comparison remains available
    in the original score_pair result.
    """

    return {
        "crm_account_id": result["crm_account_id"],
        "crm_name": result["crm_name"],
        "score": result["score"],
        "evidence_coverage": result["evidence_coverage"],
        "classification": result["classification"],
        "location_conflicts": result["location_conflicts"],
        "supporting_evidence": result["supporting_evidence"],
    }


# ---------------------------------------------------------
# 4. Rank candidates for one website community
# ---------------------------------------------------------

def rank_candidates_for_community(
    website_record,
    crm_accounts,
):
    """
    Compare one website community against every CRM account.

    Returns:
        - Best candidate
        - Second-best candidate
        - Score gap
        - Top five candidates
        - All candidate comparisons
        - Review flags
    """

    all_results = []

    # Compare this website community with every CRM account.
    for crm_account in crm_accounts:

        result = score_pair(
            website_record=website_record,
            crm_record=crm_account,
        )

        all_results.append(result)

    # Sort by:
    # 1. Highest score
    # 2. Highest evidence coverage
    #
    # We do not use account ID or name as a meaningful
    # tie-breaker. If candidates remain tied, that is
    # something the reviewer should see.
    all_results.sort(
        key=lambda result: (
            -result["score"],
            -result["evidence_coverage"],
        )
    )

    # Get the first and second candidates.
    best_result = (
        all_results[0]
        if all_results
        else None
    )

    second_result = (
        all_results[1]
        if len(all_results) > 1
        else None
    )

    best_candidate = (
        summarize_candidate(best_result)
        if best_result
        else None
    )

    second_best_candidate = (
        summarize_candidate(second_result)
        if second_result
        else None
    )

    # Calculate the difference between the two best scores.
    if best_result and second_result:
        score_gap = round(
            best_result["score"] - second_result["score"],
            2,
        )
    else:
        score_gap = None

    # Count candidates whose score is at least 65.
    review_candidate_count = sum(
        result["score"] >= MIN_REVIEW_SCORE
        for result in all_results
    )

    # Keep the five highest-ranked candidates for review.
    top_candidates = [
        summarize_candidate(result)
        for result in all_results[:TOP_CANDIDATES_TO_KEEP]
    ]

    # -----------------------------------------------------
    # Determine the review flag.
    # -----------------------------------------------------

    if best_result is None:
        review_flag = "no_candidate"

    elif best_result["classification"] == "location_conflict":
        review_flag = "location_conflict"

    elif best_result["classification"] == "weak_candidate":
        review_flag = "no_confident_candidate"

    elif (
        second_result is not None
        and second_result["classification"]
        in {"strong_candidate", "possible_candidate"}
        and score_gap <= AMBIGUOUS_SCORE_GAP
    ):
        review_flag = "ambiguous_top_candidates"

    else:
        review_flag = best_result["classification"]

    # Preserve all comparisons for deeper investigation.
    return {
        "website_name": website_record.get("name"),
        "website_detail_url": website_record.get("detail_url"),
        "best_candidate": best_candidate,
        "second_best_candidate": second_best_candidate,
        "score_gap": score_gap,
        "review_candidate_count": review_candidate_count,
        "review_flag": review_flag,
        "top_candidates": top_candidates,
        "all_candidate_comparisons": all_results,
    }


# ---------------------------------------------------------
# 5. Identify CRM account collisions
# ---------------------------------------------------------

def find_account_collisions(community_results):
    """
    Identify cases where multiple website communities
    have the same strong or possible best CRM candidate.

    This does not resolve the collision. It flags it.
    """

    account_to_communities = defaultdict(list)

    for result in community_results:

        best = result["best_candidate"]

        if not best:
            continue

        if best["classification"] not in {
            "strong_candidate",
            "possible_candidate",
        }:
            continue

        account_id = best["crm_account_id"]

        account_to_communities[account_id].append({
            "website_name": result["website_name"],
            "score": best["score"],
            "classification": best["classification"],
        })

    collisions = []

    for account_id, communities in account_to_communities.items():

        if len(communities) > 1:
            collisions.append({
                "crm_account_id": account_id,
                "website_communities": communities,
                "reason": (
                    "Multiple website communities selected "
                    "the same best CRM account."
                ),
            })

    return collisions


# ---------------------------------------------------------
# 6. Match the complete website dataset against the CRM
# ---------------------------------------------------------

def match_all(website_records, crm_accounts):
    """
    Run all website-to-CRM comparisons.

    For each website community:
        - Compare against all CRM accounts
        - Rank the candidates
        - Record the best candidate
        - Record ambiguous matches

    Then:
        - Detect CRM account collisions
        - Return a complete matching report
    """

    validate_inputs(
        website_records,
        crm_accounts,
    )

    community_results = []

    total_comparisons = (
        len(website_records) * len(crm_accounts)
    )

    print("\nStarting matching process...")
    print(f"Total comparisons: {total_comparisons}")

    for index, website_record in enumerate(
        website_records,
        start=1,
    ):

        print(
            f"[{index}/{len(website_records)}] "
            f"Matching: {website_record['name']}"
        )

        result = rank_candidates_for_community(
            website_record=website_record,
            crm_accounts=crm_accounts,
        )

        community_results.append(result)

    # Check whether multiple communities selected
    # the same CRM account as their best candidate.
    account_collisions = find_account_collisions(
        community_results
    )

    report = {
        "website_count": len(website_records),
        "crm_count": len(crm_accounts),
        "comparison_count": total_comparisons,
        "community_results": community_results,
        "account_collisions": account_collisions,
    }

    print("\nMatching completed.")
    print(f"Comparisons completed: {total_comparisons}")
    print(f"Account collisions: {len(account_collisions)}")

    return report


# ---------------------------------------------------------
# 7. Run example tests
# ---------------------------------------------------------

if __name__ == "__main__":

    print("Testing complete matcher...\n")

    # Website records
    website_maplewood = {
        "name": "Bellhaven of Maplewood",
        "detail_url": "/communities/bellhaven-of-maplewood",
        "street_address": "210 Orchard Lane",
        "detail_city": "Maplewood",
        "detail_state": "OH",
        "zip_code": "44280",
        "phone": "(614) 250-9447",
        "detail_care_offerings": ["Assisted Living"],
    }

    website_owosso = {
        "name": "Bellhaven of Owosso",
        "detail_url": "/communities/bellhaven-of-owosso",
        "street_address": "1120 W Main St",
        "detail_city": "Owosso",
        "detail_state": "MI",
        "zip_code": "48867",
        "phone": "(734) 503-1363",
        "detail_care_offerings": ["Assisted Living"],
    }

    # CRM accounts
    crm_maplewood = {
        "account_id": "TEST-MAPLEWOOD",
        "name": "Bellhaven of Maplewood",
        "billing_street": "210 Orchard Ln",
        "billing_city": "Maplewood",
        "billing_state": "OH",
        "billing_zip": "44280",
        "phone": "(614) 250-9447",
        "care_type": "Assisted Living",
    }

    crm_owosso_1 = {
        "account_id": "TEST-OWOSSO-1",
        "name": "Bellhaven of Owosso",
        "billing_street": "1120 W Main St",
        "billing_city": "Owosso",
        "billing_state": "MI",
        "billing_zip": "48867",
        "phone": "(734) 503-1363",
        "care_type": "Assisted Living",
    }

    crm_owosso_2 = {
        "account_id": "TEST-OWOSSO-2",
        "name": "Bellhaven of Owosso",
        "billing_street": "1120 West Main Street",
        "billing_city": "Owosso",
        "billing_state": "MI",
        "billing_zip": "48867",
        "phone": "(330) 383-5991",
        "care_type": "Assisted Living",
    }

    website_records = [
        website_maplewood,
        website_owosso,
    ]

    crm_accounts = [
        crm_maplewood,
        crm_owosso_1,
        crm_owosso_2,
    ]

    # Run all six possible comparisons.
    test_report = match_all(
        website_records=website_records,
        crm_accounts=crm_accounts,
    )

    # -----------------------------------------------------
    # Test 1: Comparison count
    # -----------------------------------------------------

    assert test_report["comparison_count"] == 6

    # -----------------------------------------------------
    # Test 2: Maplewood has one clear candidate
    # -----------------------------------------------------

    maplewood_match = test_report["community_results"][0]

    print("\nMAPLEWOOD MATCH")
    print("Best candidate:", maplewood_match["best_candidate"])
    print("Score gap:", maplewood_match["score_gap"])
    print("Review flag:", maplewood_match["review_flag"])

    assert (
        maplewood_match["best_candidate"]["crm_account_id"]
        == "TEST-MAPLEWOOD"
    )

    assert maplewood_match["review_flag"] == "strong_candidate"

    # -----------------------------------------------------
    # Test 3: Owosso has two equally strong candidates
    # -----------------------------------------------------

    owosso_match = test_report["community_results"][1]

    print("\nOWOSSO MATCH")
    print("Best candidate:", owosso_match["best_candidate"])
    print("Second candidate:", owosso_match["second_best_candidate"])
    print("Score gap:", owosso_match["score_gap"])
    print("Review flag:", owosso_match["review_flag"])

    assert owosso_match["score_gap"] == 0

    assert (
        owosso_match["review_flag"]
        == "ambiguous_top_candidates"
    )

    # -----------------------------------------------------
    # Test 4: Account collision detection
    # -----------------------------------------------------

    collision_test_results = [
        {
            "website_name": "Community A",
            "best_candidate": {
                "crm_account_id": "TEST-SHARED",
                "score": 100,
                "classification": "strong_candidate",
            },
        },
        {
            "website_name": "Community B",
            "best_candidate": {
                "crm_account_id": "TEST-SHARED",
                "score": 95,
                "classification": "strong_candidate",
            },
        },
    ]

    collisions = find_account_collisions(
        collision_test_results
    )

    print("\nCOLLISION TEST")
    print(collisions)

    assert len(collisions) == 1
    assert collisions[0]["crm_account_id"] == "TEST-SHARED"

    print("\nAll matcher tests passed.")

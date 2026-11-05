
"""
Business-level classification of website-to-CRM matching results.

This module does not modify source data or write to the CRM.
It adds review categories and explanations to existing match results.
"""

EXPECTED_PARENT_ID = "0015QAPLGS3FVYEEEM"

MIN_CREDIBLE_SCORE = 65
MIN_IDENTITY_SCORE = 80
MIN_EXACT_LOCATION_SIMILARITY = 95
MIN_NAME_SIMILARITY = 85
AMBIGUOUS_SCORE_GAP = 5


def get_candidate_comparison(result, account_id):
    """Return the detailed field comparisons for a CRM candidate."""

    for comparison in result.get("all_candidate_comparisons", []):
        if comparison.get("crm_account_id") == account_id:
            return comparison

    return {}


def get_field_status(comparison, field_name):
    """Find the comparison status for one field."""

    for field in comparison.get("field_comparisons", []):
        if field.get("field") == field_name:
            return field.get("status")

    return "unavailable"


def get_field_similarity(comparison, field_name):
    """Find the similarity score for one field."""

    for field in comparison.get("field_comparisons", []):
        if field.get("field") == field_name:
            return field.get("similarity", 0)

    return 0


def is_ambiguous(result):
    """Identify cases where multiple CRM candidates compete."""

    if result.get("review_flag") == "ambiguous_top_candidates":
        return True

    if result.get("score_gap") is not None:
        if result["score_gap"] <= AMBIGUOUS_SCORE_GAP:
            return True

    # More than one credible candidate is a reason for review,
    # especially when the leading candidates have similar evidence.
    if result.get("review_candidate_count", 0) > 1:
        return True

    return False



def has_established_identity(result, comparison):
    """
    Establish identity only when both the facility name and
    physical location provide sufficiently strong evidence.

    A matching address with a substantially different name
    requires human identity review.
    """

    name_similarity = get_field_similarity(comparison, "name")
    street_similarity = get_field_similarity(comparison, "street")

    city_status = get_field_status(comparison, "city")
    state_status = get_field_status(comparison, "state")
    zip_status = get_field_status(comparison, "zip")

    name_and_address_match = (
        name_similarity >= MIN_NAME_SIMILARITY
        and street_similarity >= MIN_EXACT_LOCATION_SIMILARITY
        and city_status == "exact_match"
        and state_status == "exact_match"
    )

    # A different facility name at the same physical address
    # is a possible rename or ownership change, not proof
    # that the CRM account represents the website community.
    location_and_name_match = (
        name_similarity >= MIN_NAME_SIMILARITY
        and street_similarity >= MIN_EXACT_LOCATION_SIMILARITY
        and zip_status == "exact_match"
        and city_status == "exact_match"
        and state_status == "exact_match"
        and result.get("best_candidate", {}).get("score", 0)
            >= MIN_IDENTITY_SCORE
    )

    return name_and_address_match or location_and_name_match


def identify_field_issues(comparison, candidate):
    """Collect fields that differ or need human attention."""

    issues = []

    for field in comparison.get("field_comparisons", []):
        if field.get("status") not in ("exact_match", "close_match"):
            issues.append(field.get("field"))

    supporting = candidate.get("supporting_evidence", {})

    for field_name, evidence in supporting.items():
        if evidence.get("status") != "exact_match":
            issues.append(field_name)

    return sorted(set(issues))


def classify_community(result, crm_by_id):
    """
    Add a business-level category to one website community result.

    Returns a new dictionary. Does not modify the original result.
    """

    output = dict(result)

    candidate = result.get("best_candidate")

    output["review_category"] = None
    output["issue_flags"] = []
    output["recommended_action"] = None
    output["field_issues"] = []
    output["identity_established"] = False

    # No credible CRM candidate.
    if (
        not candidate
        or candidate.get("score", 0) < MIN_CREDIBLE_SCORE
    ):
        output["review_category"] = "website_only"
        output["issue_flags"].append("no_credible_crm_match")
        output["recommended_action"] = (
            "Review whether a new CRM account should be created."
        )
        return output

    account_id = candidate.get("crm_account_id")
    crm_record = crm_by_id.get(account_id, {})

    comparison = get_candidate_comparison(result, account_id)

    # Ambiguity takes priority over selecting an individual account.
    if is_ambiguous(result):
        output["review_category"] = "ambiguous_match"
        output["issue_flags"].append("multiple_or_close_candidates")
        output["recommended_action"] = (
            "Compare competing CRM accounts and select the correct record."
        )
        return output

    identity_established = has_established_identity(
        result,
        comparison
    )

    output["identity_established"] = identity_established

    if not identity_established:
        output["review_category"] = "ambiguous_match"
        output["issue_flags"].append("identity_not_established")
        output["recommended_action"] = (
            "Review the candidate evidence before linking records."
        )
        return output

    # Collect field discrepancies after identity is established.
    field_issues = identify_field_issues(comparison, candidate)
    output["field_issues"] = field_issues

    # Parent ownership is checked separately from community identity.
    actual_parent_id = crm_record.get("parent_id") or ""

    if actual_parent_id != EXPECTED_PARENT_ID:
        output["review_category"] = "potential_wrong_parent"
        output["issue_flags"].append("parent_mismatch")

        if field_issues:
            output["issue_flags"].append("crm_field_discrepancies")

        output["recommended_action"] = (
            "Verify the parent organization before changing CRM hierarchy."
        )
        return output

    # A known identity with field discrepancies needs correction/review.
    if field_issues:
        output["review_category"] = "match_needs_update"
        output["issue_flags"].append("crm_field_discrepancies")
        output["recommended_action"] = (
            "Review the differing CRM fields against the website evidence."
        )
        return output

    # Only clean, established matches receive this category.
    output["review_category"] = "confirmed_match"
    output["recommended_action"] = (
        "No change recommended; retain the existing CRM record."
    )

    return output


def classify_all(matching_results, crm_records):
    """Classify all website community results."""

    crm_by_id = {
        record["account_id"]: record
        for record in crm_records
    }

    classified = []

    for result in matching_results.get("community_results", []):
        classified.append(
            classify_community(result, crm_by_id)
        )

    return {
        "website_count": matching_results.get("website_count", 0),
        "crm_count": matching_results.get("crm_count", 0),
        "community_results": classified,
    }
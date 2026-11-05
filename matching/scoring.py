
from rapidfuzz import fuzz

from matching.normalize import (
    normalize_website_record,
    normalize_crm_record,
)


# ---------------------------------------------------------
# 1. Scoring configuration
# ---------------------------------------------------------

FIELD_WEIGHTS = {
    "name": 25,
    "street": 35,
    "zip": 20,
    "city": 10,
    "state": 10,
}

# These thresholds are initial heuristics.
# We will calibrate them after examining actual matches.
STRONG_CANDIDATE_THRESHOLD = 85
POSSIBLE_CANDIDATE_THRESHOLD = 65

MIN_STRONG_COVERAGE = 80
MIN_POSSIBLE_COVERAGE = 60


# ---------------------------------------------------------
# 2. Compare two text values using fuzzy similarity
# ---------------------------------------------------------

def fuzzy_similarity(value_1, value_2):
    """
    Return a similarity score from 0 to 100.

    Missing values are not considered a match.
    """

    if not value_1 or not value_2:
        return 0

    return round(fuzz.ratio(value_1, value_2), 2)


# ---------------------------------------------------------
# 3. Compare two values exactly
# ---------------------------------------------------------

def exact_similarity(value_1, value_2):
    """
    Return 100 for an exact match and 0 otherwise.

    Missing values receive 0.
    """

    if not value_1 or not value_2:
        return 0

    return 100 if value_1 == value_2 else 0


# ---------------------------------------------------------
# 4. Compare a single field
# ---------------------------------------------------------

def compare_field(
    field_name,
    website_value,
    crm_value,
    weight,
    comparison_method,
):
    """
    Compare one normalized website field with one
    normalized CRM field.

    Returns a dictionary containing the source values,
    similarity, weighted points, and comparison status.
    """

    # A field is available only if both sources have values.
    available = bool(website_value and crm_value)

    if not available:
        similarity = 0
        status = "missing_data"

    elif comparison_method == "fuzzy":
        similarity = fuzzy_similarity(
            website_value,
            crm_value,
        )

        if similarity == 100:
            status = "exact_match"
        elif similarity >= 85:
            status = "close_match"
        else:
            status = "mismatch"

    elif comparison_method == "exact":
        similarity = exact_similarity(
            website_value,
            crm_value,
        )

        status = (
            "exact_match"
            if similarity == 100
            else "mismatch"
        )

    else:
        raise ValueError(
            f"Unknown comparison method: {comparison_method}"
        )

    weighted_points = round(
        weight * similarity / 100,
        2,
    )

    return {
        "field": field_name,
        "website_value": website_value,
        "crm_value": crm_value,
        "available": available,
        "similarity": similarity,
        "weight": weight,
        "weighted_points": weighted_points,
        "status": status,
    }


# ---------------------------------------------------------
# 5. Compare supporting evidence
# ---------------------------------------------------------

def compare_supporting_evidence(
    website_normalized,
    crm_normalized,
):
    """
    Compare phone and care types separately.

    These fields are supporting evidence only.
    They do not contribute to the core score.

    Website care offerings may contain multiple values,
    while the CRM may store only one.
    """

    website_phone = website_normalized["phone_norm"]
    crm_phone = crm_normalized["phone_norm"]

    if not website_phone or not crm_phone:
        phone_status = "missing_data"
    elif website_phone == crm_phone:
        phone_status = "exact_match"
    else:
        phone_status = "mismatch"

    website_care = set(
        website_normalized["care_types_norm"]
    )
    crm_care = set(
        crm_normalized["care_types_norm"]
    )

    if not website_care or not crm_care:
        care_status = "missing_data"
    elif website_care == crm_care:
        care_status = "exact_match"
    elif website_care.intersection(crm_care):
        care_status = "partial_match"
    else:
        care_status = "mismatch"

    return {
        "phone": {
            "website_value": website_phone,
            "crm_value": crm_phone,
            "status": phone_status,
        },
        "care_type": {
            "website_value": sorted(website_care),
            "crm_value": sorted(crm_care),
            "status": care_status,
        },
    }


# ---------------------------------------------------------
# 6. Detect hard location conflicts
# ---------------------------------------------------------

def detect_location_conflicts(
    website_normalized,
    crm_normalized,
):
    """
    Identify state and ZIP disagreements.

    These conflicts prevent a pair from being classified
    as a strong or possible candidate automatically.

    Missing values are not treated as conflicts.
    """

    conflicts = []

    website_state = website_normalized["state_norm"]
    crm_state = crm_normalized["state_norm"]

    if (
        website_state
        and crm_state
        and website_state != crm_state
    ):
        conflicts.append({
            "field": "state",
            "website_value": website_state,
            "crm_value": crm_state,
            "reason": "State values differ.",
        })

    website_zip = website_normalized["zip_norm"]
    crm_zip = crm_normalized["zip_norm"]

    if (
        website_zip
        and crm_zip
        and website_zip != crm_zip
    ):
        conflicts.append({
            "field": "zip",
            "website_value": website_zip,
            "crm_value": crm_zip,
            "reason": "ZIP code values differ.",
        })

    return conflicts


# ---------------------------------------------------------
# 7. Classify the candidate
# ---------------------------------------------------------

def classify_candidate(
    score,
    evidence_coverage,
    conflicts,
):
    """
    Assign a preliminary candidate classification.

    This is not an approval decision.
    """

    if conflicts:
        return "location_conflict"

    if (
        score >= STRONG_CANDIDATE_THRESHOLD
        and evidence_coverage >= MIN_STRONG_COVERAGE
    ):
        return "strong_candidate"

    if (
        score >= POSSIBLE_CANDIDATE_THRESHOLD
        and evidence_coverage >= MIN_POSSIBLE_COVERAGE
    ):
        return "possible_candidate"

    return "weak_candidate"


# ---------------------------------------------------------
# 8. Score one website record against one CRM record
# ---------------------------------------------------------

def score_pair(website_record, crm_record):
    """
    Compare one website community with one CRM account.

    Returns:
        - normalized field values
        - individual field comparisons
        - total weighted score
        - evidence coverage
        - supporting evidence
        - location conflicts
        - preliminary classification
    """

    website_normalized = normalize_website_record(
        website_record
    )

    crm_normalized = normalize_crm_record(
        crm_record
    )

    # Define which normalized fields to compare.
    comparisons = [
        (
            "name",
            website_normalized["name_norm"],
            crm_normalized["name_norm"],
            FIELD_WEIGHTS["name"],
            "fuzzy",
        ),
        (
            "street",
            website_normalized["street_norm"],
            crm_normalized["street_norm"],
            FIELD_WEIGHTS["street"],
            "fuzzy",
        ),
        (
            "zip",
            website_normalized["zip_norm"],
            crm_normalized["zip_norm"],
            FIELD_WEIGHTS["zip"],
            "exact",
        ),
        (
            "city",
            website_normalized["city_norm"],
            crm_normalized["city_norm"],
            FIELD_WEIGHTS["city"],
            "exact",
        ),
        (
            "state",
            website_normalized["state_norm"],
            crm_normalized["state_norm"],
            FIELD_WEIGHTS["state"],
            "exact",
        ),
    ]

    field_results = []

    for (
        field_name,
        website_value,
        crm_value,
        weight,
        method,
    ) in comparisons:

        result = compare_field(
            field_name=field_name,
            website_value=website_value,
            crm_value=crm_value,
            weight=weight,
            comparison_method=method,
        )

        field_results.append(result)

    # The score is out of 100.
    # Missing fields receive zero points.
    total_score = round(
        sum(
            result["weighted_points"]
            for result in field_results
        ),
        2,
    )

    # Coverage measures how much of the possible
    # comparison weight had values on both sides.
    available_weight = sum(
        result["weight"]
        for result in field_results
        if result["available"]
    )

    evidence_coverage = round(
        available_weight / sum(FIELD_WEIGHTS.values()) * 100,
        2,
    )

    conflicts = detect_location_conflicts(
        website_normalized,
        crm_normalized,
    )

    supporting_evidence = compare_supporting_evidence(
        website_normalized,
        crm_normalized,
    )

    classification = classify_candidate(
        score=total_score,
        evidence_coverage=evidence_coverage,
        conflicts=conflicts,
    )

    return {
        "website_name": website_record.get("name"),
        "crm_account_id": crm_record.get("account_id"),
        "crm_name": crm_record.get("name"),
        "score": total_score,
        "evidence_coverage": evidence_coverage,
        "classification": classification,
        "field_comparisons": field_results,
        "supporting_evidence": supporting_evidence,
        "location_conflicts": conflicts,
    }


# ---------------------------------------------------------
# 9. Run example tests
# ---------------------------------------------------------

if __name__ == "__main__":

    print("Testing scoring engine...\n")

    # Test 1: Exact match
    website_maplewood = {
        "name": "Bellhaven of Maplewood",
        "street_address": "210 Orchard Lane",
        "detail_city": "Maplewood",
        "detail_state": "OH",
        "zip_code": "44280",
        "phone": "(614) 250-9447",
        "detail_care_offerings": ["Assisted Living"],
    }

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

    maplewood_result = score_pair(
        website_maplewood,
        crm_maplewood,
    )

    print("MAPLEWOOD TEST")
    print("Score:", maplewood_result["score"])
    print("Coverage:", maplewood_result["evidence_coverage"])
    print("Classification:", maplewood_result["classification"])

    assert maplewood_result["score"] == 100
    assert maplewood_result["classification"] == "strong_candidate"
    assert not maplewood_result["location_conflicts"]

    # Test 2: Same location, different phone numbers
    owosso_website = {
        "name": "Bellhaven of Owosso",
        "street_address": "1120 W Main St",
        "detail_city": "Owosso",
        "detail_state": "MI",
        "zip_code": "48867",
        "phone": "(734) 503-1363",
        "detail_care_offerings": ["Assisted Living"],
    }

    owosso_crm = {
        "account_id": "TEST-OWOSSO",
        "name": "Bellhaven of Owosso",
        "billing_street": "1120 West Main Street",
        "billing_city": "Owosso",
        "billing_state": "MI",
        "billing_zip": "48867",
        "phone": "(330) 383-5991",
        "care_type": "Assisted Living",
    }

    owosso_result = score_pair(
        owosso_website,
        owosso_crm,
    )

    print("\nOWOSSO TEST")
    print("Score:", owosso_result["score"])
    print("Coverage:", owosso_result["evidence_coverage"])
    print("Classification:", owosso_result["classification"])
    print(
        "Phone status:",
        owosso_result["supporting_evidence"]["phone"]["status"],
    )

    assert owosso_result["score"] == 100
    assert (
        owosso_result["supporting_evidence"]["phone"]["status"]
        == "mismatch"
    )

    # Test 3: Same name, different state and ZIP
    conflict_crm = {
        "account_id": "TEST-CONFLICT",
        "name": "Bellhaven of Maplewood",
        "billing_street": "210 Orchard Lane",
        "billing_city": "Maplewood",
        "billing_state": "MI",
        "billing_zip": "49000",
        "phone": "",
        "care_type": "Assisted Living",
    }

    conflict_result = score_pair(
        website_maplewood,
        conflict_crm,
    )

    print("\nLOCATION CONFLICT TEST")
    print("Score:", conflict_result["score"])
    print("Classification:", conflict_result["classification"])
    print("Conflicts:", conflict_result["location_conflicts"])

    assert conflict_result["classification"] == "location_conflict"
    assert len(conflict_result["location_conflicts"]) == 2

    print("\nAll scoring tests passed.")

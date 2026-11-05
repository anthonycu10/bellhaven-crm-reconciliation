
import ast
import re
import unicodedata
import re


# ---------------------------------------------------------
# 1. General text cleanup
# ---------------------------------------------------------

def clean_text(value):
    """
    Convert a value into a clean, lowercase string.

    Examples:
        "  MAPLEWOOD  " -> "maplewood"
        None            -> ""
        "St. Mary's"    -> "st mary s"
    """

    if value is None:
        return ""

    text = str(value).strip().lower()

    # Normalize accented characters.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    # Replace punctuation with spaces.
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Collapse repeated whitespace.
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ---------------------------------------------------------
# 2. Community name normalization
# ---------------------------------------------------------

LEGAL_SUFFIXES = {
    "inc",
    "incorporated",
    "llc",
    "l l c",
    "ltd",
    "limited",
    "corp",
    "corporation",
}


def normalize_name(value):
    """
    Standardize community or account names.

    Removes punctuation, standardizes whitespace, and
    removes a legal suffix at the end of the name.

    It does NOT remove meaningful words such as:
        of, at, care, center, senior, living
    """

    text = clean_text(value)

    if not text:
        return ""

    words = text.split()

    # Remove legal suffixes only from the end.
    while words:
        last_word = words[-1]

        if last_word in LEGAL_SUFFIXES:
            words.pop()
        else:
            break

    return " ".join(words)


# ---------------------------------------------------------
# 3. Street address normalization
# ---------------------------------------------------------

STREET_ABBREVIATIONS = {
    # Street types
    "street": "st", "st": "st",
    "avenue": "ave", "ave": "ave",
    "road": "rd", "rd": "rd",
    "boulevard": "blvd", "blvd": "blvd",
    "drive": "dr", "dr": "dr",
    "lane": "ln", "ln": "ln",
    "court": "ct", "ct": "ct",
    "circle": "cir", "cir": "cir",
    "terrace": "ter", "ter": "ter",
    "highway": "hwy", "hwy": "hwy",
    "parkway": "pkwy", "pkwy": "pkwy",
    "place": "pl", "pl": "pl",
    "trail": "trl", "trl": "trl",

    # Cardinal directions
    "north": "n", "n": "n",
    "south": "s", "s": "s",
    "east": "e", "e": "e",
    "west": "w", "w": "w",

    # Compound directions
    "northeast": "ne", "ne": "ne",
    "northwest": "nw", "nw": "nw",
    "southeast": "se", "se": "se",
    "southwest": "sw", "sw": "sw",
}

def normalize_street(value):
    """
    Standardize common street abbreviations and directional words.
    """

    text = clean_text(value)

    if not text:
        return ""

    # Normalize punctuated directions: N.W., N. W., N.E., etc.
    text = re.sub(
        r'\b([nsew])\s*\.?\s+([nsew])\b',
        r'\1\2',
        text
    )

    # Remove remaining periods
    text = text.replace(".", "")

    words = text.split()

    normalized_words = [
        STREET_ABBREVIATIONS.get(word, word)
        for word in words
    ]

    return " ".join(normalized_words)

# ---------------------------------------------------------
# 4. City normalization
# ---------------------------------------------------------

def normalize_city(value):
    """
    Standardize city names.

    Does not remove meaningful words or attempt to
    infer alternate city names.
    """

    return clean_text(value)


# ---------------------------------------------------------
# 5. State normalization
# ---------------------------------------------------------

def normalize_state(value):
    """
    Standardize state abbreviations.

    The source data already uses two-letter state codes,
    so this function standardizes capitalization and
    whitespace rather than guessing full state names.
    """

    return clean_text(value).upper()


# ---------------------------------------------------------
# 6. ZIP code normalization
# ---------------------------------------------------------

def normalize_zip(value):
    """
    Return the five-digit ZIP code as a string.

    ZIP codes must remain strings because some begin
    with zero.

    A ZIP+4 value such as 02108-1234 becomes 02108.
    """

    if value is None:
        return ""

    # Avoid converting missing numeric values such as NaN
    # into the literal string "nan".
    if isinstance(value, float) and value != value:
        return ""

    digits = re.sub(r"\D", "", str(value).strip())

    if len(digits) < 5:
        return ""

    return digits[:5]


# ---------------------------------------------------------
# 7. Phone number normalization
# ---------------------------------------------------------

def normalize_phone(value):
    """
    Keep only digits from a phone number.

    Example:
        "(614) 250-9447" -> "6142509447"
    """

    if value is None:
        return ""

    digits = re.sub(r"\D", "", str(value))

    # Handle US numbers with a leading country code.
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    return digits


# ---------------------------------------------------------
# 8. Care offering normalization
# ---------------------------------------------------------

def normalize_care_type(value):
    """
    Normalize a single care offering.

    This standardizes formatting only. It does not assume
    that different care categories are equivalent.
    """

    text = clean_text(value)

    if not text:
        return ""

    # Standardize "and" and "&" formatting.
    text = re.sub(r"\s+and\s+", " and ", text)

    return text


def normalize_care_offerings(value):
    """
    Normalize one or more care offerings.

    Accepts:
        ["Assisted Living", "Memory Support"]

    Also accepts CSV-style text:
        "['Assisted Living', 'Memory Support']"

    Returns a sorted list of normalized offerings.
    """

    if value is None:
        return []

    # If the value is a string, try parsing a list
    # stored as text in the CSV.
    if isinstance(value, str):
        value = value.strip()

        if not value:
            return []

        try:
            parsed = ast.literal_eval(value)

            if isinstance(parsed, (list, tuple, set)):
                value = parsed
            else:
                value = [value]

        except (ValueError, SyntaxError):
            value = [value]

    # Handle an actual list or tuple.
    if not isinstance(value, (list, tuple, set)):
        value = [value]

    normalized = {
        normalize_care_type(item)
        for item in value
        if normalize_care_type(item)
    }

    return sorted(normalized)


# ---------------------------------------------------------
# 9. Normalize a complete website record
# ---------------------------------------------------------

def normalize_website_record(record):
    """
    Return a normalized copy of a website community.

    Original source values are preserved in the original
    record. This function creates a separate normalized
    representation for matching.
    """

    return {
        "name_norm": normalize_name(record.get("name")),
        "street_norm": normalize_street(
            record.get("street_address")
        ),
        "city_norm": normalize_city(
            record.get("detail_city")
        ),
        "state_norm": normalize_state(
            record.get("detail_state")
        ),
        "zip_norm": normalize_zip(
            record.get("zip_code")
        ),
        "phone_norm": normalize_phone(
            record.get("phone")
        ),
        "care_types_norm": normalize_care_offerings(
            record.get("detail_care_offerings")
        ),
    }


# ---------------------------------------------------------
# 10. Normalize a complete CRM record
# ---------------------------------------------------------

def normalize_crm_record(record):
    """
    Return a normalized copy of a CRM account.

    The CRM uses billing_* field names, so we map those
    into the same normalized structure as the website.
    """

    return {
        "name_norm": normalize_name(record.get("name")),
        "street_norm": normalize_street(
            record.get("billing_street")
        ),
        "city_norm": normalize_city(
            record.get("billing_city")
        ),
        "state_norm": normalize_state(
            record.get("billing_state")
        ),
        "zip_norm": normalize_zip(
            record.get("billing_zip")
        ),
        "phone_norm": normalize_phone(
            record.get("phone")
        ),
        "care_types_norm": normalize_care_offerings(
            record.get("care_type")
        ),
    }


# ---------------------------------------------------------
# 11. Basic tests
# ---------------------------------------------------------

if __name__ == "__main__":

    print("Testing normalization functions...\n")

    # Street address test
    street_1 = normalize_street("1120 W Main St.")
    street_2 = normalize_street("1120 West Main Street")

    print("Street 1:", street_1)
    print("Street 2:", street_2)

    assert street_1 == street_2

    # Name test
    name_1 = normalize_name("Bellhaven of Maplewood")
    name_2 = normalize_name("BELLHAVEN OF MAPLEWOOD")

    print("\nName 1:", name_1)
    print("Name 2:", name_2)

    assert name_1 == name_2

    # ZIP code test
    zip_code = normalize_zip("02108-1234")

    print("\nZIP:", zip_code)

    assert zip_code == "02108"

    # Phone test
    phone = normalize_phone("(614) 250-9447")

    print("\nPhone:", phone)

    assert phone == "6142509447"

    # Care offering test
    care = normalize_care_offerings(
        "['Assisted Living', 'Memory Support']"
    )

    print("\nCare offerings:", care)

    assert care == ["assisted living", "memory support"]

    print("\nAll basic tests passed.")

    print("\nTesting Owosso duplicate candidate...")

    owosso_1 = {
        "name": "Bellhaven of Owosso",
        "billing_street": "1120 W Main St",
        "billing_city": "Owosso",
        "billing_state": "MI",
        "billing_zip": "48867",
        "phone": "(734) 503-1363",
        "care_type": "Assisted Living",
    }

    owosso_2 = {
        "name": "Bellhaven of Owosso",
        "billing_street": "1120 West Main Street",
        "billing_city": "Owosso",
        "billing_state": "MI",
        "billing_zip": "48867",
        "phone": "(330) 383-5991",
        "care_type": "Assisted Living",
    }

    normalized_1 = normalize_crm_record(owosso_1)
    normalized_2 = normalize_crm_record(owosso_2)

    print("Account 1:", normalized_1)
    print("Account 2:", normalized_2)

    assert normalized_1["name_norm"] == normalized_2["name_norm"]
    assert normalized_1["street_norm"] == normalized_2["street_norm"]
    assert normalized_1["city_norm"] == normalized_2["city_norm"]
    assert normalized_1["state_norm"] == normalized_2["state_norm"]
    assert normalized_1["zip_norm"] == normalized_2["zip_norm"]

    assert normalized_1["phone_norm"] != normalized_2["phone_norm"]

    print("\nOwosso normalization test passed.")

    test_addresses = [
    "1250 NW Franklin St",
    "1250 nw franklin st",
    "1250 Northwest Franklin St",
    "1250 N.W. Franklin Street",
    "1250 N.E. Main St",
    "1250 Northeast Main Street",
    ]

    for address in test_addresses:
        print(f"{address:<35} -> {normalize_street(address)}")

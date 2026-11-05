import re
import unicodedata

def normalize_text(value):
    if value is None:
        return ""

    value = str(value).strip().lower()

    # Normalize accented characters
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )

    # Replace punctuation with spaces
    value = re.sub(r"[^a-z0-9\s]", " ", value)

    # Collapse repeated whitespace
    value = re.sub(r"\s+", " ", value).strip()

    return value


def normalize_address(value):
    value = normalize_text(value)

    replacements = {
        " street": " st",
        " avenue": " ave",
        " boulevard": " blvd",
        " road": " rd",
        " drive": " dr",
        " lane": " ln",
        " court": " ct",
        " highway": " hwy",
        " apartment": " apt",
        " suite": " ste",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return value


def normalize_state(value):
    return normalize_text(value).upper()


def normalize_zip(value):
    if value is None:
        return ""

    # Keep ZIP codes as strings; preserve leading zeros.
    value = str(value).strip()
    return value[:5] if value else ""
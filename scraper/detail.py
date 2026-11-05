
import re

from scraper.directory import get_soup


def scrape_detail_page(url):
    """
    Scrape an individual Bellhaven community detail page.
    """

    soup = get_soup(url)

    details = {}

    # Extract all label/value pairs from the detail section
    for dt in soup.select(".detail dt"):

        dd = dt.find_next_sibling("dd")

        if not dd:
            continue

        key = dt.get_text(" ", strip=True).lower()

        # get_text(" ", strip=True) combines text separated by <br>
        value = dd.get_text(" ", strip=True)

        details[key] = value

    # --------------------------------
    # Extract and parse address
    # --------------------------------

    address_text = details.get("address")

    street_address = None
    city = None
    state = None
    zip_code = None

    if address_text:

        # Example:
        # "210 Orchard Lane Maplewood, OH 44280"

        # Split the address into two lines using the HTML <br>
        address_element = soup.find(
            "dt",
            string=re.compile(r"^\s*Address\s*$", re.I)
        )

        if address_element:

            address_dd = address_element.find_next_sibling("dd")

            address_lines = [
                line.strip()
                for line in address_dd.stripped_strings
            ]

            if len(address_lines) >= 2:

                street_address = address_lines[0]

                location_line = address_lines[1]

                # Extract city, state and ZIP
                match = re.match(
                    r"^(.*),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$",
                    location_line
                )

                if match:
                    city = match.group(1).strip()
                    state = match.group(2)
                    zip_code = match.group(3)

    # --------------------------------
    # Extract care offerings
    # --------------------------------

    care_offerings = []

    care_element = soup.find(
        "dt",
        string=re.compile(r"^\s*Care Offerings\s*$", re.I)
    )

    if care_element:

        care_dd = care_element.find_next_sibling("dd")

        care_offerings = [
            badge.get_text(" ", strip=True)
            for badge in care_dd.select(".badge")
        ]

    # --------------------------------
    # Return structured record
    # --------------------------------

    return {
        "street_address": street_address,
        "detail_city": city,
        "detail_state": state,
        "zip_code": zip_code,
        "detail_care_offerings": care_offerings,
        "administrator": details.get("administrator"),
        "phone": details.get("phone")
    }

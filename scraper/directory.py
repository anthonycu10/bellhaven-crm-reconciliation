# to extract communication information from all three pages on the Bellhaven site 

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scraper.config import (
    BASE_URL,
    DIRECTORY_URL,
    REQUEST_TIMEOUT
)

# using a session instead of requests.get() so that we can reuse the underlying connection
session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0 BellhavenAssessmentBot/1.0"
})

def get_soup(url):
    """
    Retrieve a webpage and return its parsed HTML.
    """

    # sends an HTTP GET request 
    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT
    )

    # error check
    response.raise_for_status()

    # return the HTML response 
    return BeautifulSoup(
        response.text,
        "html.parser"
    )

def extract_community_cards(soup, page_url):
    """
    Extract community information from one directory page.
    """

    communities = []

    cards = soup.select(".cardgrid .card")

    for card in cards:

        link = card.select_one("h3 a")
        city_element = card.select_one(".city")

        if not link:
            continue

        name = link.get_text(" ", strip=True)

        detail_url = urljoin(
            BASE_URL,
            link.get("href")
        )

        city_state = (
            city_element.get_text(" ", strip=True)
            if city_element
            else None
        )

        # Split "Maplewood, OH" into city and state
        if city_state and "," in city_state:
            city, state = [
                value.strip()
                for value in city_state.rsplit(",", 1)
            ]
        else:
            city = city_state
            state = None

        care_offerings = [
            badge.get_text(" ", strip=True)
            for badge in card.select(".badge")
        ]

        communities.append({
            "name": name,
            "detail_url": detail_url,
            "city": city,
            "state": state,
            "care_offerings": care_offerings,
            "source_page": page_url
        })

    return communities

import time

from scraper.config import REQUEST_DELAY


def scrape_directory():
    """
    Scrape all pages of the community directory.
    """

    url = DIRECTORY_URL

    all_communities = []
    visited_pages = set()

    while url:

        # Prevent revisiting the same page
        if url in visited_pages:
            break

        visited_pages.add(url)

        print(f"Scraping directory: {url}")

        soup = get_soup(url)

        communities = extract_community_cards(
            soup,
            url
        )

        all_communities.extend(communities)

        # Look for the Next page link
        next_link = None

        for link in soup.select(".pager a[href]"):

            link_text = link.get_text(" ", strip=True).lower()

            if "next" in link_text:
                next_link = link
                break

        if next_link:
            url = urljoin(
                BASE_URL,
                next_link["href"]
            )
        else:
            url = None

        time.sleep(REQUEST_DELAY)

    return all_communities
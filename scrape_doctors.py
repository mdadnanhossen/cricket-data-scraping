import csv
import re
import time
import random
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup, NavigableString, Tag

BASE_URL = "https://doctor.bd"
LIST_URL = "https://doctor.bd/doctors"
OUTPUT = "doctors_data.csv"
TARGET = 2000

COLUMNS = [
    "doctor_name",
    "specialty",
    "qualification",
    "designation",
    "hospital",
    "location",
    "experience",
    "profile_url"
]

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
})


def clean(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if text else "N/A"


def fetch(url):
    for attempt in range(3):
        try:
            response = session.get(url, timeout=15)
            if response.status_code == 200:
                return response.text
        except requests.RequestException:
            pass
        time.sleep(2)
    return None


# ------------------------------------------------------------------
# FIX #1: profile page "Doctor information" box.
# On the real page the order is LABEL then VALUE for specialty /
# workplace / location (e.g. "Specialty" followed by "ENT"), but the
# small stat counters at the top are VALUE then LABEL (e.g. "—"
# followed by "Years"). The old code used texts[i-1] for everything,
# which only matched the "years" case and grabbed the WRONG
# neighbouring text for specialty/workplace/location.
# ------------------------------------------------------------------
def parse_profile(url):
    html = fetch(url)

    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    texts = [clean(x) for x in soup.stripped_strings]
    n = len(texts)

    data = {}

    for i, text in enumerate(texts):
        key = text.lower()

        if key == "years" and i > 0:
            # value comes BEFORE the "Years" label
            value = texts[i - 1]
            if value not in ("-", "—", "N/A"):
                data["experience"] = (
                    value if "year" in value.lower() else value + " Years"
                )

        elif key == "specialty" and i + 1 < n:
            # value comes AFTER the "Specialty" label
            data["specialty"] = texts[i + 1]

        elif key == "workplace" and i + 1 < n:
            # value comes AFTER the "Workplace" label
            data["hospital"] = texts[i + 1]

        elif key == "location" and i + 1 < n:
            # value comes AFTER the "Location" label
            data["location"] = texts[i + 1]

    return data


# ------------------------------------------------------------------
# FIX #2: listing page card boundaries.
# The old code climbed up parents looking for a container with
# exactly 1 doctor-link + 1 "Profile"-link + 1 heading. That
# condition can basically never be true (every card has 2-3 links to
# the same /doctor/<slug> URL: the thumbnail, the name, and the
# "Profile" button) - so it kept climbing until it grabbed a huge
# ancestor spanning MANY cards. That's why specialty/qualification/
# etc. could bleed between doctors and "experience" repeated the
# same value for the whole page.
#
# Fix: walk forward from the name heading using next_elements and
# stop the instant we hit THIS card's own "Profile" link. That is a
# precise, unambiguous boundary - no ancestor guessing needed.
# ------------------------------------------------------------------
def parse_listing(html):
    soup = BeautifulSoup(html, "html.parser")
    records = []

    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):

        link = heading.find("a", href=True)
        if not link:
            continue

        href = link.get("href", "")
        if not re.search(r"/doctor/[A-Za-z0-9-]+/?$", href):
            continue

        name = clean(link.get_text())
        profile_url = urljoin(BASE_URL, href)

        values = []
        experience = "N/A"

        for node in heading.next_elements:
            # stop as soon as we reach this card's own "Profile" button
            if isinstance(node, Tag) and node.name == "a":
                node_text = clean(node.get_text())
                if node_text.lower() == "profile":
                    break

            if isinstance(node, NavigableString):
                text = clean(str(node))

                if text in ("N/A", name):
                    continue

                # experience badge, e.g. "17+ Years" or "Not specified"
                if re.fullmatch(r"\d+\+?\s*Years?", text, re.IGNORECASE):
                    if experience == "N/A":
                        experience = text
                    continue
                if text.lower() == "not specified":
                    continue

                if text not in values:
                    values.append(text)

        specialty = values[0] if len(values) > 0 else "N/A"
        qualification = values[1] if len(values) > 1 else "N/A"
        designation = values[2] if len(values) > 2 else "N/A"
        hospital = values[3] if len(values) > 3 else "N/A"

        records.append({
            "doctor_name": name,
            "specialty": specialty,
            "qualification": qualification,
            "designation": designation,
            "hospital": hospital,
            "location": "N/A",
            "experience": experience,
            "profile_url": profile_url
        })

    return records


def save_csv(records):
    with open(OUTPUT, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(records)


def main():
    records = []
    seen_urls = set()
    page = 1
    consecutive_empty_pages = 0

    while len(records) < TARGET and page <= 450:  # safety cap on pages

        print(f"Page {page} | Records collected: {len(records)}")

        listing_url = f"{LIST_URL}?page={page}"
        html = fetch(listing_url)

        if not html:
            print("Page request failed.")
            consecutive_empty_pages += 1
            if consecutive_empty_pages >= 3:
                print("Too many failed pages in a row - stopping.")
                break
            page += 1
            continue

        doctors = parse_listing(html)

        if not doctors:
            print("No doctors found on this page.")
            consecutive_empty_pages += 1
            if consecutive_empty_pages >= 3:
                print("3 empty pages in a row - assuming end of pagination.")
                break
            page += 1
            continue

        consecutive_empty_pages = 0

        for doctor in doctors:
            profile_url = doctor["profile_url"]

            if profile_url in seen_urls:
                continue

            profile = parse_profile(profile_url)

            if profile.get("location"):
                doctor["location"] = profile["location"]
            if profile.get("experience"):
                doctor["experience"] = profile["experience"]
            if profile.get("specialty"):
                doctor["specialty"] = profile["specialty"]
            if profile.get("hospital"):
                doctor["hospital"] = profile["hospital"]

            records.append(doctor)
            seen_urls.add(profile_url)

            print(f"{len(records)}. {doctor['doctor_name']}")

            # checkpoint every 50 records so a crash doesn't lose everything
            if len(records) % 50 == 0:
                save_csv(records)
                print(f"    ... checkpoint saved ({len(records)} records)")

            if len(records) >= TARGET:
                break

            time.sleep(random.uniform(1, 2))

        page += 1

    save_csv(records)

    print()
    print("=" * 50)
    print("SCRAPING COMPLETE")
    print("=" * 50)
    print("Total records:", len(records))
    print("Total columns:", len(COLUMNS))
    print("Output file:", OUTPUT)
    print("=" * 50)


if __name__ == "__main__":
    main()
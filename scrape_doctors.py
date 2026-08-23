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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
})


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip() or "N/A"


def fetch(url):
    for attempt in range(3):
        try:
            r = session.get(url, timeout=15)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass

        time.sleep(2 * (attempt + 1))

    return None


def get_profile_data(url):
    html = fetch(url)

    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    texts = [clean(x) for x in soup.stripped_strings]

    data = {}

    for i, text in enumerate(texts):
        key = text.lower()

        if i == 0:
            continue

        if key == "location":
            data["location"] = texts[i - 1]

        elif key == "workplace":
            data["hospital"] = texts[i - 1]

        elif key == "specialty":
            data["specialty"] = texts[i - 1]

        elif key == "years":
            value = texts[i - 1]

            if value not in ("-", "—", "N/A"):
                data["experience"] = (
                    value if "year" in value.lower()
                    else value + " Years"
                )

    return data


def parse_listing(html):
    soup = BeautifulSoup(html, "html.parser")
    records = []

    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):

        doctor_link = heading.find("a", href=True)

        if not doctor_link:
            continue

        href = doctor_link["href"]

        if not re.search(r"/doctor/[A-Za-z0-9-]+/?$", href):
            continue

        name = clean(doctor_link.get_text())
        profile_url = urljoin(BASE_URL, href)

        values = []

        for element in heading.next_elements:

            if isinstance(element, Tag):
                if element.name == "a":
                    link_text = clean(element.get_text()).lower()

                    if link_text == "profile":
                        break

                    if link_text == "appointment":
                        continue

            if isinstance(element, NavigableString):

                parent = element.parent

                if parent and parent.name in ["script", "style"]:
                    continue

                if parent and parent.name == "a":
                    continue

                text = clean(str(element))

                if text and text not in values:
                    values.append(text)

        specialty = values[0] if len(values) > 0 else "N/A"
        qualification = values[1] if len(values) > 1 else "N/A"
        designation = values[2] if len(values) > 2 else "N/A"
        hospital = values[3] if len(values) > 3 else "N/A"

        experience = "N/A"

        previous_links = heading.find_all_previous(
            "a",
            limit=5
        )

        for link in previous_links:
            text = clean(link.get_text())

            if "year" in text.lower():
                experience = text
                break

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


records = []
seen = set()
page = 1

while len(records) < TARGET:

    print(f"Page {page} | Records: {len(records)}")

    html = fetch(f"{LIST_URL}?page={page}")

    if not html:
        page += 1
        continue

    doctors = parse_listing(html)

    if not doctors:
        print("No more doctors found.")
        break

    for doctor in doctors:

        url = doctor["profile_url"]

        if url in seen:
            continue

        profile = get_profile_data(url)

        if profile.get("location"):
            doctor["location"] = profile["location"]

        if profile.get("experience"):
            doctor["experience"] = profile["experience"]

        if doctor["specialty"] == "N/A":
            doctor["specialty"] = profile.get(
                "specialty",
                "N/A"
            )

        if doctor["hospital"] == "N/A":
            doctor["hospital"] = profile.get(
                "hospital",
                "N/A"
            )

        records.append(doctor)
        seen.add(url)

        print(
            f"  {len(records)}/"
            f"{TARGET} - "
            f"{doctor['doctor_name']}"
        )

        if len(records) >= TARGET:
            break

        time.sleep(random.uniform(1, 2))

    page += 1


with open(
    OUTPUT,
    "w",
    newline="",
    encoding="utf-8"
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=COLUMNS
    )

    writer.writeheader()
    writer.writerows(records)


print("\nScraping complete!")
print("Total records:", len(records))
print("Total columns:", len(COLUMNS))
print("CSV file:", OUTPUT)
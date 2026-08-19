import csv
import re
import time
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

BASE_URL = "https://www.tigercricket.com.bd"
TARGET_WORDS = 2000
OUTPUT_FILE = "scraped_data.csv"
DELAY = 1

CATEGORIES = {
    "Latest News": f"{BASE_URL}/category/latest-news",
    "Media Release": f"{BASE_URL}/category/media-release",
    "BCB Election 2026": f"{BASE_URL}/category/bcb-election-2026",
    "Notun Kuri Sports 2026": f"{BASE_URL}/category/notun-kuri-sports-2026",
    "Women's Cricket": f"{BASE_URL}/category/women",
    "High Performance": f"{BASE_URL}/category/high-performance"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
}

def clean(text):
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()

def get_soup(session, url):
    try:
        r = session.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return BeautifulSoup(r.text, "html.parser")
    except requests.RequestException as e:
        print("Error:", url, e)
        return None

def get_content(soup):
    for tag in soup(["script", "style", "nav", "header",
                     "footer", "noscript"]):
        tag.decompose()

    texts, seen = [], set()

    for p in soup.find_all("p"):
        text = clean(p.get_text(" ", strip=True))
        if len(text.split()) < 3 or text in seen:
            continue
        if any(x in text.lower() for x in
               ["all rights reserved", "contact us",
                "read more", "load more", "back to top"]):
            continue
        seen.add(text)
        texts.append(text)

    return " ".join(texts)

def get_title(soup):
    tag = soup.find("meta", property="og:title")
    if tag and tag.get("content"):
        return clean(tag["content"])

    h1 = soup.find("h1")
    return clean(h1.get_text(" ", strip=True)) if h1 else ""

def scrape_article(session, category, url):
    soup = get_soup(session, url)
    if not soup:
        return None

    title = get_title(soup)
    content = get_content(soup)

    if not title or not content:
        return None

    date = soup.find("meta", property="article:published_time")
    author = soup.find("meta", attrs={"name": "author"})
    image = soup.find("meta", property="og:image")

    return {
        "title": title,
        "category": category,
        "published_date": date.get("content", "") if date else "",
        "author": author.get("content", "") if author else "",
        "url": url,
        "image_url": image.get("content", "") if image else "",
        "content": content,
        "word_count": len(content.split())
    }

def collect_links(session):
    links = []
    seen = set()

    for category, page in CATEGORIES.items():
        print("Scanning:", category)
        soup = get_soup(session, page)

        if not soup:
            continue

        for a in soup.find_all("a", href=True):
            href = a["href"]

            if "/detail/" not in href:
                continue

            url = urljoin(BASE_URL, href)

            if url not in seen:
                seen.add(url)
                links.append((category, url))

        time.sleep(DELAY)

    return links

def save_csv(records):
    if not records:
        print("No data found.")
        return

    fields = [
        "title", "category", "published_date", "author",
        "url", "image_url", "content", "word_count"
    ]

    with open(OUTPUT_FILE, "w", newline="",
              encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

def main():
    session = requests.Session()
    records = []
    seen_content = set()
    total_words = 0

    print("Collecting article links...")
    links = collect_links(session)
    print("Found:", len(links), "articles")

    for i, (category, url) in enumerate(links, 1):
        if total_words >= TARGET_WORDS:
            break

        print(f"[{i}/{len(links)}] Scraping:", url)

        record = scrape_article(session, category, url)

        if not record:
            continue

        if record["content"] in seen_content:
            print("Duplicate skipped")
            continue

        seen_content.add(record["content"])
        records.append(record)
        total_words += record["word_count"]

        print("Words:", record["word_count"],
              "| Total:", total_words)

        time.sleep(DELAY)

    save_csv(records)

    print("\nScraping Complete!")
    print("Records:", len(records))
    print("Total Words:", total_words)
    print("CSV:", OUTPUT_FILE)

if __name__ == "__main__":
    main()
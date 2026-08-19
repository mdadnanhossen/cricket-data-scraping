import csv
import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================================
# CONFIGURATION
# ============================================================================

BASE_URL = "https://www.tigercricket.com.bd"

CATEGORY_PAGES = {
    "Latest News": f"{BASE_URL}/category/latest-news",
    "Media Release": f"{BASE_URL}/category/media-release",
    "BCB Election 2026": f"{BASE_URL}/category/bcb-election-2026",
    "Notun Kuri Sports 2026": f"{BASE_URL}/category/notun-kuri-sports-2026",
    "Women's Cricket": f"{BASE_URL}/category/women",
    "High Performance": f"{BASE_URL}/category/high-performance",
}


# Real static pages used only if article content is not enough
STATIC_PAGES = {
    "History": f"{BASE_URL}/history",
    "Board of Directors": f"{BASE_URL}/board-of-directors",
    "Former Presidents": f"{BASE_URL}/former-presidents",
    "Standing Committees": f"{BASE_URL}/standing-committees",
    "Policies and Guidelines": f"{BASE_URL}/policies-and-guidelines",
    "Constitution": f"{BASE_URL}/constitution",
    "Legal Entity": f"{BASE_URL}/legal-entity",
    "Development Program": f"{BASE_URL}/development-program",
    "Bangladesh Tigers": f"{BASE_URL}/bangladesh-tigers",
    "Physically Challenged": f"{BASE_URL}/physically-challenged",
    "Organogram": f"{BASE_URL}/organogram",
    "Opportunity": f"{BASE_URL}/opportunity",
}


TARGET_WORD_COUNT = 2000
MAX_ARTICLES = 120
REQUEST_DELAY_SECONDS = 1.0
OUTPUT_FILE = "scraped_data.csv"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ============================================================================
# TEXT CLEANING
# ============================================================================

BOILERPLATE_MARKERS = [
    "all rights reserved",
    "contact us",
    "read more",
    "load more",
    "back to top",
    "tweets by",
]


def clean_text(text: str) -> str:
    """
    Clean and normalize text.
    """
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def is_boilerplate(text: str) -> bool:
    """
    Check whether a text fragment is unnecessary website boilerplate.
    """
    lower_text = text.lower()

    return any(
        marker in lower_text
        for marker in BOILERPLATE_MARKERS
    )


def word_count(text: str) -> int:
    """
    Count words in a text.
    """
    if not text:
        return 0

    return len(text.split())


# ============================================================================
# REQUEST + BEAUTIFULSOUP
# ============================================================================

def get_soup(session: requests.Session, url: str):
    """
    Fetch webpage using Requests and parse it using BeautifulSoup.
    """

    try:
        response = session.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

    except requests.exceptions.RequestException as error:
        print(f"  [WARNING] Could not fetch: {url}")
        print(f"  [ERROR] {error}")
        return None

    response.encoding = response.apparent_encoding or "utf-8"

    return BeautifulSoup(
        response.text,
        "html.parser"
    )


# ============================================================================
# META DATA EXTRACTION
# ============================================================================

def extract_meta(soup: BeautifulSoup, names):
    """
    Try multiple meta tag names and return the first available value.
    """

    for name in names:

        tag = (
            soup.find("meta", attrs={"property": name})
            or soup.find("meta", attrs={"name": name})
        )

        if tag and tag.get("content"):
            return clean_text(tag["content"])

    return ""


# ============================================================================
# MAIN CONTENT EXTRACTION
# ============================================================================

def extract_main_text(soup: BeautifulSoup) -> str:
    """
    Extract meaningful paragraph text from the webpage.

    Removes:
    - script
    - style
    - navigation
    - header
    - footer
    - noscript

    Also removes:
    - empty text
    - very short text
    - duplicate paragraphs
    - common boilerplate
    """

    working_soup = BeautifulSoup(
        str(soup),
        "html.parser"
    )

    # Remove unnecessary HTML elements
    for tag in working_soup(
        [
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "noscript"
        ]
    ):
        tag.decompose()

    paragraphs = []
    seen_paragraphs = set()

    for paragraph in working_soup.find_all("p"):

        text = clean_text(
            paragraph.get_text(" ", strip=True)
        )

        # Ignore empty text
        if not text:
            continue

        # Ignore extremely short text
        if len(text.split()) < 3:
            continue

        # Ignore boilerplate
        if is_boilerplate(text):
            continue

        # Remove duplicate paragraphs
        if text in seen_paragraphs:
            continue

        seen_paragraphs.add(text)
        paragraphs.append(text)

    return " ".join(paragraphs)


# ============================================================================
# COLLECT ARTICLE LINKS
# ============================================================================

def collect_article_links(session: requests.Session):

    """
    Visit all selected category pages and collect unique article URLs.
    """

    links = []
    seen_urls = set()

    print("\nCollecting article links...\n")

    for category, category_url in CATEGORY_PAGES.items():

        print(
            f"Scanning category: {category}"
        )

        soup = get_soup(
            session,
            category_url
        )

        if soup is None:
            continue

        for anchor in soup.find_all(
            "a",
            href=True
        ):

            href = anchor["href"]

            # TigerCricket article URLs
            if "/detail/" not in href:
                continue

            full_url = urljoin(
                BASE_URL,
                href
            )

            # Remove duplicate URLs
            if full_url in seen_urls:
                continue

            seen_urls.add(full_url)

            links.append(
                (
                    category,
                    full_url
                )
            )

        time.sleep(
            REQUEST_DELAY_SECONDS
        )

    print(
        f"\nFound {len(links)} unique article links.\n"
    )

    return links


# ============================================================================
# SCRAPE ARTICLE
# ============================================================================

def scrape_article(
    session: requests.Session,
    category: str,
    url: str
):

    """
    Scrape one article page.
    """

    soup = get_soup(
        session,
        url
    )

    if soup is None:
        return None

    # ------------------------------------------------------------
    # TITLE
    # ------------------------------------------------------------

    title = extract_meta(
        soup,
        [
            "og:title",
            "twitter:title"
        ]
    )

    if not title:

        h1 = soup.find("h1")

        if h1:
            title = clean_text(
                h1.get_text(" ", strip=True)
            )

    if not title:

        print(
            f"  [SKIP] No title found: {url}"
        )

        return None

    # ------------------------------------------------------------
    # OTHER INFORMATION
    # ------------------------------------------------------------

    published_date = extract_meta(
        soup,
        [
            "article:published_time"
        ]
    )

    author = extract_meta(
        soup,
        [
            "author",
            "article:author"
        ]
    )

    image_url = extract_meta(
        soup,
        [
            "og:image"
        ]
    )

    # ------------------------------------------------------------
    # CONTENT
    # ------------------------------------------------------------

    content = extract_main_text(
        soup
    )

    if not content:

        print(
            f"  [SKIP] No usable content: {url}"
        )

        return None

    return {
        "title": title,
        "category": category,
        "published_date": published_date,
        "author": author,
        "url": url,
        "image_url": image_url,
        "content": content,
        "word_count": word_count(content)
    }


# ============================================================================
# SCRAPE STATIC PAGE
# ============================================================================

def scrape_static_page(
    session: requests.Session,
    name: str,
    url: str
):

    """
    Scrape a real static page from the website.
    """

    soup = get_soup(
        session,
        url
    )

    if soup is None:
        return None

    title = extract_meta(
        soup,
        [
            "og:title",
            "twitter:title"
        ]
    )

    if not title:

        h1 = soup.find("h1")

        if h1:

            title = clean_text(
                h1.get_text(" ", strip=True)
            )

        else:
            title = name

    content = extract_main_text(
        soup
    )

    if not content:
        return None

    return {
        "title": title,
        "category": "About BCB",
        "published_date": "",
        "author": "",
        "url": url,
        "image_url": extract_meta(
            soup,
            ["og:image"]
        ),
        "content": content,
        "word_count": word_count(content)
    }


# ============================================================================
# DUPLICATE CHECK
# ============================================================================

def is_duplicate_record(
    record,
    seen_urls,
    seen_contents
):

    """
    Check whether a record is already collected.
    """

    if not record:
        return True

    if not record["content"]:
        return True

    # Duplicate URL
    if record["url"] in seen_urls:
        return True

    # Duplicate full content
    if record["content"] in seen_contents:
        return True

    return False


# ============================================================================
# MAIN PROGRAM
# ============================================================================

def main():

    print("=" * 70)
    print("BANGLADESH CRICKET BOARD DATA SCRAPER")
    print("=" * 70)

    session = requests.Session()

    records = []

    seen_urls = set()
    seen_contents = set()

    total_words = 0

    # ================================================================
    # STEP 1: COLLECT ARTICLE LINKS
    # ================================================================

    article_links = collect_article_links(
        session
    )

    # ================================================================
    # STEP 2: SCRAPE ARTICLES
    # ================================================================

    print("Starting article scraping...\n")

    for index, (category, url) in enumerate(
        article_links,
        start=1
    ):

        # Stop only when UNIQUE content has reached 2000 words
        if total_words >= TARGET_WORD_COUNT:
            break

        if len(records) >= MAX_ARTICLES:
            break

        print(
            f"[{index}/{len(article_links)}] "
            f"Scraping article:"
        )

        print(url)

        record = scrape_article(
            session,
            category,
            url
        )

        if record is None:
            time.sleep(
                REQUEST_DELAY_SECONDS
            )
            continue

        # ------------------------------------------------------------
        # DUPLICATE CHECK BEFORE ADDING RECORD
        # ------------------------------------------------------------

        if is_duplicate_record(
            record,
            seen_urls,
            seen_contents
        ):

            print(
                "  -> Duplicate content/URL skipped"
            )

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

            continue

        # ------------------------------------------------------------
        # ADD UNIQUE RECORD
        # ------------------------------------------------------------

        records.append(
            record
        )

        seen_urls.add(
            record["url"]
        )

        seen_contents.add(
            record["content"]
        )

        total_words += record["word_count"]

        print(
            f"  -> {record['word_count']} words "
            f"(unique running total: {total_words})"
        )

        time.sleep(
            REQUEST_DELAY_SECONDS
        )

    # ================================================================
    # STEP 3: STATIC PAGES IF STILL BELOW 2000 WORDS
    # ================================================================

    if total_words < TARGET_WORD_COUNT:

        print(
            "\nArticle content is below 2000 words."
        )

        print(
            "Checking additional real static pages...\n"
        )

        for name, url in STATIC_PAGES.items():

            if total_words >= TARGET_WORD_COUNT:
                break

            print(
                f"Scraping static page: {name}"
            )

            print(url)

            record = scrape_static_page(
                session,
                name,
                url
            )

            if record is None:

                time.sleep(
                    REQUEST_DELAY_SECONDS
                )

                continue

            # --------------------------------------------------------
            # DUPLICATE CHECK
            # --------------------------------------------------------

            if is_duplicate_record(
                record,
                seen_urls,
                seen_contents
            ):

                print(
                    "  -> Duplicate content/URL skipped"
                )

                time.sleep(
                    REQUEST_DELAY_SECONDS
                )

                continue

            # --------------------------------------------------------
            # ADD UNIQUE STATIC PAGE
            # --------------------------------------------------------

            records.append(
                record
            )

            seen_urls.add(
                record["url"]
            )

            seen_contents.add(
                record["content"]
            )

            total_words += record["word_count"]

            print(
                f"  -> {record['word_count']} words "
                f"(unique running total: {total_words})"
            )

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

    # ================================================================
    # STEP 4: FINAL WORD COUNT
    # ================================================================

    total_words = sum(
        record["word_count"]
        for record in records
    )

    # ================================================================
    # STEP 5: SAVE CSV
    # ================================================================

    if records:

        fieldnames = [
            "title",
            "category",
            "published_date",
            "author",
            "url",
            "image_url",
            "content",
            "word_count"
        ]

        with open(
            OUTPUT_FILE,
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as csv_file:

            writer = csv.DictWriter(
                csv_file,
                fieldnames=fieldnames
            )

            writer.writeheader()

            writer.writerows(
                records
            )

    # ================================================================
    # STEP 6: FINAL REPORT
    # ================================================================

    print("\n")
    print("=" * 70)
    print("SCRAPING COMPLETE")
    print("=" * 70)

    print(
        f"Number of records scraped : {len(records)}"
    )

    print(
        f"Total word count          : {total_words}"
    )

    print(
        f"CSV filename              : {OUTPUT_FILE}"
    )

    if total_words >= TARGET_WORD_COUNT:

        print(
            "Confirmation              : "
            "Dataset contains 2000+ words. OK"
        )

    else:

        print(
            "Confirmation              : "
            f"Dataset is below 2000 words "
            f"({total_words} words)."
        )

        print(
            "No fake content was added."
        )

    print("=" * 70)


# ============================================================================
# PROGRAM START
# ============================================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print(
            "\nScraping interrupted by user."
        )

        sys.exit(1)

    except Exception as error:

        print(
            "\nUnexpected error occurred:"
        )

        print(error)

        sys.exit(1)
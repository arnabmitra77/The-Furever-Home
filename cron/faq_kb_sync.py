"""
Furever Home — Pet Care FAQ Knowledge Base Sync
================================================
Fetches pet care articles from reputable sources (ASPCA, PetMD, AKC)
and writes them to the `pet_care_kb` tab in your Google Sheet.

REQUIRED SETUP (one-time, see README_CRON.md):
  1. GOOGLE_CREDENTIALS_JSON — service-account JSON string (or path)
  2. SHEET_ID               — your Google Sheet ID

Run locally : python faq_kb_sync.py
Run dry-run : python faq_kb_sync.py --dry-run
Run on GitHub Actions : see .github/workflows/faq_kb_sync.yml
"""

import os
import sys
import json
import time
import hashlib
import re
import logging
import gspread
import requests
import feedparser
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — set these as environment variables or edit directly for
# local testing (never commit real keys to GitHub)
# ─────────────────────────────────────────────────────────────────────────────
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
SHEET_ID          = os.environ.get("SHEET_ID", "1Xg4T3vmhoLxN0C2lEBFaN88Y2LSvoF6DQVoCxL3dt80")

# Google Sheet worksheet name for the knowledge base
WORKSHEET_NAME = "pet_care_kb"

# Required sheet columns in order
COLUMNS = [
    "articleId", "title", "url", "source", "category",
    "summary", "keywords", "fullText", "fetchedAt"
]

# Maximum rows allowed in the knowledge base (excluding header)
MAX_ROWS = 500

# ─────────────────────────────────────────────────────────────────────────────
# CLI ARGUMENT PARSING
# ─────────────────────────────────────────────────────────────────────────────
DRY_RUN = "--dry-run" in sys.argv

# ─────────────────────────────────────────────────────────────────────────────
# STOP WORDS — common English words excluded from keyword extraction
# ─────────────────────────────────────────────────────────────────────────────
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "dare",
    "it", "its", "this", "that", "these", "those", "i", "you", "he", "she",
    "we", "they", "me", "him", "her", "us", "them", "my", "your", "his",
    "our", "their", "what", "which", "who", "whom", "when", "where", "why",
    "how", "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "no", "not", "only", "own", "same", "so", "than",
    "too", "very", "just", "about", "above", "after", "again", "also",
    "as", "if", "into", "through", "during", "before", "between", "up",
    "down", "out", "off", "over", "under", "then", "once", "here", "there",
}

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY KEYWORDS — used by categorize_article()
# ─────────────────────────────────────────────────────────────────────────────
CATEGORY_KEYWORDS = {
    "nutrition": ["food", "diet", "feed", "feeding", "nutrition", "nutrient", "meal", "eat", "eating"],
    "training": ["train", "training", "obedience", "command", "commands", "trick", "tricks", "leash"],
    "health": ["vet", "veterinary", "disease", "symptom", "symptoms", "health", "medical", "illness", "vaccine", "vaccination"],
    "behavior": ["aggression", "aggressive", "anxiety", "anxious", "behavior", "behaviour", "bark", "barking", "bite", "biting"],
}

# ─────────────────────────────────────────────────────────────────────────────
# ARTICLE TRANSFORMATION AND FIELD EXTRACTION UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def extract_keywords(title, summary):
    """
    Extract keywords from title and summary text.

    Tokenizes into lowercase words, removes stop words and non-alphabetic tokens,
    and returns at most 10 unique lowercase alphabetic terms as a comma-separated string.

    Args:
        title: Article title string.
        summary: Article summary string.

    Returns:
        Comma-separated string of at most 10 unique lowercase alphabetic keywords.
    """
    combined = f"{title} {summary}".lower()
    # Split on non-alpha characters to get individual words
    tokens = re.split(r'[^a-z]+', combined)
    # Filter: must be alphabetic, not empty, not a stop word
    seen = set()
    keywords = []
    for token in tokens:
        if token and token.isalpha() and token not in STOP_WORDS and token not in seen:
            seen.add(token)
            keywords.append(token)
            if len(keywords) >= 10:
                break
    return ",".join(keywords)


def truncate_text(html_content, max_chars=1500):
    """
    Strip HTML tags and truncate text at the last complete word boundary.

    Uses BeautifulSoup to remove all HTML markup, then truncates at the last
    complete word boundary at or within max_chars.

    Args:
        html_content: HTML string to process.
        max_chars: Maximum character length for the output (default 1500).

    Returns:
        Plain text string with no HTML markup, truncated at a word boundary,
        at most max_chars characters long.
    """
    if not html_content:
        return ""

    # Strip all HTML tags using BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")
    plain_text = soup.get_text(separator=" ")

    # Normalize whitespace (collapse multiple spaces, strip leading/trailing)
    plain_text = re.sub(r'\s+', ' ', plain_text).strip()

    if len(plain_text) <= max_chars:
        return plain_text

    # Truncate at the last complete word boundary within max_chars
    truncated = plain_text[:max_chars]
    # Find last space to avoid cutting in the middle of a word
    last_space = truncated.rfind(' ')
    if last_space > 0:
        return truncated[:last_space]
    # If no space found (single very long word), return up to max_chars
    return truncated


def categorize_article(title, summary):
    """
    Categorize an article based on keyword matching in title and summary.

    Matches against predefined keyword lists for each category.
    Returns the first matching category or "general" as default.

    Args:
        title: Article title string.
        summary: Article summary string.

    Returns:
        One of: "nutrition", "training", "health", "behavior", "general".
    """
    combined = f"{title} {summary}".lower()
    tokens = set(re.split(r'[^a-z]+', combined))

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in tokens:
                return category

    return "general"


def generate_summary(text, max_chars=300):
    """
    Generate a summary from plain text, truncated at the last complete sentence
    within max_chars, or at the last word boundary if no sentence fits.

    Args:
        text: Plain text to summarize.
        max_chars: Maximum character length for the summary (default 300).

    Returns:
        Summary string of at most max_chars characters.
    """
    if not text:
        return ""

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    if len(text) <= max_chars:
        return text

    # Try to find the last complete sentence within max_chars
    truncated = text[:max_chars]

    # Look for sentence-ending punctuation followed by a space or end of string
    # Search backwards for the last sentence boundary
    sentence_end = -1
    for match in re.finditer(r'[.!?](?:\s|$)', truncated):
        sentence_end = match.end()

    if sentence_end > 0:
        return truncated[:sentence_end].strip()

    # No complete sentence fits — truncate at last word boundary
    last_space = truncated.rfind(' ')
    if last_space > 0:
        return truncated[:last_space]
    return truncated


def generate_article_id(url):
    """
    Generate a unique article ID from the canonical URL.

    Computes SHA-256 hash of the URL and returns the first 12 hex characters.

    Args:
        url: The canonical URL of the article.

    Returns:
        First 12 hex characters of the SHA-256 hash of the URL.
    """
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]

# ─────────────────────────────────────────────────────────────────────────────
# SOURCE CONFIGURATIONS — RSS feed URLs for pet care article sources
# ─────────────────────────────────────────────────────────────────────────────
SOURCES = [
    {
        "name": "ASPCA",
        "feed_url": "https://www.aspca.org/rss.xml",
        "source_id": "aspca",
    },
    {
        "name": "PetMD",
        "feed_url": "https://www.petmd.com/rss",
        "source_id": "petmd",
    },
    {
        "name": "AKC",
        "feed_url": "https://www.akc.org/feed/",
        "source_id": "akc",
    },
]

# HTTP request timeout in seconds
HTTP_TIMEOUT = 30

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Fetch articles from RSS feeds
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def fetch_articles_from_source(source_config):
    """
    Fetch and parse articles from a single RSS feed source.

    Args:
        source_config: dict with keys 'name', 'feed_url', 'source_id'

    Returns:
        List of dicts with keys: title, url, source, html_content
        On errors, logs the issue and returns partial results (skipping failed articles).
    """
    source_name = source_config["name"]
    feed_url = source_config["feed_url"]
    articles = []

    # Fetch the RSS feed
    try:
        response = requests.get(feed_url, timeout=HTTP_TIMEOUT)
        if response.status_code >= 400:
            logger.error(
                f"HTTP {response.status_code} fetching feed for {source_name}: {feed_url}"
            )
            return articles
    except requests.RequestException as e:
        logger.error(f"Network error fetching feed for {source_name}: {feed_url} — {e}")
        return articles

    # Parse the RSS/Atom feed
    feed = feedparser.parse(response.content)

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()

        if not title or not link:
            continue

        # Try to get full content from the feed entry itself
        html_content = ""
        if hasattr(entry, "content") and entry.content:
            # Atom-style content element
            html_content = entry.content[0].get("value", "")
        elif hasattr(entry, "summary") and entry.summary:
            # RSS description/summary field
            html_content = entry.summary

        # If the feed doesn't include full content, fetch the article page
        if not html_content or len(html_content) < 200:
            try:
                article_response = requests.get(link, timeout=HTTP_TIMEOUT)
                if article_response.status_code >= 400:
                    logger.error(
                        f"HTTP {article_response.status_code} fetching article for "
                        f"{source_name}: {link}"
                    )
                    continue
                html_content = article_response.text
            except requests.RequestException as e:
                logger.error(
                    f"Network error fetching article for {source_name}: {link} — {e}"
                )
                continue

        articles.append({
            "title": title,
            "url": link,
            "source": source_name,
            "html_content": html_content,
        })

    return articles


def fetch_all_articles(sources=None):
    """
    Fetch articles from all configured sources.

    Args:
        sources: list of source configs (defaults to SOURCES)

    Returns:
        Tuple of (all_articles, per_source_counts) where:
        - all_articles: List of raw article dicts with: title, url, source, html_content
        - per_source_counts: dict mapping source name → number of articles fetched
    """
    if sources is None:
        sources = SOURCES

    all_articles = []
    per_source_counts = {}
    for source_config in sources:
        print(f"  Fetching from {source_config['name']}...")
        articles = fetch_articles_from_source(source_config)
        print(f"    → {len(articles)} articles fetched")
        per_source_counts[source_config["name"]] = len(articles)
        all_articles.extend(articles)

    return all_articles, per_source_counts


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Authenticate with Google Sheets via service account
# ─────────────────────────────────────────────────────────────────────────────
def get_gspread_client():
    """Authenticate and return a gspread client using service account credentials."""
    print("[1/6] Authenticating with Google Sheets API...")

    creds_file = None

    if GOOGLE_CREDS_JSON:
        # Try parsing as JSON string first (GitHub Actions stores it as JSON string)
        try:
            creds_data = json.loads(GOOGLE_CREDS_JSON)
            with open("_temp_creds.json", "w") as f:
                json.dump(creds_data, f)
            creds_file = "_temp_creds.json"
        except (json.JSONDecodeError, TypeError):
            # If not valid JSON, treat it as a file path
            if os.path.exists(GOOGLE_CREDS_JSON):
                creds_file = GOOGLE_CREDS_JSON
            else:
                print("  ERROR: GOOGLE_CREDENTIALS_JSON is not valid JSON and file not found.")
                sys.exit(1)
    else:
        # Fall back to checking for a local service_account.json file
        if os.path.exists("service_account.json"):
            creds_file = "service_account.json"
        else:
            print("  ERROR: No Google credentials found.")
            print("  Set GOOGLE_CREDENTIALS_JSON env var to your service-account JSON string")
            print("  or place a service_account.json file in the working directory.")
            sys.exit(1)

    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds  = Credentials.from_service_account_file(creds_file, scopes=scopes)
    client = gspread.authorize(creds)

    print("  OK — authenticated with Google Sheets")
    return client


def cleanup_temp_creds():
    """Remove temporary credentials file if it was created."""
    if os.path.exists("_temp_creds.json"):
        os.remove("_temp_creds.json")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Deduplication and Google Sheets write logic
# ─────────────────────────────────────────────────────────────────────────────

def get_or_create_worksheet(spreadsheet):
    """
    Get the pet_care_kb worksheet from the spreadsheet, or create it with
    the correct header row if it doesn't exist.

    Args:
        spreadsheet: An open gspread Spreadsheet object.

    Returns:
        gspread Worksheet for the pet_care_kb tab.
    """
    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=WORKSHEET_NAME, rows=1, cols=len(COLUMNS)
        )
        worksheet.append_row(COLUMNS, value_input_option="RAW")
    return worksheet


def get_existing_article_ids(worksheet):
    """
    Read all existing articleId values from column A of the worksheet.

    Skips the header row and returns a set of all articleId strings currently
    stored in the knowledge base.

    Args:
        worksheet: gspread Worksheet object for pet_care_kb.

    Returns:
        Set of articleId strings already present in the sheet.
    """
    # Get all values in column A (articleId column)
    col_values = worksheet.col_values(1)
    # Skip the header row (index 0) and filter out empty strings
    existing_ids = set(val for val in col_values[1:] if val)
    return existing_ids


def enforce_row_cap(worksheet, max_rows=500):
    """
    Enforce a maximum row cap on the knowledge base worksheet.

    If the total number of data rows (excluding header) exceeds max_rows,
    deletes the rows with the lowest (oldest) `fetchedAt` values until
    the total is at or below max_rows.

    Args:
        worksheet: gspread Worksheet object for pet_care_kb.
        max_rows: Maximum allowed data rows (default 500).

    Returns:
        Number of rows pruned (deleted).
    """
    # Get all values from the worksheet (includes header row)
    all_values = worksheet.get_all_values()

    # First row is header; data rows start at index 1
    data_rows = all_values[1:]
    total_rows = len(data_rows)

    if total_rows <= max_rows:
        return 0

    rows_to_prune = total_rows - max_rows

    # fetchedAt is column index 8 (0-based) — the 9th column
    FETCHED_AT_COL = 8

    # Build list of (row_index_in_sheet, fetchedAt_value) for all data rows
    # Sheet rows are 1-based, and header is row 1, so data starts at row 2
    indexed_rows = []
    for i, row in enumerate(data_rows):
        fetched_at = row[FETCHED_AT_COL] if len(row) > FETCHED_AT_COL else ""
        sheet_row_index = i + 2  # +2 because: +1 for 0-based→1-based, +1 for header
        indexed_rows.append((sheet_row_index, fetched_at))

    # Sort by fetchedAt ascending (oldest first) to identify rows to delete
    indexed_rows.sort(key=lambda x: x[1])

    # Take the oldest rows_to_prune rows
    rows_to_delete = indexed_rows[:rows_to_prune]

    # Sort by row index descending so we delete from bottom to top
    # This avoids index shifting issues
    rows_to_delete.sort(key=lambda x: x[0], reverse=True)

    # Delete rows one by one from bottom to top
    for row_index, _ in rows_to_delete:
        worksheet.delete_rows(row_index)

    return rows_to_prune


def write_new_articles(worksheet, articles, existing_ids):
    """
    Filter out duplicate articles and write new ones to the worksheet.

    Compares each article's articleId against existing_ids and skips duplicates.
    Appends new articles as rows matching the schema column order.

    Args:
        worksheet: gspread Worksheet object for pet_care_kb.
        articles: List of transformed article dicts.
        existing_ids: Set of articleId strings already in the sheet.

    Returns:
        Tuple of (new_count, duplicate_count) indicating how many articles
        were written and how many were skipped as duplicates.
    """
    new_rows = []
    duplicate_count = 0

    for article in articles:
        if article["articleId"] in existing_ids:
            duplicate_count += 1
            continue
        # Build row in the correct column order
        row = [
            article["articleId"],
            article["title"],
            article["url"],
            article["source"],
            article["category"],
            article["summary"],
            article["keywords"],
            article["fullText"],
            article["fetchedAt"],
        ]
        new_rows.append(row)
        # Track the ID so we don't write duplicates within the same batch
        existing_ids.add(article["articleId"])

    new_count = len(new_rows)

    if new_rows and not DRY_RUN:
        worksheet.append_rows(new_rows, value_input_option="RAW")

    return new_count, duplicate_count


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    start = time.time()

    print("=" * 60)
    print("  Furever Home — Pet Care FAQ KB Sync")
    print(f"  Mode: {'DRY RUN' if DRY_RUN else 'LIVE'}")
    print(f"  Time: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print("=" * 60)

    try:
        client = get_gspread_client()

        # Task 1.2 — Fetch articles from RSS feeds
        print("\n[2/6] Fetching articles from RSS feeds...")
        raw_articles, per_source_counts = fetch_all_articles()
        print(f"  Total raw articles fetched: {len(raw_articles)}")

        # Task 1.3 — Transform articles and extract fields
        print("\n[3/6] Transforming articles...")
        transformed_articles = []
        for raw in raw_articles:
            plain_text = truncate_text(raw["html_content"], max_chars=1500)
            summary = generate_summary(plain_text, max_chars=300)
            article = {
                "articleId": generate_article_id(raw["url"]),
                "title": raw["title"],
                "url": raw["url"],
                "source": raw["source"],
                "category": categorize_article(raw["title"], summary),
                "summary": summary,
                "keywords": extract_keywords(raw["title"], summary),
                "fullText": plain_text,
                "fetchedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            transformed_articles.append(article)
        print(f"  Transformed {len(transformed_articles)} articles")

        # Task 1.6 — Deduplication and Google Sheets write
        print("\n[4/6] Writing to Google Sheets...")
        spreadsheet = client.open_by_key(SHEET_ID)
        worksheet = get_or_create_worksheet(spreadsheet)
        existing_ids = get_existing_article_ids(worksheet)
        print(f"  Existing articles in sheet: {len(existing_ids)}")

        if DRY_RUN:
            # In dry-run mode, compute what would be written but skip actual write
            new_count = 0
            duplicate_count = 0
            for article in transformed_articles:
                if article["articleId"] in existing_ids:
                    duplicate_count += 1
                else:
                    new_count += 1
                    existing_ids.add(article["articleId"])
            print(f"  [DRY RUN] Would write {new_count} new articles, skip {duplicate_count} duplicates")

            # Print each article to stdout so user can inspect what would be written
            print("\n  --- Fetched Articles (DRY RUN) ---")
            for article in transformed_articles:
                print(f"  • {article['title']}")
                print(f"    URL:      {article['url']}")
                print(f"    Source:   {article['source']}")
                print(f"    Category: {article['category']}")
                print()
        else:
            new_count, duplicate_count = write_new_articles(
                worksheet, transformed_articles, existing_ids
            )
            print(f"  Written {new_count} new articles, skipped {duplicate_count} duplicates")

        # Task 1.8 — Row cap enforcement (prune to 500 rows)
        print("\n[5/6] Enforcing row cap...")
        pruned = 0
        if DRY_RUN:
            # In dry-run mode, estimate how many rows would be pruned
            all_values = worksheet.get_all_values()
            current_total = len(all_values) - 1  # Exclude header
            if current_total > MAX_ROWS:
                pruned = current_total - MAX_ROWS
                print(f"  [DRY RUN] Would prune {pruned} oldest rows (current: {current_total}, cap: {MAX_ROWS})")
            else:
                print(f"  [DRY RUN] No pruning needed (current: {current_total}, cap: {MAX_ROWS})")
        else:
            pruned = enforce_row_cap(worksheet, max_rows=MAX_ROWS)
            if pruned > 0:
                print(f"  Pruned {pruned} oldest rows to enforce {MAX_ROWS}-row cap")
            else:
                print(f"  No pruning needed (within {MAX_ROWS}-row cap)")

        # Task 1.10 — Run summary output
        elapsed = round(time.time() - start, 1)
        source_breakdown = ", ".join(
            f"{name}: {count}" for name, count in per_source_counts.items()
        )
        print("\n[6/6] Done!")
        print("═══════════════════════════════════════════════════════════")
        print("  SUMMARY")
        print(f"  Articles fetched: {len(raw_articles)} ({source_breakdown})")
        print(f"  New articles written: {new_count}")
        print(f"  Duplicates skipped: {duplicate_count}")
        print(f"  Rows pruned: {pruned}")
        print(f"  Total time: {elapsed}s")
        print("═══════════════════════════════════════════════════════════")

    finally:
        cleanup_temp_creds()

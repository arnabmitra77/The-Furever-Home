"""
Furever Home â€” Petfinder â†’ Google Sheets Nightly Sync
======================================================
Fetches live available dogs and cats from Bay Area shelters
via the Petfinder API and writes them to your Google Sheet.

REQUIRED SETUP (one-time, see README_CRON.md):
  1. PETFINDER_API_KEY   â€” from petfinder.com/developers
  2. PETFINDER_SECRET    â€” from petfinder.com/developers
  3. GOOGLE_CREDENTIALS  â€” path to your service-account JSON file
  4. SHEET_ID            â€” your Google Sheet ID

Run locally : python petfinder_sync.py
Run on GitHub Actions : see .github/workflows/nightly_sync.yml
"""

import os
import sys
import json
import time
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CONFIGURATION â€” set these as environment variables or edit directly for
# local testing (never commit real keys to GitHub)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
PETFINDER_API_KEY  = os.environ.get("PETFINDER_API_KEY",  "YOUR_KEY_HERE")
PETFINDER_SECRET   = os.environ.get("PETFINDER_SECRET",   "YOUR_SECRET_HERE")
GOOGLE_CREDS_JSON  = os.environ.get("GOOGLE_CREDENTIALS", "service_account.json")
SHEET_ID           = os.environ.get("SHEET_ID", "1Xg4T3vmhoLxN0C2lEBFaN88Y2LSvoF6DQVoCxL3dt80")

# Bay Area locations to search (city, state pairs)
LOCATIONS = [
    ("Pleasanton", "CA"),
    ("Oakland",    "CA"),
    ("Milpitas",   "CA"),
    ("Fremont",    "CA"),
    ("San Jose",   "CA"),
]

# Distance in miles from each location
DISTANCE = 10

# Max pets to fetch per location per type (Petfinder max is 100 per page)
LIMIT_PER_CALL = 100

# Google Sheet worksheet name
WORKSHEET_NAME = "Sheet1"

# Required sheet columns in order
COLUMNS = [
    "petId", "petName", "species", "breed", "age", "weight",
    "location", "price", "match", "tags", "imageUrl",
    "shelterName", "shelterPhone", "shelterUrl", "story",
    "gender", "energy", "size", "available", "lastUpdated"
]

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 1 â€” Get Petfinder OAuth2 token (expires in 3600s)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def get_petfinder_token():
    print("[1/5] Authenticating with Petfinder API...")
    resp = requests.post(
        "https://api.petfinder.com/v2/oauth2/token",
        data={
            "grant_type":    "client_credentials",
            "client_id":     PETFINDER_API_KEY,
            "client_secret": PETFINDER_SECRET,
        },
        timeout=15
    )
    if resp.status_code != 200:
        print(f"  ERROR: Auth failed â€” {resp.status_code} {resp.text}")
        sys.exit(1)
    token = resp.json()["access_token"]
    print(f"  OK â€” token acquired")
    return token

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 2 â€” Fetch pets from Petfinder for all locations
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def fetch_pets(token):
    print("[2/5] Fetching pets from Petfinder...")
    headers = {"Authorization": f"Bearer {token}"}
    all_pets = {}  # keyed by petfinder ID to deduplicate across locations

    for animal_type in ["dog", "cat"]:
        for city, state in LOCATIONS:
            location = f"{city}, {state}"
            params = {
                "type":     animal_type,
                "location": location,
                "distance": DISTANCE,
                "limit":    LIMIT_PER_CALL,
                "status":   "adoptable",
                "page":     1,
            }
            try:
                resp = requests.get(
                    "https://api.petfinder.com/v2/animals",
                    headers=headers,
                    params=params,
                    timeout=15
                )
                if resp.status_code == 200:
                    animals = resp.json().get("animals", [])
                    for a in animals:
                        all_pets[a["id"]] = a
                    print(f"  {animal_type.upper():4} @ {location:20} â†’ {len(animals)} pets")
                else:
                    print(f"  WARN: {animal_type} @ {location} â†’ HTTP {resp.status_code}")
                time.sleep(0.3)  # respect rate limits
            except Exception as e:
                print(f"  WARN: {location} fetch error â€” {e}")

    print(f"  Total unique pets fetched: {len(all_pets)}")
    return list(all_pets.values())

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 3 â€” Transform Petfinder animal object â†’ sheet row
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def transform_pet(animal, idx):
    """Map Petfinder API fields to our sheet columns."""

    # Name & species
    pet_id  = str(animal.get("id", idx))
    name    = animal.get("name", "Unknown").strip().title()
    species = animal.get("species", "").lower()

    # Breed
    breeds = animal.get("breeds", {})
    breed  = breeds.get("primary", "") or ""
    if breeds.get("secondary"):
        breed += " Mix"

    # Age mapping: baby/young/adult/senior
    age_raw = animal.get("age", "").lower()
    age_map = {"baby": "Kitten" if species == "cat" else "Puppy",
               "young": "Young", "adult": "Adult", "senior": "Senior"}
    age = age_map.get(age_raw, age_raw.title())

    # Size
    size_raw = (animal.get("size") or "").lower()
    size_map = {"small": "small", "medium": "medium",
                "large": "large", "xlarge": "large"}
    size = size_map.get(size_raw, "medium")

    # Weight â€” Petfinder doesn't provide weight directly, estimate from size
    weight_map = {"small": "Under 25 lbs", "medium": "25â€“50 lbs",
                  "large": "50+ lbs"}
    weight = weight_map.get(size, "")

    # Location
    contact = animal.get("contact", {})
    addr    = contact.get("address", {})
    city    = addr.get("city", "") or ""
    state   = addr.get("state", "") or ""
    location = f"{city}, {state}".strip(", ")

    # Price â€” shelters set their own fees; Petfinder doesn't expose this
    # Use a sensible default based on species and age
    if species == "cat":
        price = "75" if age_raw == "senior" else "100" if age_raw == "adult" else "125"
    else:
        price = "200" if age_raw == "senior" else "250" if age_raw == "adult" else "350"

    # Match % â€” not real AI, placeholder for display
    match = ""

    # Tags from attributes
    attrs  = animal.get("attributes", {})
    colors = animal.get("colors", {})
    tag_list = []
    if attrs.get("spayed_neutered"):   tag_list.append("Fixed")
    if attrs.get("house_trained"):     tag_list.append("House-trained")
    if attrs.get("special_needs"):     tag_list.append("Special Needs")
    if age_raw == "baby":              tag_list.append("Puppy" if species == "dog" else "Kitten")
    if age_raw == "senior":            tag_list.append("Senior")
    env = animal.get("environment", {})
    if env.get("children"):            tag_list.append("Good with kids")
    if env.get("dogs"):                tag_list.append("Good with dogs")
    if env.get("cats"):                tag_list.append("Good with cats")
    tags = ",".join(tag_list[:4])  # cap at 4 tags

    # Photo â€” first photo medium size
    photos  = animal.get("photos", [])
    img_url = ""
    if photos:
        img_url = photos[0].get("medium") or photos[0].get("large") or photos[0].get("full") or ""

    # Shelter info
    org_id   = animal.get("organization_id", "")
    shelter  = animal.get("organization", {}).get("name", "") if "organization" in animal else ""
    # Petfinder /animals doesn't embed org name â€” use org_id as placeholder
    if not shelter:
        shelter = org_id
    phone    = contact.get("phone", "") or ""
    shelter_url = f"https://www.petfinder.com/pet-details/{pet_id}"

    # Story / description
    story = (animal.get("description") or "").strip()
    story = story[:300] + ("..." if len(story) > 300 else "")  # truncate

    # Gender
    gender = animal.get("gender", "").title()

    # Energy â€” map from Petfinder coat/size/age heuristic (no direct field)
    energy = "High" if age_raw in ("baby", "young") else "Medium" if age_raw == "adult" else "Low"

    now = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M UTC")

    return {
        "petId":        pet_id,
        "petName":      name,
        "species":      species,
        "breed":        breed,
        "age":          age,
        "weight":       weight,
        "location":     location,
        "price":        price,
        "match":        match,
        "tags":         tags,
        "imageUrl":     img_url,
        "shelterName":  shelter,
        "shelterPhone": phone,
        "shelterUrl":   shelter_url,
        "story":        story,
        "gender":       gender,
        "energy":       energy,
        "size":         size,
        "available":    "yes",
        "lastUpdated":  now,
    }

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 4 â€” Connect to Google Sheets and write data
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def write_to_sheet(rows):
    print("[4/5] Connecting to Google Sheets...")

    # Load credentials
    if not os.path.exists(GOOGLE_CREDS_JSON):
        # Try parsing from env var (GitHub Actions stores it as JSON string)
        creds_env = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
        if creds_env:
            with open("_temp_creds.json", "w") as f:
                f.write(creds_env)
            creds_file = "_temp_creds.json"
        else:
            print("  ERROR: No Google credentials found.")
            print("  Set GOOGLE_CREDENTIALS env var to path of service-account.json")
            sys.exit(1)
    else:
        creds_file = GOOGLE_CREDS_JSON

    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds  = Credentials.from_service_account_file(creds_file, scopes=scopes)
    client = gspread.authorize(creds)

    # Open sheet
    sheet     = client.open_by_key(SHEET_ID)
    worksheet = sheet.worksheet(WORKSHEET_NAME)
    print(f"  OK â€” connected to sheet: {sheet.title}")

    # Clear existing data and write fresh
    worksheet.clear()
    print(f"  Cleared old data")

    # Write header row
    worksheet.append_row(COLUMNS)

    # Write all pet rows
    data_rows = [[row.get(col, "") for col in COLUMNS] for row in rows]
    if data_rows:
        worksheet.append_rows(data_rows, value_input_option="USER_ENTERED")

    print(f"  Written: {len(data_rows)} pets to sheet")

    # Cleanup temp creds
    if os.path.exists("_temp_creds.json"):
        os.remove("_temp_creds.json")

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 5 â€” Run summary
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def print_summary(rows, start_time):
    elapsed = round(time.time() - start_time, 1)
    dogs = sum(1 for r in rows if r["species"] == "dog")
    cats = sum(1 for r in rows if r["species"] == "cat")
    print("[5/5] Sync complete!")
    print(f"  Dogs: {dogs}")
    print(f"  Cats: {cats}")
    print(f"  Total: {len(rows)}")
    print(f"  Time:  {elapsed}s")
    print(f"  Ran at: {datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M UTC')}")

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# DRY RUN MODE â€” tests everything except writing to sheet
# Usage: python petfinder_sync.py --dry-run
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def dry_run(token):
    print("\n=== DRY RUN MODE (no sheet write) ===")
    animals = fetch_pets(token)
    rows = [transform_pet(a, i) for i, a in enumerate(animals)]
    dogs = sum(1 for r in rows if r["species"] == "dog")
    cats = sum(1 for r in rows if r["species"] == "cat")
    print(f"\nSample record (first pet):")
    if rows:
        for k, v in list(rows[0].items())[:10]:
            print(f"  {k:15} : {v}")
    print(f"\nTotal: {len(rows)} pets ({dogs} dogs, {cats} cats)")
    print("Dry run complete â€” no data was written to sheet.")
    return rows

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MAIN
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    start = time.time()
    is_dry = "--dry-run" in sys.argv

    print("=" * 60)
    print("  Furever Home â€” Petfinder Nightly Sync")
    print(f"  Mode: {'DRY RUN' if is_dry else 'LIVE'}")
    print(f"  Time: {datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # Validate config
    if PETFINDER_API_KEY == "YOUR_KEY_HERE":
        print("\nERROR: PETFINDER_API_KEY not set.")
        print("Get your free key at: https://www.petfinder.com/developers/")
        print("Then set: $env:PETFINDER_API_KEY = 'your_key'")
        print("      and: $env:PETFINDER_SECRET  = 'your_secret'")
        sys.exit(1)

    token = get_petfinder_token()

    if is_dry:
        dry_run(token)
    else:
        print("[3/5] Transforming pet data...")
        animals = fetch_pets(token)
        rows    = [transform_pet(a, i) for i, a in enumerate(animals)]
        print(f"  Transformed {len(rows)} pets")
        write_to_sheet(rows)
        print_summary(rows, start)



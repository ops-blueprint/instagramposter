#!/usr/bin/env python3
"""Fetch real 'On This Day' history facts from Wikipedia's free public API.

No API key required. Endpoint docs:
https://en.wikipedia.org/api/rest_v1/#/Feed/get_feed_onthisday_type_month_day
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
USED_LOG = BASE_DIR / "used_facts.json"

WIKI_API = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/{month:02d}/{day:02d}"

REGION_KEYWORDS = {
    "USA": ["united states", "america", "u.s.", "washington", "new york", "california", "president"],
    "UK": ["united kingdom", "britain", "england", "scotland", "wales", "london"],
    "Australia": ["australia", "sydney", "melbourne", "canberra"],
    "Europe": ["france", "germany", "italy", "spain", "europe", "european", "russia",
               "netherlands", "poland", "greece", "rome", "berlin", "paris"],
}

REGION_FLAG = {"USA": "🇺🇸", "UK": "🇬🇧", "Australia": "🇦🇺", "Europe": "🇪🇺", "World": "🌍"}

# Skipped entirely in unattended runs -- real "on this day" history includes assassinations,
# mass-casualty violence, and sexual violence, which are a brand/backlash risk to auto-post
# with zero human review. Ordinary historical conflict/war facts are NOT filtered.
# Used by default for general-audience pipelines (NatureWonders9, Instagram is separate).
SENSITIVE_KEYWORDS = [
    "assassinat", "mass shooting", "school shooting", "terrorist attack", "suicide bomb",
    "genocide", "massacre", "rape", "sexual assault", "mass murder", "beheading", "lynching",
    "holocaust", "auschwitz", "concentration camp", "deportation", "ethnic cleansing",
    "war crime", "torture", "gas chamber", "pogrom",
]

# A much shorter, non-negotiable floor -- sexual violence content stays off-limits
# regardless of a page's niche/brand (e.g. a "dark facts" account can cover
# assassinations/massacres/genocide as historical education, but not this).
HARD_FLOOR_KEYWORDS = ["rape", "sexual assault", "molestation", "child abuse", "pedophil"]


def is_sensitive(text, keywords=None):
    lowered = text.lower()
    return any(kw in lowered for kw in (keywords or SENSITIVE_KEYWORDS))


def load_used():
    if USED_LOG.exists():
        return set(json.loads(USED_LOG.read_text()))
    return set()


def save_used(used):
    USED_LOG.write_text(json.dumps(sorted(used), indent=2))


def tag_region(text):
    lowered = text.lower()
    for region, keywords in REGION_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return region
    return "World"


def fetch_events(month, day):
    url = WIKI_API.format(month=month, day=day)
    headers = {"User-Agent": "FactsAutomation/1.0 (personal content project)"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json().get("events", [])


def pick_facts(events, count, used, skip_sensitive=True, sensitive_keywords=None):
    scored = []
    for e in events:
        text = e.get("text", "").strip()
        if not text:
            continue
        key = text[:80]
        if key in used:
            continue
        if skip_sensitive and is_sensitive(text, sensitive_keywords):
            continue
        region = tag_region(text)
        year = e.get("year")
        scored.append((region != "World", year or 0, region, year, text))
    # Prefer regionally-tagged facts, then more recent years, for variety and relatability
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    picked = []
    seen_regions = {}
    for is_regional, _, region, year, text in scored:
        if len(picked) >= count:
            break
        # spread facts across regions instead of dumping 5 USA facts in a row
        if seen_regions.get(region, 0) >= 2 and len(picked) < count - 1:
            continue
        picked.append({"region": region, "flag": REGION_FLAG[region], "year": year, "text": text})
        seen_regions[region] = seen_regions.get(region, 0) + 1

    # top up if the region cap left us short
    if len(picked) < count:
        for is_regional, _, region, year, text in scored:
            if len(picked) >= count:
                break
            if any(p["text"] == text for p in picked):
                continue
            picked.append({"region": region, "flag": REGION_FLAG[region], "year": year, "text": text})

    return picked


def main():
    parser = argparse.ArgumentParser(description="Fetch history facts for a given day (defaults to today)")
    parser.add_argument("--date", help="MM-DD, defaults to today")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--out", default=str(BASE_DIR / "facts_today.json"))
    args = parser.parse_args()

    if args.date:
        month, day = map(int, args.date.split("-"))
    else:
        today = datetime.date.today()
        month, day = today.month, today.day

    events = fetch_events(month, day)
    used = load_used()
    facts = pick_facts(events, args.count, used)

    if not facts:
        print("No new facts found (all recent facts for this date already used, or API returned nothing).",
              file=sys.stderr)
        sys.exit(1)

    for f in facts:
        used.add(f["text"][:80])
    save_used(used)

    Path(args.out).write_text(json.dumps(facts, indent=2))
    print(f"Saved {len(facts)} facts to {args.out}")
    for f in facts:
        print(f"  {f['flag']} [{f['region']}] {f['year']}: {f['text'][:90]}")


if __name__ == "__main__":
    main()

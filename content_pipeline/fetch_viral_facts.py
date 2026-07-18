#!/usr/bin/env python3
"""Fetch what's genuinely popular right now, via Wikipedia's free Pageviews API.

This substitutes for Reddit "most engaged" content, since Reddit ended
self-serve developer API access in 2026 (new apps can no longer be created
without manual staff approval). Wikipedia's pageview counts are arguably a
stronger "what people actually care about today" signal anyway -- it reflects
real search/reading interest across everyone, not one platform's voting game.

No API key required:
https://wikimedia.org/api/rest_v1/#/Pageviews%20data/get_metrics_pageviews_top_project_access_year_month_day
"""
import datetime
import re
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from fetch_facts import is_sensitive  # reuse the same sensitive-content filter

TOP_API = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{year}/{month:02d}/{day:02d}"
SUMMARY_API = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

# Wikipedia namespace/meta pages that show up in top-pageviews but aren't real topics
SKIP_PREFIXES = ("Special:", "Wikipedia:", "Portal:", "Talk:", "User:", "File:", "Category:", "Help:", "Main_Page")

VIRAL_FLAG = "🔥"


def fetch_top_articles(date, limit=30):
    headers = {"User-Agent": "FactsAutomation/1.0 (personal content project)"}
    url = TOP_API.format(year=date.year, month=date.month, day=date.day)
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    articles = resp.json()["items"][0]["articles"]
    return [a["article"] for a in articles if not a["article"].startswith(SKIP_PREFIXES)][:limit]


def fetch_summary(title):
    headers = {"User-Agent": "FactsAutomation/1.0 (personal content project)"}
    url = SUMMARY_API.format(title=title)
    resp = requests.get(url, headers=headers, timeout=15)
    if not resp.ok:
        return None
    return resp.json().get("extract", "").strip()


def first_sentence(text):
    match = re.search(r".+?[.!?](?:\s|$)", text)
    return match.group(0).strip() if match else text


def pick_viral_facts(count, used, date=None, max_attempts=15, sensitive_keywords=None):
    date = date or (datetime.date.today() - datetime.timedelta(days=1))
    try:
        titles = fetch_top_articles(date)
    except requests.RequestException:
        return []

    picked = []
    for title in titles:
        if len(picked) >= count or max_attempts <= 0:
            break
        max_attempts -= 1

        extract = fetch_summary(title)
        if not extract:
            continue
        sentence = first_sentence(extract)
        if len(sentence) < 25:
            continue

        display_title = title.replace("_", " ")
        text = f"Right now, people are searching for {display_title} on Wikipedia. Here's why: {sentence}"

        key = text[:80]
        if key in used or is_sensitive(text, sensitive_keywords):
            continue

        picked.append({
            "region": "Viral",
            "flag": VIRAL_FLAG,
            "year": None,
            "text": text,
            "eyebrow_suffix": "TRENDING NOW",
        })

    return picked

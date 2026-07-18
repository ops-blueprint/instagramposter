#!/usr/bin/env python3
"""Fetch general 'interesting facts' (any topic) from a free, no-key public API.

Complements fetch_facts.py's date-anchored history facts with broader,
audience-interest content -- science, nature, human body, records, etc.
No API key required: https://uselessfacts.jsph.pl/
"""
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from fetch_facts import is_sensitive  # reuse the same sensitive-content filter

FACTS_API = "https://uselessfacts.jsph.pl/api/v2/facts/random?language=en"

TRENDING_FLAG = "💡"


def fetch_one():
    headers = {"User-Agent": "FactsAutomation/1.0 (personal content project)"}
    resp = requests.get(FACTS_API, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def pick_trending_facts(count, used, max_attempts=30, sensitive_keywords=None):
    picked = []
    attempts = 0
    while len(picked) < count and attempts < max_attempts:
        attempts += 1
        try:
            data = fetch_one()
        except requests.RequestException:
            continue
        text = (data.get("text") or "").strip()
        if not text:
            continue
        key = text[:80]
        if key in used or any(p["text"][:80] == key for p in picked):
            continue
        if is_sensitive(text, sensitive_keywords):
            continue
        picked.append({
            "region": "Trending",
            "flag": TRENDING_FLAG,
            "year": None,
            "text": text,
            "eyebrow_suffix": "DID YOU KNOW",
        })
    return picked

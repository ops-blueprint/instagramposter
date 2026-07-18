#!/usr/bin/env python3
"""Generate one fresh fact card and post it to Instagram via the Graph API.

Own standalone repo on purpose -- fully separate from the Facebook Page
automation (which lives in the facebookposter repo): own dedupe log
(content_pipeline/used_facts_instagram.json), own credentials (IG_USER_ID /
IG_ACCESS_TOKEN), own git history. Nothing here can break or race against
the Facebook scheduling pipeline.

Unlike Facebook Pages, Instagram's Content Publishing API has NO native
scheduled_publish_time -- posting must happen live, at trigger time, via
GitHub Actions cron (best-effort timing, same caveat as Facebook's old
live-cron setup: can drift by hours, not exact).

Instagram also requires a *public URL* for the image (it fetches it itself --
no direct file upload like Facebook's /photos endpoint). Since this repo is
public, we commit the rendered card and reference its raw.githubusercontent.com
URL. Ordinary content publish rate limit is far above what we use (2/day vs a
25/day cap), so no throttling concern.

Setup required (see README.md):
  1. An Instagram Business account (@curseorcure3), linked to the Meme Vault
     USA Facebook Page
  2. instagram_basic + instagram_content_publish permissions added to the Meta app
  3. IG_USER_ID (the linked Instagram account's numeric ID) and an access token
     with those permissions, saved as IG_ACCESS_TOKEN
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "content_pipeline"))

import requests
from dotenv import load_dotenv

import fetch_facts
import fetch_trending_facts
import fetch_viral_facts
import make_cards

GRAPH_API_VERSION = "v20.0"
DEDUPE_LOG = BASE_DIR / "content_pipeline" / "used_facts_instagram.json"
REPO_SLUG = "ops-blueprint/instagramposter"  # for building the raw.githubusercontent.com URL
IMAGE_REPO_PATH = "content_pipeline/output/instagram"

SOURCE_WEIGHTS = {"viral": 0.45, "trending": 0.30, "history": 0.25}

# @curseorcure3's own brand is "dark facts" -- assassinations/massacres/genocide etc.
# are the appeal here, not a risk to filter out like on the general-audience pages.
# Only the hard floor (sexual violence) still applies, regardless of niche.
DARK_FACTS_KEYWORDS = fetch_facts.HARD_FLOOR_KEYWORDS

DARK_HOOKS = [
    "The dark truth behind this one 🕯️",
    "They don't teach you this in school.",
    "A twisted story most people never hear.",
    "This one will stay with you.",
    "Dark fact of the day 🖤",
]

DARK_QUESTIONS = [
    "Did you know this one? Tell us below.",
    "Could you handle knowing the full story?",
    "Save this if it gave you chills.",
    "Follow for more dark facts they don't teach you.",
    "What's the darkest fact YOU know?",
]

DARK_HASHTAGS = ["#DarkFacts", "#DarkHistory", "#TwistedTruths", "#DidYouKnow", "#CurseOrCure"]


def build_dark_caption(fact, index):
    hook = DARK_HOOKS[index % len(DARK_HOOKS)]
    question = DARK_QUESTIONS[index % len(DARK_QUESTIONS)]
    prefix = f"{fact['year']}: " if fact.get("year") else ""
    return f"{hook}\n\n🖤 {prefix}{fact['text']}\n\n{question}\n\n{' '.join(DARK_HASHTAGS)}"


def load_dedupe():
    if DEDUPE_LOG.exists():
        return set(json.loads(DEDUPE_LOG.read_text()))
    return set()


def save_dedupe(used):
    DEDUPE_LOG.write_text(json.dumps(sorted(used), indent=2))


def get_one_fact(used):
    import random
    today = datetime.date.today()
    remaining = list(SOURCE_WEIGHTS.items())
    order = []
    while remaining:
        names, weights = zip(*remaining)
        pick = random.choices(names, weights=weights, k=1)[0]
        order.append(pick)
        remaining = [(n, w) for n, w in remaining if n != pick]

    for source in order:
        if source == "viral":
            facts = fetch_viral_facts.pick_viral_facts(count=1, used=used, sensitive_keywords=DARK_FACTS_KEYWORDS)
        elif source == "trending":
            facts = fetch_trending_facts.pick_trending_facts(count=1, used=used, sensitive_keywords=DARK_FACTS_KEYWORDS)
        else:
            events = fetch_facts.fetch_events(today.month, today.day)
            facts = fetch_facts.pick_facts(events, count=1, used=used, sensitive_keywords=DARK_FACTS_KEYWORDS)
        if facts:
            return facts[0]
    return None


def commit_and_push_image(image_path: Path, dry_run: bool):
    """Commit just this one image file so it gets a stable public raw URL.
    Isolated to this file only -- never touches used_facts.json or the
    scheduled_slots_*.json files the Facebook workflows own."""
    if dry_run:
        return f"https://raw.githubusercontent.com/{REPO_SLUG}/main/{IMAGE_REPO_PATH}/{image_path.name}"

    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=BASE_DIR, check=True)
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"],
                    cwd=BASE_DIR, check=True)
    subprocess.run(["git", "add", str(image_path.relative_to(BASE_DIR))], cwd=BASE_DIR, check=True)
    subprocess.run(["git", "commit", "-m", f"Add Instagram post image {image_path.name} [skip ci]"],
                    cwd=BASE_DIR, check=True)

    for attempt in range(5):
        push = subprocess.run(["git", "push"], cwd=BASE_DIR, capture_output=True, text=True)
        if push.returncode == 0:
            break
        print(f"Push rejected (attempt {attempt + 1}) -- rebasing and retrying...")
        time.sleep(5 + attempt * 3)
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=BASE_DIR, check=True)
    else:
        raise RuntimeError("Failed to push image after 5 attempts")

    # brief wait for raw.githubusercontent.com's CDN to pick up the new commit
    time.sleep(5)
    return f"https://raw.githubusercontent.com/{REPO_SLUG}/main/{IMAGE_REPO_PATH}/{image_path.name}"


def publish_to_instagram(ig_user_id, access_token, image_url, caption, dry_run=False):
    base = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ig_user_id}"

    if dry_run:
        print(f"[dry-run] Would create IG media container: image_url={image_url}")
        return {"dry_run": True}

    create = requests.post(f"{base}/media", data={
        "image_url": image_url, "caption": caption, "access_token": access_token,
    }, timeout=60)
    if not create.ok:
        raise RuntimeError(f"IG media container creation failed: {create.status_code} {create.text}")
    creation_id = create.json()["id"]

    for _ in range(20):  # poll up to ~60s for Instagram's async processing
        status = requests.get(f"https://graph.facebook.com/{GRAPH_API_VERSION}/{creation_id}",
                               params={"fields": "status_code", "access_token": access_token}, timeout=30)
        code = status.json().get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"IG container processing failed: {status.json()}")
        time.sleep(3)
    else:
        raise RuntimeError("IG container never finished processing (timed out after ~60s)")

    publish = requests.post(f"{base}/media_publish", data={
        "creation_id": creation_id, "access_token": access_token,
    }, timeout=60)
    if not publish.ok:
        raise RuntimeError(f"IG publish failed: {publish.status_code} {publish.text}")
    return publish.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv(BASE_DIR / ".env")

    used = load_dedupe()
    fact = get_one_fact(used)
    if not fact:
        print("No new facts available right now -- skipping this run.")
        return
    used.add(fact["text"][:80])

    out_dir = BASE_DIR / IMAGE_REPO_PATH
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = out_dir / f"post_{stamp}.png"
    make_cards.make_card(fact, image_path, page_handle="@curseorcure3")

    caption = build_dark_caption(fact, index=hash(fact["text"]) % 5)

    image_url = commit_and_push_image(image_path, args.dry_run)

    ig_user_id = os.environ.get("IG_USER_ID")
    ig_token = os.environ.get("IG_ACCESS_TOKEN")
    if not args.dry_run and (not ig_user_id or not ig_token):
        print("Missing IG_USER_ID / IG_ACCESS_TOKEN in .env", file=sys.stderr)
        sys.exit(1)

    result = publish_to_instagram(ig_user_id, ig_token, image_url, caption, dry_run=args.dry_run)
    label = f"{fact['region']}, {fact['year']}" if fact.get("year") else fact["region"]
    print(f"{'[dry-run] Would post' if args.dry_run else 'Posted'} to Instagram ({label}): {result}")

    if not args.dry_run:
        save_dedupe(used)


if __name__ == "__main__":
    main()

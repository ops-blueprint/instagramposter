# Instagram auto-poster (@curseorcure3)

Free, automated fact-card posting to Instagram — pulls a mixed feed of
genuinely popular content (Wikipedia Pageviews), general "anything
interesting" facts, and date-anchored history facts, rendered into branded
cards, with dark-facts-toned captions matching this account's own brand.

Standalone repo on purpose: fully separate from the Facebook Page automation
(a different project) so nothing here can interfere with it.

## One-time setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in IG_USER_ID and IG_ACCESS_TOKEN
```

## Test locally

```bash
python3 auto_post_instagram.py --dry-run
```

## Go live

Add `IG_USER_ID` and `IG_ACCESS_TOKEN` as repo secrets (Settings → Secrets
and variables → Actions), then the workflow in
`.github/workflows/auto_post_instagram.yml` posts automatically at 9am/9pm
IST daily (best-effort timing — Instagram's API has no native scheduling
like Facebook Pages do, so this runs live via GitHub Actions cron).

## Why a public image URL trick

Instagram's Content Publishing API requires a public URL for the image (it
fetches it itself — no direct file upload). Since this repo is public, each
run commits the rendered card and references its
`raw.githubusercontent.com` URL. No extra hosting service needed.

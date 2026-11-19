#!/usr/bin/env python3
"""Add up GitHub traffic views across all your repos and write a shields.io badge.

GitHub only keeps 14 days of traffic, so this script stores each day's count in
stats/repo-views-history.json. Run it daily and the total keeps growing.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
TOKEN = os.environ.get("VIEWS_TOKEN")
INCLUDE_PRIVATE = os.environ.get("INCLUDE_PRIVATE", "false").lower() == "true"
INCLUDE_FORKS = os.environ.get("INCLUDE_FORKS", "false").lower() == "true"
LABEL = os.environ.get("BADGE_LABEL", "Repo views")
COLOR = os.environ.get("BADGE_COLOR", "blue")
DATA = Path(os.environ.get("DATA_DIR", "stats"))
HISTORY = DATA / "repo-views-history.json"
BADGE = DATA / "repo-views.json"


def get(url):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "repo-views-counter",
    })
    with urllib.request.urlopen(req) as r:
        return json.load(r), r.headers.get("Link", "")


def list_repos():
    visibility = "all" if INCLUDE_PRIVATE else "public"
    url = f"{API}/user/repos?affiliation=owner&visibility={visibility}&per_page=100"
    repos = []
    while url:
        page, link = get(url)
        repos += page
        url = None
        for part in link.split(","):
            if 'rel="next"' in part:
                url = part[part.index("<") + 1:part.index(">")]
    return [r["full_name"] for r in repos if INCLUDE_FORKS or not r["fork"]]


def main():
    if not TOKEN:
        sys.exit("VIEWS_TOKEN is not set. Add it as a repository secret.")

    history = json.loads(HISTORY.read_text()) if HISTORY.exists() else {}

    for repo in list_repos():
        try:
            data, _ = get(f"{API}/repos/{repo}/traffic/views?per=day")
        except urllib.error.HTTPError as e:
            print(f"skip {repo}: HTTP {e.code}")
            continue
        days = history.setdefault(repo, {})
        for v in data.get("views", []):
            day = v["timestamp"][:10]
            # Today's count is still growing, so keep the larger number.
            days[day] = max(days.get(day, 0), v["count"])
        print(f"{repo}: {sum(days.values())}")

    total = sum(sum(days.values()) for days in history.values())
    DATA.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n")
    BADGE.write_text(json.dumps({
        "schemaVersion": 1,
        "label": LABEL,
        "message": f"{total:,}",
        "color": COLOR,
    }) + "\n")
    print(f"Total: {total:,}")


if __name__ == "__main__":
    main()

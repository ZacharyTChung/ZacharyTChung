#!/usr/bin/env python3
"""Refresh the Projects section of README.md from live GitHub repo data.

Pulls the user's public repos, drops forks/archived/the profile repo, keeps the
most recently pushed ones, and rewrites the block between the PROJECTS markers
with github-readme-stats pin cards. Runs daily (and on push) via GitHub Actions
so the section tracks the account without manual edits.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

# NOTE: do not read $USERNAME — in zsh it is a special parameter bound to the OS
# user, so an inline `USERNAME=...` is silently clobbered. Use GH_USERNAME.
USERNAME = os.environ.get("GH_USERNAME", "ZacharyTChung")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"

START = "<!-- PROJECTS:START -->"
END = "<!-- PROJECTS:END -->"

# How many repos to surface, and the card theme (matches the rest of the page).
MAX_CARDS = 6
THEME = "tokyonight"


def fetch_repos():
    repos = []
    page = 1
    while True:
        url = (
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?per_page=100&page={page}&sort=pushed"
        )
        headers = {
            "User-Agent": "project-updater",
            "Accept": "application/vnd.github+json",
        }
        if TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.loads(r.read())
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return repos


def pick(repos):
    keep = [
        r
        for r in repos
        if not r.get("fork")
        and not r.get("archived")
        and not r.get("private")
        and r.get("name", "").lower() != USERNAME.lower()
    ]
    # Most recently pushed first; pin cards carry stars/description on their own.
    keep.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)
    return keep[:MAX_CARDS]


def render(repos):
    if not repos:
        return f"{START}\n_No public projects to show yet._\n{END}"

    cards = []
    for r in repos:
        repo = r["name"]
        href = r["html_url"]
        pin = (
            f"https://github-readme-stats.vercel.app/api/pin/"
            f"?username={USERNAME}&repo={repo}&theme={THEME}&hide_border=true"
        )
        cards.append(f'  <a href="{href}">\n    <img src="{pin}" />\n  </a>')

    body = "\n".join(cards)
    return (
        f"{START}\n"
        "<!-- This block is updated automatically by scripts/update_projects.py -->\n\n"
        '<div align="center">\n\n'
        f"{body}\n\n"
        "</div>\n"
        f"{END}"
    )


def main():
    text = README.read_text()
    if START not in text or END not in text:
        print("error: PROJECTS markers not found in README.md", file=sys.stderr)
        return 1

    repos = pick(fetch_repos())
    block = render(repos)

    before = text.split(START)[0]
    after = text.split(END)[1]
    README.write_text(before + block + after)

    shown = ", ".join(r["name"] for r in repos) or "(none)"
    print(f"updated Projects with {len(repos)} repos: {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate GIT INVADERS arcade SVG from real GitHub contribution data.

Each cell in the user's contribution graph (53 weeks x 7 days) becomes an
alien sprite, color-graded by commit count. A player ship at the bottom
fires lasers; explosions pop at real commit cells. Regenerated daily so the
formation reshapes itself as new commits land.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

USERNAME = os.environ.get("USERNAME", "ZacharyTChung")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "git-invaders.svg"

QUERY = """
query($u: String!) {
  user(login: $u) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
"""

# Sprite cell layout: each alien occupies CELL x CELL pixels; the 8x6 sprite
# is drawn in the top-left of each cell.
GRID_X0 = 64
GRID_Y0 = 110
CELL = 14
SPRITE_W = 8
SPRITE_H = 6


def fetch_graphql():
    if not TOKEN:
        return None
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"u": USERNAME}}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "git-invaders-generator",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        if "errors" in data:
            print(f"warn: graphql errors: {data['errors']}", file=sys.stderr)
            return None
        return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    except Exception as e:
        print(f"warn: graphql fetch failed: {e}", file=sys.stderr)
        return None


def fetch_public():
    """Scrape the public contribution page when no token is available."""
    url = f"https://github.com/users/{USERNAME}/contributions"
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 git-invaders"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode()
    except Exception as e:
        print(f"warn: public fetch failed: {e}", file=sys.stderr)
        return {"totalContributions": 0, "weeks": []}

    # Extract per-day attributes from the modern table-based layout.
    cells = re.findall(
        r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*data-level="(\d+)"',
        html,
    )
    if not cells:
        cells = re.findall(
            r'data-date="(\d{4}-\d{2}-\d{2})"[^>]*data-level="(\d+)"', html
        )

    # Approximate count from level bucket (no exact counts on public page).
    level_to_count = {0: 0, 1: 2, 2: 5, 3: 8, 4: 12}
    by_date = {d: level_to_count.get(int(lvl), int(lvl)) for d, lvl in cells}
    if not by_date:
        return {"totalContributions": 0, "weeks": []}

    sorted_dates = sorted(by_date.keys())
    weeks = []
    cur = []
    last_gh_dow = None
    for d in sorted_dates:
        gh_dow = (datetime.fromisoformat(d).weekday() + 1) % 7  # Sunday = 0
        if last_gh_dow is not None and gh_dow <= last_gh_dow:
            weeks.append({"contributionDays": cur})
            cur = []
        cur.append({"contributionCount": by_date[d], "date": d})
        last_gh_dow = gh_dow
    if cur:
        weeks.append({"contributionDays": cur})

    return {"totalContributions": sum(by_date.values()), "weeks": weeks}


def fetch():
    cal = fetch_graphql()
    if cal is None:
        print("info: falling back to public contribution scrape", file=sys.stderr)
        cal = fetch_public()
    return cal


def stats(cal):
    total = cal.get("totalContributions", 0)
    weeks = cal.get("weeks", [])
    days = [d for w in weeks for d in w.get("contributionDays", [])]
    days.sort(key=lambda d: d["date"])

    busiest = max((d["contributionCount"] for d in days), default=0)

    longest = run = 0
    for d in days:
        if d["contributionCount"] > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    today = date.today().isoformat()
    current = 0
    for d in reversed(days):
        if d["date"] > today:
            continue
        if d["contributionCount"] > 0:
            current += 1
        else:
            break

    return {
        "total": total,
        "busiest": busiest,
        "longest": longest,
        "current": current,
        "active_days": sum(1 for d in days if d["contributionCount"] > 0),
    }


def alien_color(c: int) -> str:
    if c < 3:
        return "#0e8e3a"
    if c < 6:
        return "#39d353"
    if c < 10:
        return "#ffcc33"
    return "#ff6644"


def build_formation(weeks):
    """Render every active commit day as a <use> of #alien."""
    items = []
    for wi, w in enumerate(weeks):
        for di, day in enumerate(w.get("contributionDays", [])):
            c = day["contributionCount"]
            if c <= 0:
                continue
            x = GRID_X0 + wi * CELL
            y = GRID_Y0 + di * CELL
            items.append(f'<use href="#alien" x="{x}" y="{y}" fill="{alien_color(c)}"/>')
    return "\n  ".join(items)


def build_stars(seed: int = 42, n: int = 70):
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        x = rnd.randint(8, 860)
        y = rnd.randint(8, 530)
        s = rnd.choice([1, 1, 1, 1, 2])
        delay = round(rnd.uniform(0, 4), 2)
        dur = round(rnd.uniform(2.2, 4.5), 2)
        out.append(
            f'<rect x="{x}" y="{y}" width="{s}" height="{s}" fill="#fff">'
            f'<animate attributeName="opacity" values="0.15;0.85;0.15" '
            f'dur="{dur}s" begin="{delay}s" repeatCount="indefinite"/></rect>'
        )
    return "\n  ".join(out)


def build_explosions(weeks, seed: int = 7, n: int = 8, cycle: float = 9.0):
    """Pop explosions at real commit cells, staggered across the loop."""
    active = [
        (wi, di, d["contributionCount"])
        for wi, w in enumerate(weeks)
        for di, d in enumerate(w.get("contributionDays", []))
        if d["contributionCount"] > 0
    ]
    if not active:
        return ""
    # Bias toward busier cells
    active.sort(key=lambda t: -t[2])
    pool = active[: max(20, len(active) // 4)]
    rnd = random.Random(seed)
    rnd.shuffle(pool)
    picks = pool[:n]
    out = []
    step = cycle / max(n, 1)
    for i, (wi, di, _c) in enumerate(picks):
        x = GRID_X0 + wi * CELL
        y = GRID_Y0 + di * CELL
        begin = round(i * step, 2)
        out.append(
            f'<g transform="translate({x},{y})" opacity="0">'
            f'<animate attributeName="opacity" values="0;1;1;0;0" '
            f'keyTimes="0;0.04;0.10;0.18;1" dur="{cycle}s" '
            f'begin="{begin}s" repeatCount="indefinite"/>'
            f'<rect x="0" y="-1" width="{SPRITE_W}" height="{SPRITE_H + 2}" fill="#ffee00"/>'
            f'<rect x="-2" y="1" width="2" height="2" fill="#ff6644"/>'
            f'<rect x="{SPRITE_W}" y="1" width="2" height="2" fill="#ff6644"/>'
            f'<rect x="2" y="-3" width="2" height="2" fill="#ff6644"/>'
            f'<rect x="2" y="{SPRITE_H + 1}" width="2" height="2" fill="#ff6644"/>'
            f"</g>"
        )
    return "\n  ".join(out)


def fmt6(n: int) -> str:
    return f"{min(n, 999999):06d}"


def build(cal) -> str:
    s = stats(cal)
    weeks = cal.get("weeks", [])
    formation = build_formation(weeks)
    stars = build_stars()
    explosions = build_explosions(weeks)

    today = date.today().strftime("%Y.%m.%d")
    score = fmt6(s["total"])
    hi = fmt6(max(s["busiest"], s["total"]))
    streak = fmt6(s["current"])
    longest = fmt6(s["longest"])

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 870 540" width="100%" preserveAspectRatio="xMidYMid meet" shape-rendering="crispEdges" role="img" aria-label="GIT INVADERS - contribution graph as alien formation">
  <title>GIT INVADERS · {s['total']} contributions · {s['active_days']} aliens · {s['current']}-day streak</title>
  <defs>
    <!-- 8x6 squid-style invader sprite. Fill comes from the <use>. -->
    <g id="alien">
      <rect x="1" y="0" width="2" height="1"/>
      <rect x="5" y="0" width="2" height="1"/>
      <rect x="0" y="1" width="8" height="1"/>
      <rect x="0" y="2" width="1" height="1"/>
      <rect x="2" y="2" width="1" height="1"/>
      <rect x="5" y="2" width="1" height="1"/>
      <rect x="7" y="2" width="1" height="1"/>
      <rect x="0" y="3" width="8" height="1"/>
      <rect x="1" y="4" width="1" height="1"/>
      <rect x="6" y="4" width="1" height="1"/>
      <rect x="0" y="5" width="1" height="1"/>
      <rect x="7" y="5" width="1" height="1"/>
    </g>
    <!-- Player ship -->
    <g id="ship">
      <rect x="6"  y="0" width="2"  height="2" fill="#39d353"/>
      <rect x="5"  y="2" width="4"  height="2" fill="#39d353"/>
      <rect x="2"  y="4" width="10" height="2" fill="#39d353"/>
      <rect x="0"  y="6" width="14" height="3" fill="#39d353"/>
      <rect x="1"  y="9" width="3"  height="1" fill="#39d353"/>
      <rect x="10" y="9" width="3"  height="1" fill="#39d353"/>
      <rect x="6"  y="3" width="2"  height="1" fill="#fff"/>
    </g>
  </defs>

  <style>
    text {{ font-family: 'Courier New', ui-monospace, monospace; font-weight: 700; }}
    @keyframes blink   {{ 0%,49% {{ opacity: 1 }} 50%,100% {{ opacity: 0.15 }} }}
    @keyframes coin    {{ 0%,49% {{ opacity: 1 }} 50%,100% {{ opacity: 0 }} }}
    @keyframes march   {{ 0%,100% {{ transform: translateX(-3px) }} 50% {{ transform: translateX(3px) }} }}
    @keyframes slide   {{ 0% {{ transform: translate(70px, 470px) }} 25% {{ transform: translate(620px, 470px) }} 50% {{ transform: translate(330px, 470px) }} 75% {{ transform: translate(770px, 470px) }} 100% {{ transform: translate(70px, 470px) }} }}
    @keyframes laser   {{ 0%,9% {{ opacity: 0; transform: translateY(0) }} 10% {{ opacity: 1; transform: translateY(0) }} 35% {{ opacity: 1; transform: translateY(-340px) }} 36%,100% {{ opacity: 0; transform: translateY(-340px) }} }}
    @keyframes scan    {{ 0% {{ transform: translateY(-30px) }} 100% {{ transform: translateY(540px) }} }}
    .blink {{ animation: blink 0.7s step-end infinite; }}
    .coin  {{ animation: coin 1.1s step-end infinite; }}
    .march {{ animation: march 1.6s ease-in-out infinite; }}
    .ship  {{ animation: slide 14s ease-in-out infinite; }}
    .laser {{ animation: laser 2.2s linear infinite; }}
    .scan  {{ animation: scan 5s linear infinite; }}
  </style>

  <!-- CRT bezel -->
  <rect width="870" height="540" fill="#000"/>
  <rect x="6" y="6" width="858" height="528" fill="#000" stroke="#222" stroke-width="2"/>

  <!-- Starfield -->
  <g>
  {stars}
  </g>

  <!-- HUD -->
  <text x="40"  y="34" font-size="14" fill="#33ccff">SCORE</text>
  <text x="40"  y="54" font-size="14" fill="#fff" class="blink">{score}</text>

  <text x="200" y="34" font-size="14" fill="#ff3333">HI-SCORE</text>
  <text x="210" y="54" font-size="14" fill="#fff">{hi}</text>

  <text x="380" y="34" font-size="14" fill="#ffcc00">STREAK</text>
  <text x="380" y="54" font-size="14" fill="#fff">{streak}</text>

  <text x="540" y="34" font-size="14" fill="#39d353">LONGEST</text>
  <text x="555" y="54" font-size="14" fill="#fff">{longest}</text>

  <text x="720" y="34" font-size="14" fill="#ff66cc">DATE</text>
  <text x="700" y="54" font-size="14" fill="#fff">{today}</text>

  <text x="435" y="86" text-anchor="middle" font-size="22" fill="#fff" letter-spacing="6">GIT INVADERS</text>

  <!-- Invader formation (the contribution graph) -->
  <g class="march">
    {formation}
    <!-- explosions sit on top of the formation -->
    {explosions}
  </g>

  <!-- Ship + laser -->
  <g class="ship">
    <use href="#ship" x="0" y="0"/>
    <g class="laser" transform="translate(7, -6)">
      <rect x="-1" y="-30" width="2" height="30" fill="#ffffff"/>
      <rect x="0"  y="-30" width="1" height="30" fill="#33ccff"/>
    </g>
  </g>

  <!-- Defense line -->
  <rect x="40" y="498" width="790" height="1" fill="#39d353" opacity="0.5"/>

  <!-- Color legend -->
  <g font-size="9" fill="#888">
    <text x="40" y="525">aliens by commits:</text>
    <use href="#alien" x="170" y="518" fill="#0e8e3a"/>
    <text x="184" y="525">1-2</text>
    <use href="#alien" x="220" y="518" fill="#39d353"/>
    <text x="234" y="525">3-5</text>
    <use href="#alien" x="270" y="518" fill="#ffcc33"/>
    <text x="284" y="525">6-9</text>
    <use href="#alien" x="320" y="518" fill="#ff6644"/>
    <text x="334" y="525">10+</text>
  </g>

  <!-- Footer -->
  <text x="600" y="525" font-size="11" fill="#666">DEFEND THE MAIN BRANCH  ·  </text>
  <text x="780" y="525" font-size="11" fill="#ffcc00" class="coin">1UP</text>

  <!-- Moving CRT scanline -->
  <rect class="scan" x="0" y="0" width="870" height="3" fill="rgba(255,255,255,0.05)"/>
</svg>
"""


def main():
    cal = fetch()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(cal))
    s = stats(cal)
    print(
        f"wrote {OUT}: total={s['total']} active={s['active_days']} "
        f"streak={s['current']} longest={s['longest']}"
    )


if __name__ == "__main__":
    main()

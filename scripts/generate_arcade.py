#!/usr/bin/env python3
"""Generate ZACHARY-KONG arcade SVG from real GitHub contribution data.

Fetches the user's contribution calendar via the GitHub GraphQL API and bakes
the data into a Donkey Kong themed animated SVG. Each week becomes a column of
colored girder bricks (intensity = commit count). HUD shows live stats.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

USERNAME = os.environ.get("USERNAME", "ZacharyTChung")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "dk-arcade.svg"

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


def fetch():
    if not TOKEN:
        print("warn: no token, using empty calendar", file=sys.stderr)
        return {"totalContributions": 0, "weeks": []}
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"u": USERNAME}}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "zachary-kong-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def stats(cal):
    total = cal.get("totalContributions", 0)
    weeks = cal.get("weeks", [])
    days = [d for w in weeks for d in w.get("contributionDays", [])]
    days.sort(key=lambda d: d["date"])

    busiest = max((d["contributionCount"] for d in days), default=0)

    longest = current = run = 0
    today = date.today().isoformat()
    for d in days:
        if d["contributionCount"] > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
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
    }


# DK-themed gradient: dark -> ember -> ember -> bright orange -> gold
def brick_color(c: int) -> str:
    if c <= 0:
        return "#1c1c1c"
    if c < 3:
        return "#7a2b00"
    if c < 6:
        return "#cc4b1f"
    if c < 10:
        return "#ff8c2a"
    return "#ffcc33"


def grid_svg(weeks, x0=70, y0=395, cell=12, gap=2):
    out = []
    for wi, w in enumerate(weeks):
        for di, day in enumerate(w.get("contributionDays", [])):
            x = x0 + wi * (cell + gap)
            y = y0 + di * (cell + gap)
            c = day["contributionCount"]
            fill = brick_color(c)
            # Brick highlight (top edge) for 3D effect
            out.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{fill}"/>'
            )
            if c > 0:
                out.append(
                    f'<rect x="{x}" y="{y}" width="{cell}" height="2" fill="rgba(255,255,255,0.18)"/>'
                )
    return "\n  ".join(out)


def fmt6(n: int) -> str:
    return f"{min(n, 999999):06d}"


def build(cal) -> str:
    s = stats(cal)
    weeks = cal.get("weeks", [])
    grid = grid_svg(weeks)

    today = date.today().strftime("%Y.%m.%d")
    score = fmt6(s["total"])
    hi = fmt6(max(s["busiest"], s["total"]))
    streak = fmt6(s["current"])
    longest = fmt6(s["longest"])

    # 53 weeks * 14px = 742, +70 left = grid spans 70..812 — viewBox 800 wide (slight clip OK)
    # Pad to 870 wide so full grid fits.
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 870 540" width="100%" preserveAspectRatio="xMidYMid meet" shape-rendering="crispEdges" role="img" aria-label="ZACHARY-KONG arcade view of contribution graph">
  <title>ZACHARY-KONG · {s['total']} contributions · {s['current']}-day streak</title>
  <style>
    text {{ font-family: 'Courier New', ui-monospace, monospace; font-weight: 700; }}
    @keyframes blink   {{ 0%,49% {{ opacity: 1 }} 50%,100% {{ opacity: 0.15 }} }}
    @keyframes coin    {{ 0%,49% {{ opacity: 1 }} 50%,100% {{ opacity: 0 }} }}
    @keyframes dkbob   {{ 0%,100% {{ transform: translate(80px,30px) }} 50% {{ transform: translate(80px,25px) }} }}
    @keyframes mariojump {{ 0%,70% {{ transform: translate(420px,360px) }} 78% {{ transform: translate(420px,336px) }} 85% {{ transform: translate(420px,360px) }} }}
    @keyframes heartbeat {{ 0%,100% {{ transform: translate(720px,30px) scale(1) }} 50% {{ transform: translate(718px,28px) scale(1.25) }} }}
    @keyframes flame   {{ 0%,100% {{ transform: translate(56px,387px) scaleY(1) }} 50% {{ transform: translate(56px,385px) scaleY(1.3) }} }}
    @keyframes scan    {{ 0% {{ transform: translateY(-100%) }} 100% {{ transform: translateY(540px) }} }}
    .blink {{ animation: blink 0.7s step-end infinite; }}
    .coin  {{ animation: coin 1.1s step-end infinite; }}
    .dk    {{ animation: dkbob 1.6s ease-in-out infinite; }}
    .mario {{ animation: mariojump 3s ease-out infinite; }}
    .heart {{ animation: heartbeat 0.9s ease-in-out infinite; }}
    .flame {{ animation: flame 0.4s ease-in-out infinite; }}
    .scan  {{ animation: scan 5s linear infinite; }}
  </style>

  <!-- CRT bezel + screen -->
  <rect width="870" height="540" fill="#000"/>
  <rect x="6" y="6" width="858" height="528" fill="#000" stroke="#222" stroke-width="2"/>

  <!-- Scanlines -->
  <g opacity="0.05" fill="#fff">
    <rect x="0" y="0" width="870" height="1"/><rect x="0" y="6" width="870" height="1"/>
    <rect x="0" y="12" width="870" height="1"/><rect x="0" y="18" width="870" height="1"/>
    <rect x="0" y="24" width="870" height="1"/><rect x="0" y="30" width="870" height="1"/>
    <rect x="0" y="36" width="870" height="1"/><rect x="0" y="42" width="870" height="1"/>
    <rect x="0" y="48" width="870" height="1"/><rect x="0" y="54" width="870" height="1"/>
  </g>

  <!-- HUD (live data) -->
  <text x="40"  y="34" font-size="14" fill="#33ccff">1UP</text>
  <text x="40"  y="54" font-size="14" fill="#fff" class="blink">{score}</text>

  <text x="200" y="34" font-size="14" fill="#ff3333">HIGH SCORE</text>
  <text x="225" y="54" font-size="14" fill="#fff">{hi}</text>

  <text x="400" y="34" font-size="14" fill="#ffcc00">STREAK</text>
  <text x="395" y="54" font-size="14" fill="#fff">{streak}</text>

  <text x="560" y="34" font-size="14" fill="#39d353">LONGEST</text>
  <text x="570" y="54" font-size="14" fill="#fff">{longest}</text>

  <text x="740" y="34" font-size="14" fill="#ff66cc">DATE</text>
  <text x="720" y="54" font-size="14" fill="#fff">{today}</text>

  <!-- Red girders (top half: arcade scene) -->
  <g fill="#e84545">
    <rect x="60" y="92"  width="750" height="8"/>
    <polygon points="60,168 810,178 810,186 60,176"/>
    <polygon points="60,258 810,250 810,258 60,266"/>
    <polygon points="60,338 810,346 810,354 60,346"/>
    <rect x="60"  y="100" width="6" height="246"/>
    <rect x="804" y="100" width="6" height="246"/>
  </g>

  <!-- Yellow ladders -->
  <g fill="#ffcc00">
    <rect x="700" y="100" width="3" height="78"/><rect x="720" y="100" width="3" height="78"/>
    <rect x="700" y="110" width="23" height="2"/><rect x="700" y="125" width="23" height="2"/>
    <rect x="700" y="140" width="23" height="2"/><rect x="700" y="155" width="23" height="2"/>
    <rect x="700" y="170" width="23" height="2"/>

    <rect x="120" y="176" width="3" height="82"/><rect x="140" y="176" width="3" height="82"/>
    <rect x="120" y="186" width="23" height="2"/><rect x="120" y="201" width="23" height="2"/>
    <rect x="120" y="216" width="23" height="2"/><rect x="120" y="231" width="23" height="2"/>
    <rect x="120" y="246" width="23" height="2"/>

    <rect x="700" y="254" width="3" height="86"/><rect x="720" y="254" width="3" height="86"/>
    <rect x="700" y="264" width="23" height="2"/><rect x="700" y="279" width="23" height="2"/>
    <rect x="700" y="294" width="23" height="2"/><rect x="700" y="309" width="23" height="2"/>
    <rect x="700" y="324" width="23" height="2"/>
  </g>

  <!-- Oil drum + flame -->
  <rect x="48" y="360" width="36" height="22" fill="#3a8de8"/>
  <rect x="48" y="360" width="36" height="2"  fill="#0044aa"/>
  <rect x="48" y="372" width="36" height="2"  fill="#0044aa"/>
  <rect x="48" y="358" width="36" height="2"  fill="#000"/>
  <text x="60" y="376" font-size="9" fill="#fff">OIL</text>
  <g class="flame">
    <polygon points="0,0 8,-12 16,0 12,-6 20,-14 24,0" fill="#ff9900"/>
    <polygon points="4,0 10,-8 14,-2 18,-10 22,0"      fill="#ffee00"/>
  </g>

  <!-- Donkey Kong -->
  <g class="dk">
    <rect x="0"  y="28" width="78" height="30" fill="#a0522d"/>
    <rect x="6"  y="22" width="66" height="40" fill="#a0522d"/>
    <rect x="22" y="34" width="34" height="22" fill="#deb887"/>
    <rect x="14" y="0"  width="50" height="26" fill="#a0522d"/>
    <rect x="20" y="6"  width="38" height="14" fill="#deb887"/>
    <rect x="10" y="6"  width="6"  height="8"  fill="#a0522d"/>
    <rect x="62" y="6"  width="6"  height="8"  fill="#a0522d"/>
    <rect x="24" y="9"  width="6"  height="6"  fill="#fff"/>
    <rect x="44" y="9"  width="6"  height="6"  fill="#fff"/>
    <rect x="26" y="11" width="3"  height="3"  fill="#000"/>
    <rect x="46" y="11" width="3"  height="3"  fill="#000"/>
    <rect x="32" y="16" width="14" height="2"  fill="#000"/>
    <rect x="28" y="20" width="22" height="2"  fill="#000"/>
    <rect x="-12" y="16" width="14" height="14" fill="#a0522d"/>
    <rect x="-18" y="6"  width="12" height="14" fill="#a0522d"/>
    <rect x="76"  y="16" width="14" height="14" fill="#a0522d"/>
    <rect x="82"  y="6"  width="12" height="14" fill="#a0522d"/>
    <rect x="14" y="58" width="20" height="14" fill="#a0522d"/>
    <rect x="44" y="58" width="20" height="14" fill="#a0522d"/>
  </g>

  <!-- Pauline -->
  <g transform="translate(740, 50)">
    <rect x="6"  y="0"  width="20" height="10" fill="#ffcc00"/>
    <rect x="3"  y="3"  width="3"  height="14" fill="#ffcc00"/>
    <rect x="26" y="3"  width="3"  height="14" fill="#ffcc00"/>
    <rect x="8"  y="8"  width="16" height="12" fill="#ffd9b3"/>
    <rect x="11" y="12" width="2"  height="2"  fill="#000"/>
    <rect x="19" y="12" width="2"  height="2"  fill="#000"/>
    <rect x="13" y="16" width="6"  height="1"  fill="#cc0044"/>
    <rect x="3"  y="20" width="26" height="22" fill="#e83a8a"/>
    <rect x="0"  y="24" width="32" height="14" fill="#e83a8a"/>
    <rect x="9"  y="42" width="4"  height="6"  fill="#ffd9b3"/>
    <rect x="19" y="42" width="4"  height="6"  fill="#ffd9b3"/>
    <rect x="7"  y="48" width="6"  height="2"  fill="#000"/>
    <rect x="19" y="48" width="6"  height="2"  fill="#000"/>
  </g>
  <text x="700" y="46" font-size="11" fill="#fff">HELP!</text>

  <!-- Heart (animated) -->
  <g class="heart">
    <rect x="0" y="2" width="3" height="6" fill="#ff3366"/>
    <rect x="3" y="0" width="3" height="3" fill="#ff3366"/>
    <rect x="6" y="2" width="3" height="6" fill="#ff3366"/>
    <rect x="3" y="3" width="3" height="5" fill="#ff3366"/>
    <rect x="2" y="8" width="5" height="2" fill="#ff3366"/>
    <rect x="3" y="10" width="3" height="2" fill="#ff3366"/>
  </g>

  <!-- Mario (animated) -->
  <g class="mario">
    <rect x="0" y="0"  width="16" height="3" fill="#cc0000"/>
    <rect x="2" y="3"  width="14" height="3" fill="#cc0000"/>
    <rect x="6" y="2"  width="4"  height="2" fill="#fff"/>
    <rect x="2" y="6"  width="14" height="9" fill="#ffd9b3"/>
    <rect x="0" y="9"  width="2"  height="3" fill="#ffd9b3"/>
    <rect x="0" y="6"  width="2"  height="3" fill="#663300"/>
    <rect x="11" y="9" width="2"  height="3" fill="#000"/>
    <rect x="4" y="12" width="10" height="2" fill="#000"/>
    <rect x="0" y="15" width="16" height="9" fill="#0044cc"/>
    <rect x="0" y="15" width="3"  height="6" fill="#cc0000"/>
    <rect x="13" y="15" width="3" height="6" fill="#cc0000"/>
    <rect x="3" y="17" width="2"  height="2" fill="#ffcc00"/>
    <rect x="11" y="17" width="2" height="2" fill="#ffcc00"/>
    <rect x="-2" y="18" width="3" height="3" fill="#ffd9b3"/>
    <rect x="15" y="18" width="3" height="3" fill="#ffd9b3"/>
    <rect x="2" y="24" width="4"  height="5" fill="#0044cc"/>
    <rect x="10" y="24" width="4" height="5" fill="#0044cc"/>
    <rect x="0" y="28" width="6"  height="3" fill="#663300"/>
    <rect x="10" y="28" width="6" height="3" fill="#663300"/>
  </g>

  <!-- Animated barrel rolling across platforms -->
  <g>
    <animateTransform attributeName="transform" type="translate"
      values="120,82; 720,90; 720,168; 120,175; 120,250; 720,256; 720,332; 380,338; 380,360"
      keyTimes="0; 0.16; 0.22; 0.40; 0.46; 0.62; 0.68; 0.84; 1"
      dur="11s" repeatCount="indefinite" additive="replace"/>
    <animateTransform attributeName="transform" type="rotate"
      from="0" to="360" dur="0.5s" repeatCount="indefinite" additive="sum"/>
    <g transform="translate(-11,-7)">
      <rect x="0"  y="0"  width="22" height="14" fill="#cc6633"/>
      <rect x="0"  y="0"  width="22" height="2"  fill="#7a2b00"/>
      <rect x="0"  y="12" width="22" height="2"  fill="#7a2b00"/>
      <rect x="3"  y="0"  width="2"  height="14" fill="#000"/>
      <rect x="11" y="0"  width="2"  height="14" fill="#000"/>
      <rect x="17" y="0"  width="2"  height="14" fill="#000"/>
    </g>
  </g>

  <!-- LEVEL DATA section: contribution graph as girder bricks -->
  <text x="70" y="385" font-size="11" fill="#888" letter-spacing="2">LEVEL DATA · last 53 weeks</text>
  <g>
  {grid}
  </g>

  <!-- Brick legend -->
  <g font-size="9" fill="#888">
    <text x="640" y="510">less</text>
    <rect x="668" y="503" width="9" height="9" fill="#1c1c1c"/>
    <rect x="680" y="503" width="9" height="9" fill="#7a2b00"/>
    <rect x="692" y="503" width="9" height="9" fill="#cc4b1f"/>
    <rect x="704" y="503" width="9" height="9" fill="#ff8c2a"/>
    <rect x="716" y="503" width="9" height="9" fill="#ffcc33"/>
    <text x="730" y="510">more</text>
  </g>

  <!-- Footer -->
  <text x="435" y="528" text-anchor="middle" font-size="11" fill="#666">© ZACHARY-KONG  ·  </text>
  <text x="525" y="528" font-size="11" fill="#ffcc00" class="coin">INSERT COIN</text>

  <!-- Moving scanline overlay -->
  <rect class="scan" x="0" y="0" width="870" height="3" fill="rgba(255,255,255,0.04)"/>
</svg>
"""


def main():
    cal = fetch()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(cal))
    s = stats(cal)
    print(f"wrote {OUT}: total={s['total']} streak={s['current']} longest={s['longest']}")


if __name__ == "__main__":
    main()

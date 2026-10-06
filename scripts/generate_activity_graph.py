#!/usr/bin/env python3
"""Generate the 30-day contribution activity graph as a static SVG.

The README used to embed github-readme-activity-graph.vercel.app, whose public
deployment was shut off (HTTP 402 DEPLOYMENT_DISABLED), so the graph vanished
from the profile. This script pulls daily contribution counts from the GitHub
GraphQL API and renders the same kind of tokyo-night area/line chart to
assets/activity-graph.svg. GitHub Actions runs it on a schedule and commits the
file only when it changes, so the profile no longer depends on a third-party
host for this section.
"""
from __future__ import annotations

import json
import math
import os
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# NOTE: do not read $USERNAME - in zsh it is bound to the OS user. Use GH_USERNAME.
USERNAME = os.environ.get("GH_USERNAME", "ZacharyTChung")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
DAYS = int(os.environ.get("GRAPH_DAYS", "30"))
# "Today" is taken in the account owner's timezone so the last point is the
# day they are actually living in, not the runner's UTC date.
TZ = ZoneInfo(os.environ.get("GRAPH_TZ", "America/Los_Angeles"))
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "activity-graph.svg"

# tokyo-night, matching the other cards on the page.
BG = "#1a1b27"
TITLE = "#70a5fd"
TEXT = "#a9b1d6"
MUTED = "#565f89"
GRID = "#272a3d"
LINE = "#bf91f3"
POINT = "#38bdae"

W, H = 880, 320
PAD_L, PAD_R, PAD_T, PAD_B = 60, 28, 72, 44
PLOT_W = W - PAD_L - PAD_R
PLOT_H = H - PAD_T - PAD_B
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

QUERY = """
query($u: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $u) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch_counts(start: date, end: date) -> dict[str, int]:
    """Return {ISO date: contribution count} covering at least [start, end]."""
    if not TOKEN:
        raise SystemExit("error: GH_TOKEN or GITHUB_TOKEN is required")
    # Pad by a day each side: GitHub buckets days in the account's timezone,
    # which need not match the runner's.
    variables = {
        "u": USERNAME,
        "from": f"{start - timedelta(days=1)}T00:00:00Z",
        "to": f"{end + timedelta(days=1)}T23:59:59Z",
    }
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "activity-graph-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    if "errors" in data or not data.get("data", {}).get("user"):
        raise SystemExit(f"error: graphql: {data.get('errors') or data}")
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return {
        d["date"]: d["contributionCount"]
        for w in cal["weeks"]
        for d in w["contributionDays"]
    }


def nice_step(vmax: int, target: int = 4) -> int:
    """Smallest 1/2/5 x 10^n step that needs at most `target` gridlines above 0."""
    if vmax <= 0:
        return 1
    raw = vmax / target
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return max(1, int(m * mag))
    return max(1, int(10 * mag))


def fmt_day(d: date) -> str:
    return f"{d.strftime('%b')} {d.day}"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build(points: list[tuple[date, int]]) -> str:
    n = len(points)
    values = [v for _, v in points]
    vmax = max(values)
    step = nice_step(vmax)
    ymax = max(step, step * math.ceil(vmax / step))
    total = sum(values)
    peak_i = values.index(vmax)
    last_i = n - 1

    def x(i: int) -> float:
        return PAD_L + i * PLOT_W / max(n - 1, 1)

    def y(v: float) -> float:
        return PAD_T + PLOT_H - v / ymax * PLOT_H

    base = round(y(0), 2)
    coords = [(round(x(i), 2), round(y(v), 2)) for i, v in enumerate(values)]
    line_d = "M" + " L".join(f"{cx} {cy}" for cx, cy in coords)
    area_d = f"{line_d} L{coords[-1][0]} {base} L{coords[0][0]} {base} Z"

    # Hairline grid, one shade off the surface, with y ticks on clean numbers.
    grid, yticks = [], []
    for v in range(0, ymax + 1, step):
        gy = round(y(v), 2)
        grid.append(f'<line x1="{PAD_L}" y1="{gy}" x2="{W - PAD_R}" y2="{gy}" />')
        yticks.append(f'<text x="{PAD_L - 12}" y="{gy + 4}" text-anchor="end">{v}</text>')

    # One x label per week, counted back from the last day so "today" is labeled.
    xticks = []
    for i, (d, _) in enumerate(points):
        if (last_i - i) % 7 == 0:
            xticks.append(
                f'<text x="{coords[i][0]}" y="{H - PAD_B + 24}" '
                f'text-anchor="middle">{fmt_day(d)}</text>'
            )

    # Markers with a 2px surface ring so they stay legible where they cross the line.
    dots = [f'<circle class="dot" cx="{cx}" cy="{cy}" r="4" />' for cx, cy in coords]

    # Direct labels: the peak, plus the endpoint when it will not collide.
    picks = [(peak_i, vmax)]
    if last_i - peak_i >= 2:
        picks.append((last_i, values[last_i]))
    labels = [
        f'<text x="{coords[i][0]}" y="{coords[i][1] - 11}" text-anchor="middle">{v}</text>'
        for i, v in picks
    ]

    first_d, last_d = points[0][0], points[-1][0]
    span = f"{fmt_day(first_d)} – {fmt_day(last_d)}, {last_d.year}"
    plural = "s" if total != 1 else ""
    peak_txt = f"peak {vmax} on {fmt_day(points[peak_i][0])}" if vmax else "no contributions yet"
    subtitle = f"{span}  ·  {total} contribution{plural}  ·  {peak_txt}"
    desc = (
        f"Daily GitHub contributions for {USERNAME} from {first_d} to {last_d}: "
        f"{total} total, peak {vmax} on {points[peak_i][0]}."
    )

    nl = "\n    "
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" aria-labelledby="t d">
  <title id="t">Contribution activity · last {n} days</title>
  <desc id="d">{esc(desc)}</desc>
  <defs>
    <linearGradient id="wash" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{LINE}" stop-opacity="0.22" />
      <stop offset="1" stop-color="{LINE}" stop-opacity="0.02" />
    </linearGradient>
  </defs>
  <style>
    text {{ font-family: {FONT}; }}
    .title {{ font-size: 16px; font-weight: 600; fill: {TITLE}; }}
    .sub {{ font-size: 11.5px; fill: {MUTED}; }}
    .tick {{ font-size: 11px; fill: {MUTED}; font-variant-numeric: tabular-nums; }}
    .label {{ font-size: 11.5px; font-weight: 600; fill: {TEXT}; font-variant-numeric: tabular-nums; }}
    .grid line {{ stroke: {GRID}; stroke-width: 1; shape-rendering: crispEdges; }}
    /* Deliberately static: GitHub serves README images as plain image embeds,
       where Chrome leaves CSS animations frozen at t=0, so anything that
       fades in would stay hidden. (No angle brackets in here: this is XML.) */
    .line {{ fill: none; stroke: {LINE}; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }}
    .area {{ fill: url(#wash); }}
    .dot {{ fill: {POINT}; stroke: {BG}; stroke-width: 2; }}
  </style>

  <rect width="{W}" height="{H}" rx="6" fill="{BG}" />

  <text class="title" x="{PAD_L}" y="30">Contribution activity</text>
  <text class="sub" x="{PAD_L}" y="50">{esc(subtitle)}</text>

  <g class="grid">
    {nl.join(grid)}
  </g>
  <g class="tick">
    {nl.join(yticks)}
    {nl.join(xticks)}
  </g>

  <path class="area" d="{area_d}" />
  <path class="line" d="{line_d}" />
  <g>
    {nl.join(dots)}
  </g>
  <g class="label">
    {nl.join(labels)}
  </g>
</svg>
"""


def main() -> int:
    today = datetime.now(TZ).date()
    start = today - timedelta(days=DAYS - 1)
    dates = [start + timedelta(days=i) for i in range(DAYS)]
    counts = fetch_counts(start, today)
    missing = [d for d in dates if d.isoformat() not in counts]
    if missing:
        raise SystemExit(f"error: calendar missing {len(missing)} day(s), e.g. {missing[0]}")
    points = [(d, counts[d.isoformat()]) for d in dates]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(points))
    total = sum(v for _, v in points)
    peak = max(v for _, v in points)
    print(f"wrote {OUT.relative_to(ROOT)}: {start} -> {today} total={total} peak={peak}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate the profile's contribution animation using only Python's standard library."""

import argparse
from datetime import date
import json
import os
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
DURATION = 32
PITCH, DOT, GRID_X, GRID_Y = 16, 12, 48, 112
LEVELS = {name: index for index, name in enumerate([
    "NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"
])}
THEMES = {
    "light": {
        "background": "#ffffff", "border": "#dce5f1", "text": "#142746",
        "muted": "#536780", "line": "#e7edf5", "accent": "#1d5dc9",
        "dots": ["#e9eff8", "#c6d8f6", "#7eabed", "#367bd8", "#1d5dc9"],
    },
    "dark": {
        "background": "#0b1221", "border": "#25334b", "text": "#edf4ff",
        "muted": "#9cacc4", "line": "#25334b", "accent": "#73b7ff",
        "dots": ["#18263b", "#204779", "#2c70cb", "#58a6ff", "#81d8ee"],
    },
}
QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}"""


def element(parent, tag, text=None, **attributes):
    node = ET.SubElement(parent, f"{{{SVG}}}{tag}", {
        key.replace("_", "-"): str(value) for key, value in attributes.items()
    })
    node.text = text
    return node


def fetch_calendar(username):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("Set GITHUB_TOKEN or provide a saved API response with --calendar")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": username}}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "DanieleRaimondi-ContributionFlow"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def parse_calendar(payload):
    if payload.get("errors"):
        raise ValueError("GitHub could not return the contribution calendar")
    user = payload.get("data", {}).get("user")
    if not user:
        raise ValueError("GitHub user not found")
    calendar = user["contributionsCollection"]["contributionCalendar"]
    weeks = calendar["weeks"]
    if not 1 <= len(weeks) <= 54:
        raise ValueError("Unexpected number of weeks in the calendar")
    days = []
    seen = set()
    for column, week in enumerate(weeks):
        for day in week["contributionDays"]:
            day_date = date.fromisoformat(day["date"])
            row = (day_date.weekday() + 1) % 7
            level = LEVELS[day["contributionLevel"]]
            count = day["contributionCount"]
            if day_date in seen or not isinstance(count, int) or count < 0:
                raise ValueError("Invalid or duplicate contribution day")
            seen.add(day_date)
            days.append((column, row, level, day["date"], count))
    if not days:
        raise ValueError("The contribution calendar is empty")
    return len(weeks), days


def create_svg(calendar, theme):
    columns, days = calendar
    colors = THEMES[theme]
    width, height = columns * PITCH + 96, 336
    # An original, simple route: sweep each column in alternating directions.
    route = [(column, row) for column in range(columns)
             for row in (range(7) if column % 2 == 0 else range(6, -1, -1))]
    visits = {point: index for index, point in enumerate(route)}
    points = [(GRID_X + column * PITCH + DOT / 2,
               GRID_Y + row * PITCH + DOT / 2) for column, row in route]
    path = "M" + " L".join(f"{x:g},{y:g}" for x, y in points)

    root = ET.Element(f"{{{SVG}}}svg", {
        "viewBox": f"0 0 {width} {height}", "width": str(width), "height": str(height),
        "role": "img", "aria-labelledby": "flow-title flow-description",
    })
    element(root, "title", "Daniele Raimondi · Contribution flow", id="flow-title")
    element(root, "desc", (
        "A magenta trail sweeps through the past year's GitHub contribution calendar. "
        "Blue cells show GitHub's daily contribution levels. "
        "Original animation and presentation by Daniele Raimondi."
    ), id="flow-description")
    variables = ";".join(f"--level-{i}:{color}" for i, color in enumerate(colors["dots"]))
    css = [
        f":root{{--empty:{colors['dots'][0]};{variables}}}",
        ".flow-text{font-family:ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif}",
        ".flow-label{font-size:11px;font-weight:600;letter-spacing:1.8px}",
        ".flow-note{font-size:12px}",
        f".flow-trail{{animation:travel {DURATION}s linear infinite}}",
        f".flow-head{{animation:lead {DURATION}s linear infinite}}",
        "@keyframes travel{0%{stroke-dashoffset:8}88%,100%{stroke-dashoffset:-1000}}",
        "@keyframes lead{0%{stroke-dashoffset:1.3}88%,100%{stroke-dashoffset:-1006.7}}",
        f".flow-progress{{transform-origin:{GRID_X}px 0;animation:progress {DURATION}s linear infinite}}",
        "@keyframes progress{0%{transform:scaleX(0)}88%,92%{transform:scaleX(1)}100%{transform:scaleX(0)}}",
        "@media(prefers-reduced-motion:reduce){"
        ".contribution,.flow-trail,.flow-head,.flow-progress{animation:none!important}"
        ".flow-trail,.flow-head,.flow-progress{display:none}}",
    ]
    for column, row, level, _, _ in days:
        if level:
            index = visits[(column, row)]
            eaten = index / (len(route) - 1) * (1000 / 1008) * 88
            css.append(
                f"@keyframes consume-{index}{{0%,{eaten:.3f}%{{fill:var(--level-{level})}}"
                f"{eaten + 0.2:.3f}%,92%{{fill:var(--empty)}}"
                f"98%,100%{{fill:var(--level-{level})}}}}"
            )
    element(root, "style", "".join(css))
    element(root, "rect", x="0.5", y="0.5", width=width - 1, height=height - 1,
            rx=20, fill=colors["background"], stroke=colors["border"])
    for index, color in enumerate(["#1d5dc9", "#7e6ae6", "#ff1e9d"]):
        element(root, "rect", x=32 + index * 9, y=24, width=5, height=16,
                rx=2.5, fill=color)
    element(root, "text", "CONTRIBUTION FLOW", x=68, y=36,
            fill=colors["accent"], **{"class": "flow-text flow-label"})
    element(root, "text", "Daniele Raimondi", x=width - 32, y=36, text_anchor="end",
            fill=colors["muted"], **{"class": "flow-text flow-note"})
    element(root, "text", "A year of building, one contribution at a time.", x=32, y=67,
            fill=colors["text"], font_size=18, font_weight=600, **{"class": "flow-text"})

    for column, row, level, day_date, count in days:
        attributes = {"class": "contribution", "data-date": day_date,
                      "data-count": str(count), "data-level": str(level)}
        if level:
            attributes["style"] = f"animation:consume-{visits[(column, row)]} {DURATION}s linear infinite"
        cell = element(root, "rect", x=GRID_X + column * PITCH, y=GRID_Y + row * PITCH,
                       width=DOT, height=DOT, rx=3.5,
                       fill=f"var(--level-{level})", **attributes)
        element(cell, "title", f"{day_date}: {count} contributions")

    for css_class, color, thickness, dash, offset in [
        ("flow-trail", "#ff1e9d", 8, "8 2000", 8),
        ("flow-head", "#ffb1de", 8, "1.3 2000", 1.3),
    ]:
        element(root, "path", d=path, pathLength=1000, fill="none", stroke=color,
                stroke_width=thickness, stroke_linecap="round", stroke_linejoin="round",
                stroke_dasharray=dash, stroke_dashoffset=offset,
                **{"class": css_class})

    bar_width = (columns - 1) * PITCH + DOT
    element(root, "rect", x=GRID_X, y=258, width=bar_width, height=3, rx=1.5,
            fill=colors["dots"][0])
    element(root, "rect", x=GRID_X, y=258, width=bar_width, height=3, rx=1.5,
            fill="#ff1e9d", **{"class": "flow-progress"})
    element(root, "path", d=f"M32 286H{width - 32}", stroke=colors["line"])
    element(root, "text", "AI / DATA SCIENCE / QUANT FINANCE", x=32, y=312,
            fill=colors["muted"], **{"class": "flow-text flow-label"})
    legend_x = width - 190
    element(root, "text", "Less", x=legend_x, y=312,
            fill=colors["muted"], **{"class": "flow-text flow-note"})
    for index, color in enumerate(colors["dots"]):
        element(root, "rect", x=legend_x + 38 + index * 16, y=302,
                width=11, height=11, rx=3, fill=color)
    element(root, "text", "More", x=width - 32, y=312, text_anchor="end",
            fill=colors["muted"], **{"class": "flow-text flow-note"})
    return ET.ElementTree(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="DanieleRaimondi")
    parser.add_argument("--calendar", type=Path, help="Saved GitHub GraphQL response for local previews")
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()
    payload = json.loads(args.calendar.read_text()) if args.calendar else fetch_calendar(args.username)
    calendar = parse_calendar(payload)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        destination = args.output_dir / f"contribution-flow-{theme}.svg"
        create_svg(calendar, theme).write(destination, encoding="utf-8", xml_declaration=True)
        print(f"Generated {destination} ({len(calendar[1])} real contribution days)")


if __name__ == "__main__":
    main()

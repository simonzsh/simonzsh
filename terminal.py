"""Generate terminal.svg: an animated terminal window with live GitHub stats.

Run: python3 terminal.py   (needs the gh CLI and a token, GH_TOKEN in CI)
"""
import json
import subprocess
from datetime import date, datetime
from html import escape

LOGIN = "simonzsh"
ABOUT = [
    ("Name", "Simon"),
    ("Role", "Software developer"),
    ("Status", "Freelancer"),
    ("From", "Belgium, based in France"),
    ("School", "42 Paris, since May 2024"),
    ("OS", "macOS, Ubuntu"),
    ("Stack", "TypeScript, React, Next.js, Node.js, MongoDB"),
]
# Animated drawing at the left of the about block: 2 rows of steam above a cup.
# Each steam frame is shown in turn, FRAME_MS each. Keep all rows the same width.
STEAM = [
    ["      ( (       ", "       ) )      "],
    ["       ) )      ", "      ( (       "],
    ["       ( (      ", "        ) )     "],
    ["        ) )     ", "       ( (      "],
]
CUP = [
    r" .------------.   ",
    r" |            |--.",
    r" |            |  |",
    r" \            /--'",
    r"  `----------'    ",
]
FRAME_MS = 350
ART_W = max(map(len, CUP)) + 2  # columns reserved for the drawing, 2-column gap included

# Tokyo Night
BG, BAR, TEXT, DIM = "#1a1b26", "#16161e", "#c0caf5", "#7986b7"
GREEN, BLUE, PURPLE, RED = "#9ece6a", "#7aa2f7", "#bb9af7", "#f7768e"
WIDTH, BAR_H, PAD_X, PAD_Y = 800, 40, 12, 54
CHAR, LINE = 9.6, 28.8  # monospace 16px: char width, line height
TYPE_MS, IDLE_MS, OUT_MS, STAGGER_MS, END_MS = 70, 800, 300, 50, 200
BLINK_MS = 1600  # full on/off cycle of the last cursor
CHART_ROWS = 6
NBSP = " "  # plain spaces are collapsed by some SVG renderers
BARS = "▁▂▃▄▅▆▇█"


def gh(*args):
    out = subprocess.run(["gh", "api", *args], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def kv(rows):
    """Aligned 'label: value' rows. Leading spaces in a label indent the row."""
    width = max(len(k) for k, _ in rows) + 2
    return [[((k + ":").ljust(width).replace(" ", NBSP), BLUE), (v, TEXT)] for k, v in rows]


def mix(a, b, t):
    """Blend hex colors a and b; t=0 gives a, t=1 gives b."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def streaks(days, today):
    longest = run = 0
    for _, n in days:
        run = run + 1 if n else 0
        longest = max(longest, run)
    current = 0
    for d, n in reversed(days):
        if n:
            current += 1
        elif d != today:  # no activity yet today does not break the streak
            break
    return longest, current


def chart(weeks):
    """Bar chart of weekly totals: one column per week, 8 levels per text row.

    weeks is a list of (first day, total). Bars blend from blue (low) to purple (high).
    """
    values = [n for _, n in weeks]
    top = max(values) or 1
    pad = 2 * NBSP
    rows = [[(pad + "Contributions per week", DIM)]]
    for r in range(CHART_ROWS - 1, -1, -1):
        cells = ""
        for v in values:
            level = min(8, max(0, round(v / top * CHART_ROWS * 8 - r * 8)))
            if r == 0 and v:
                level = max(level, 1)
            cells += BARS[level - 1] if level else NBSP
        label = str(top) if r == CHART_ROWS - 1 else ""
        color = mix(BLUE, PURPLE, r / (CHART_ROWS - 1))
        rows.append([(pad + label.rjust(4, NBSP) + "│", DIM), (cells, color)])
    rows.append([(pad + "0".rjust(4, NBSP) + "└" + "─" * len(values), DIM)])
    # Month names under the first week of each month. The first, partial month
    # is skipped when the next label would overlap it.
    starts = [(i, first.strftime("%b")) for i, (first, _) in enumerate(weeks) if i == 0 or first.month != weeks[i - 1][0].month]
    if len(starts) > 1 and starts[1][0] < 4:
        starts = starts[1:]
    months = [NBSP] * len(values)
    for i, name in starts:
        if i + 3 <= len(values):
            months[i:i + 3] = name
    rows.append([(pad + NBSP * 5 + "".join(months), DIM)])
    return rows


def fmt(n):
    return f"{n:,}".replace(",", " ")


def fetch_stats():
    user = gh(f"users/{LOGIN}")
    today = date.today()
    created = datetime.fromisoformat(user["created_at"][:-1])
    # The API limits a range to one year, so one alias per calendar year.
    years = " ".join(
        f'y{y}: contributionsCollection(from:"{y}-01-01T00:00:00Z",to:"{y}-12-31T23:59:59Z")'
        "{contributionCalendar{totalContributions}}"
        for y in range(created.year, today.year + 1)
    )
    # No range on "last": the default window is the one the profile page shows.
    query = (
        f'query{{user(login:"{LOGIN}"){{{years} last: contributionsCollection'
        "{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"
    )
    data = gh("graphql", "-f", f"query={query}")["data"]["user"]
    total = sum(data[f"y{y}"]["contributionCalendar"]["totalContributions"] for y in range(created.year, today.year + 1))
    cal = data["last"]["contributionCalendar"]
    days = sorted(
        (date.fromisoformat(d["date"]), d["contributionCount"])
        for w in cal["weeks"] for d in w["contributionDays"]
        if date.fromisoformat(d["date"]) <= today
    )
    longest, current = streaks(days, today)
    best = max(days, key=lambda x: x[1])
    weeks = [
        (date.fromisoformat(w["contributionDays"][0]["date"]), sum(d["contributionCount"] for d in w["contributionDays"]))
        for w in cal["weeks"]
    ]
    github = kv([
        ("User", "@" + LOGIN),
        ("Repos", f"{user['public_repos']} public"),
        ("Network", f"{user['followers']} followers, {user['following']} following"),
        ("Joined", created.strftime("%b %Y")),
    ])
    commits = kv([
        ("All time", f"{fmt(total)} contributions"),
        ("Last 12 months", f"{fmt(cal['totalContributions'])} contributions"),
        ("  Active days", f"{sum(1 for _, n in days if n)} / {len(days)}"),
        ("  Streak", f"{current} days now, {longest} days best"),
        ("  Busiest day", f"{best[1]} on {best[0].strftime('%b %d, %Y')}"),
    ]) + chart(weeks)
    return github, commits


# --- SVG ---------------------------------------------------------------

def text_row(segments):
    out, x = [], 0
    for text, color in segments:
        w = len(text) * CHAR
        out.append(f'<tspan x="{x:.1f}" fill="{color}" textLength="{w:.1f}" lengthAdjust="spacingAndGlyphs">{escape(text)}</tspan>')
        x += w
    return f'<text class="tt">{"".join(out)}</text>'


def steam_cup(y, start):
    """Overlay with every steam frame stacked; SMIL shows one at a time."""
    n = len(STEAM)
    frames = []
    for k, steam in enumerate(STEAM):
        rows = [(r.replace(" ", NBSP), RED) for r in steam] + [(r.replace(" ", NBSP), PURPLE) for r in CUP]
        text = "".join(f'<g transform="translate(0, {i * LINE:.1f})">{text_row([row])}</g>' for i, row in enumerate(rows))
        # Visible only during its own slice of the cycle (discrete steps).
        times = [0, k / n, (k + 1) / n]
        values = ["0", "1", "0"]
        if k == 0:
            times, values = times[:1] + times[2:], ["1", "0"]
        elif k == n - 1:
            times, values = times[:2], ["0", "1"]
        anim = (
            f'<animate attributeName="opacity" values="{";".join(values)}" keyTimes="{";".join(f"{t:.4f}" for t in times)}" '
            f'calcMode="discrete" dur="{n * FRAME_MS}ms" begin="{start}ms" repeatCount="indefinite"/>'
        )
        frames.append(f'<g opacity="{1 if k == 0 else 0}">{anim}{text}</g>')
    return f'<g transform="translate(0, {y:.1f})" class="fade-in" style="animation-delay: {start}ms">{"".join(frames)}</g>'


def build():
    github, commits = fetch_stats()
    about = [[(NBSP * ART_W, DIM)] + row for row in kv(ABOUT)]
    blocks = [
        ("cat about.txt", [text_row(r) for r in about], steam_cup),
        (f"gh stats {LOGIN}", [text_row(r) for r in github], None),
        (f"gh commits {LOGIN}", [text_row(r) for r in commits], None),
        ("", [], None),  # last prompt, waits for input with a blinking cursor
    ]
    prompt = f"{LOGIN}:~$ "
    pw = len(prompt) * CHAR
    body, line, t = [], 0, 0
    for i, (cmd, rows, overlay) in enumerate(blocks):
        y = line * LINE
        type_at = t + (IDLE_MS if i else 0)  # the prompt shows first, then the typing starts
        type_ms = len(cmd) * TYPE_MS
        end = type_at + type_ms
        steps = [f"{pw + k * CHAR:.1f}" for k in range(len(cmd) + 1)]
        if cmd:
            cursor = (
                f'<animate attributeName="opacity" from="0" to="1" begin="{t}ms" dur="10ms" fill="freeze"/>'
                f'<animate attributeName="x" values="{";".join(steps)}" calcMode="discrete" begin="{type_at}ms" dur="{type_ms}ms" fill="freeze"/>'
                f'<animate attributeName="opacity" to="0" begin="{end}ms" dur="10ms" fill="freeze"/>'
            )
            # One hidden <text> per letter, shown by <set>. A clip-path reveal is
            # ignored by iOS WebKit when its rect has width 0.
            typed = "".join(
                f'<text class="tt" x="{pw + k * CHAR:.1f}" fill="{TEXT}" visibility="hidden">'
                f'<set attributeName="visibility" to="visible" begin="{type_at + round((k + 1) * type_ms / (len(cmd) + 1))}ms" fill="freeze"/>'
                f'{escape(ch)}</text>'
                for k, ch in enumerate(cmd) if ch != " "
            )
        else:
            cursor = f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="{BLINK_MS}ms" begin="{t}ms" repeatCount="indefinite"/>'
            typed = ""
        body.append(
            f'<g transform="translate(0, {y:.1f})">{typed}'
            f'<text class="tt fade-in" style="animation-delay: {t}ms" fill="{GREEN}" textLength="{pw:.1f}" lengthAdjust="spacingAndGlyphs">{escape(prompt)}</text>'
            f'<rect x="{pw:.1f}" y="-14" width="10" height="16" fill="{BLUE}" opacity="0">{cursor}</rect></g>'
        )
        line += 1
        for k, row in enumerate(rows):
            body.append(f'<g transform="translate(0, {(line + k) * LINE:.1f})" class="fade-in" style="animation-delay: {end + OUT_MS + k * STAGGER_MS}ms">{row}</g>')
        if overlay:
            body.append(overlay(line * LINE, end + OUT_MS))
        line += len(rows)
        t = end + OUT_MS + max(len(rows) - 1, 0) * STAGGER_MS + END_MS if rows else t

    height = int(PAD_Y + (line - 1) * LINE + 24)
    return f'''<svg width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Animated terminal showing: {escape(", ".join(c for c, _, _ in blocks if c))}">
  <title>{LOGIN} terminal</title>
  <style>
    .tt {{ font-family: JetBrains Mono, Fira Code, Ubuntu Mono, Consolas, Monaco, monospace; font-size: 16px; white-space: pre; }}
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    .fade-in {{ animation: fadeIn 10ms linear backwards; }}
    @media (prefers-reduced-motion: reduce) {{ * {{ animation-duration: 0.01ms !important; }} }}
  </style>
  <defs>
    <filter id="shadow" x="-8%" y="-8%" width="116%" height="120%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="8"/><feOffset dx="0" dy="6" result="o"/>
      <feFlood flood-color="#000" flood-opacity="0.55"/><feComposite in2="o" operator="in"/>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="view"><rect x="0" y="{BAR_H}" width="{WIDTH}" height="{height - BAR_H}"/></clipPath>
  </defs>
  <g filter="url(#shadow)">
    <rect width="{WIDTH}" height="{height}" rx="12" fill="{BG}"/>
    <rect width="{WIDTH}" height="{BAR_H}" rx="12" fill="{BAR}"/>
    <rect y="16" width="{WIDTH}" height="16" fill="{BAR}"/>
    <g stroke="rgba(0,0,0,0.18)" stroke-width="0.5">
      <circle cx="14" cy="16" r="6" fill="#f7768e"/><circle cx="34" cy="16" r="6" fill="#e0af68"/><circle cx="54" cy="16" r="6" fill="{GREEN}"/>
    </g>
    <text x="{WIDTH // 2}" y="24.5" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="13" fill="{TEXT}" text-anchor="middle">{LOGIN}: ~</text>
    <g clip-path="url(#view)"><g transform="translate({PAD_X}, {PAD_Y})">
      {"".join(body)}
    </g></g>
  </g>
</svg>
'''


if __name__ == "__main__":
    with open("terminal.svg", "w", encoding="utf-8") as f:
        f.write(build())

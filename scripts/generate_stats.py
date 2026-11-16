"""Create compact, self-hosted GitHub profile SVGs with the Python standard library."""
import json
import os
from collections import Counter
from datetime import date, datetime
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen

USER = os.environ.get("GITHUB_USERNAME", "nguyenj1863")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path("assets")
OUT.mkdir(exist_ok=True)
W = 460
COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#e6b800", "Python": "#3572a5",
    "HTML": "#e34c26", "CSS": "#663399", "C": "#555555", "C++": "#f34b7d",
    "Java": "#b07219", "C#": "#178600", "Shell": "#89e051",
    "Assembly": "#6e4c13",
}

def request(path, payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": "Bearer " + TOKEN,
        "User-Agent": "github-profile-stats",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = Request(
        "https://api.github.com" + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=headers,
    )
    with urlopen(req, timeout=25) as resp:
        return json.load(resp)

def text(x, y, value, size=12, color="#29364c", extra=""):
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
        f'{extra}>{escape(str(value))}</text>'
    )

def card(title, subtitle, shapes, height):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" '
        f'viewBox="0 0 {W} {height}" role="img" aria-label="{escape(title)}">'
        f'<title>{escape(title)}</title>'
        f'<rect x="1" y="1" width="{W-2}" height="{height-2}" rx="12" '
        'fill="#f8fbff" stroke="#d8e3f0"/>'
        '<g font-family="Arial, Helvetica, sans-serif">'
        + text(19, 29, title, 18, "#14243d", 'font-weight="700"')
        + text(19, 47, subtitle, 11, "#687b94")
        + "".join(shapes)
        + "</g></svg>"
    )

def languages():
    repositories = []
    for page in range(1, 11):
        page_data = request(f"/users/{USER}/repos?type=owner&per_page=100&page={page}")
        repositories.extend(page_data)
        if len(page_data) < 100:
            break

    originals = [
        r for r in repositories
        if not r["fork"] and not r["archived"] and not r.get("disabled")
        and r["name"] != USER
    ]
    totals = Counter()
    for repo in originals:
        try:
            totals.update(request(f'/repos/{USER}/{repo["name"]}/languages'))
        except Exception as exc:
            print("Skipping", repo["name"], exc)
    if not totals:
        raise RuntimeError("GitHub returned no language data")

    ordered = totals.most_common()
    total = sum(totals.values())
    shown = ordered[:5] + [("Other", sum(v for _, v in ordered[5:]))] if len(ordered) > 6 else ordered
    shapes = []
    for i, (language, count) in enumerate(shown):
        y = 76 + 32 * i
        color = COLORS.get(language, "#65758b")
        proportion = count / total
        shapes.extend([
            f'<circle cx="25" cy="{y-4}" r="4" fill="{color}"/>',
            text(36, y, language, 12),
            f'<rect x="146" y="{y-12}" width="226" height="10" rx="5" fill="#e2eaf5"/>',
            f'<rect x="146" y="{y-12}" width="{max(2,226*proportion):.2f}" height="10" rx="5" fill="{color}"/>',
            text(437, y, f"{100*proportion:.1f}%", 12, "#24354d",
                 'font-weight="600" text-anchor="end"'),
        ])
    height = 107 + 32 * len(shown)
    shapes.append(text(19, height-18, "Share of detected code bytes · public non-fork repositories", 10, "#687b94"))
    return card("Programming languages", f"Updated {date.today().isoformat()} · {len(originals)} repositories", shapes, height)

def contributions():
    query = (
        "query($login:String!){user(login:$login){"
        "contributionsCollection{contributionCalendar{totalContributions "
        "weeks{contributionDays{date contributionCount}}}}}}"
    )
    result = request("/graphql", {"query": query, "variables": {"login": USER}})
    if result.get("errors"):
        raise RuntimeError(str(result["errors"]))
    calendar = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = calendar["weeks"][-54:]
    def shade(n):
        return "#e0e8f2" if n == 0 else "#a8c8fc" if n <= 2 else "#5a96eb" if n <= 5 else "#3572d4" if n <= 10 else "#1752a5"

    shapes = []
    step = 7.75
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            dt = datetime.strptime(day["date"], "%Y-%m-%d").date()
            weekday = (dt.weekday() + 1) % 7
            x, y = 20 + col * step, 65 + weekday * 10
            shapes.append(
                f'<rect x="{x:.1f}" y="{y}" width="6.5" height="7.5" rx="1.5" '
                f'fill="{shade(day["contributionCount"])}">'
                f'<title>{day["date"]}: {day["contributionCount"]} contributions</title></rect>'
            )
    shapes.append(text(20, 162, f'{calendar["totalContributions"]:,} contributions in the past year',
                       14, "#14243d", 'font-weight="700"'))
    shapes.append(text(20, 181, "Activity visible on my GitHub profile", 10, "#687b94"))
    return card("Contribution activity", "Last 12 months", shapes, 195)

for name, generator in (("languages.svg", languages), ("contributions.svg", contributions)):
    # Do not overwrite working charts with an error placeholder after a transient API failure.
    data = generator()
    (OUT / name).write_text(data, encoding="utf-8")
    print("Updated", OUT / name)

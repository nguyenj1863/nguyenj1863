"""Render GitHub-owned SVG stats charts using only Python's standard library."""
import json
import os
from collections import Counter
from datetime import date, datetime
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen

USER = os.environ.get('GITHUB_USERNAME', 'nguyenj1863')
TOKEN = os.environ['GITHUB_TOKEN']
OUT = Path('assets')
OUT.mkdir(exist_ok=True)
COLORS = {'TypeScript': '#3178c6', 'JavaScript': '#e6b800', 'Python': '#3572a5',
          'HTML': '#e34c26', 'CSS': '#663399', 'C': '#555555', 'C++': '#f34b7d',
          'Java': '#b07219', 'C#': '#178600', 'Shell': '#89e051'}


def request(path, payload=None):
    headers = {'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28',
               'Authorization': 'Bearer ' + TOKEN, 'User-Agent': 'profile-stats'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    req = Request('https://api.github.com' + path,
                  data=json.dumps(payload).encode() if payload is not None else None,
                  headers=headers)
    with urlopen(req, timeout=25) as resp:
        return json.load(resp)


def txt(x, y, value, size=13, color='#27384e', extra=''):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" {extra}>{escape(str(value))}</text>'


def svg(title, subtitle, elements, height):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="820" height="{height}" viewBox="0 0 820 {height}" role="img" aria-label="{escape(title)}">
<title>{escape(title)}</title>
<rect x="1" y="1" width="818" height="{height-2}" rx="18" fill="#f8fbff" stroke="#d8e3f0"/>
<g font-family="Arial, Helvetica, sans-serif">
{txt(28, 42, title, 21, '#14243d', 'font-weight="700"')}
{txt(28, 66, subtitle, 12, '#687b94')}
{''.join(elements)}
</g></svg>'''


def languages():
    repos = []
    for page in range(1, 11):
        rows = request(f'/users/{USER}/repos?type=owner&per_page=100&page={page}')
        repos.extend(rows)
        if len(rows) < 100:
            break
    original = [r for r in repos if not r['fork'] and not r['archived']
                and not r.get('disabled') and r['name'] != USER]
    totals = Counter()
    for repo in original:
        try:
            totals.update(request(f'/repos/{USER}/{repo["name"]}/languages'))
        except Exception as ex:
            print('Skipping', repo['name'], ex)
    if not totals:
        raise RuntimeError('No language data returned')
    ordered = totals.most_common()
    total = sum(totals.values())
    shown = ordered[:5] + [('Other', sum(x[1] for x in ordered[5:]))] if len(ordered) > 6 else ordered
    parts = []
    for i, (lang, amount) in enumerate(shown):
        y = 112 + 44*i
        pct = 100*amount/total
        color = COLORS.get(lang, '#64748b')
        parts += [f'<circle cx="34" cy="{y-5}" r="5" fill="{color}"/>',
                  txt(47, y, lang, 14),
                  f'<rect x="190" y="{y-15}" width="502" height="14" rx="7" fill="#dce6f2"/>',
                  f'<rect x="190" y="{y-15}" width="{max(2, 502*amount/total):.1f}" height="14" rx="7" fill="{color}"/>',
                  txt(787, y, f'{pct:.1f}%', 14, extra='font-weight="600" text-anchor="end"')]
    height = 164 + len(shown)*44
    parts += [f'<path d="M28 {height-55}H792" stroke="#d8e3f0"/>',
              txt(28, height-30, 'Percentages by GitHub-detected code bytes · public repositories · forks excluded', 11, '#687b94')]
    return svg('Languages in my public repositories',
               f'{len(original)} public repositories considered · Updated {date.today().isoformat()}', parts, height)


def contributions():
    query = 'query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}'
    result = request('/graphql', {'query': query, 'variables': {'login': USER}})
    if result.get('errors'):
        raise RuntimeError(str(result['errors']))
    calendar = result['data']['user']['contributionsCollection']['contributionCalendar']
    weeks = calendar['weeks'][-54:]
    def shade(n):
        return '#e0e8f2' if n == 0 else '#a8c8fc' if n <= 2 else '#5a96eb' if n <= 5 else '#3572d4' if n <= 10 else '#1752a5'
    parts = []
    months = set()
    for col, week in enumerate(weeks):
        for day in week['contributionDays']:
            d = datetime.strptime(day['date'], '%Y-%m-%d').date()
            weekday = (d.weekday() + 1) % 7
            x, y = 39 + col*13.6, 114 + weekday*13.6
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="10.5" height="10.5" rx="2" fill="{shade(day["contributionCount"])}"><title>{day["date"]}: {day["contributionCount"]} contributions</title></rect>')
            key = (d.year, d.month)
            if d.day <= 7 and weekday == 0 and key not in months:
                months.add(key)
                parts.append(txt(f'{x:.1f}', 97, d.strftime('%b'), 12, '#687b94'))
    parts += [txt(39, 239, f'{calendar["totalContributions"]:,} contributions in the past year', 16, extra='font-weight="700"'),
              txt(39, 263, 'Includes contributions visible to GitHub Actions.', 11, '#687b94'),
              txt(672, 263, 'Less', 11, '#687b94')]
    for i, n in enumerate([0,1,3,7,11]):
        parts.append(f'<rect x="{710 + i*16}" y="253" width="11" height="11" rx="2" fill="{shade(n)}"/>')
    parts.append(txt(806, 263, 'More', 11, '#687b94', 'text-anchor="end"'))
    return svg('GitHub contribution activity', 'Daily contributions over the last 12 months', parts, 290)


for filename, build in [('languages.svg', languages), ('contributions.svg', contributions)]:
    try:
        content = build()
    except Exception as ex:
        print('Unable to retrieve', filename, ex)
        content = svg('GitHub statistics', 'This chart retries on the next scheduled run.',
                      [txt(28, 112, 'Statistics are temporarily unavailable.', 14)], 145)
    (OUT / filename).write_text(content, encoding='utf-8')
    print('Generated:', OUT / filename)

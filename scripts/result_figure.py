"""Generate the README result table from real demo outputs, without dependencies."""
import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render():
    result = json.loads((ROOT / 'results/fit.json').read_text())
    labels = {'framework': 'Stated-tier proxy', 'proportional+mNAV': 'Proportional + mNAV*'}
    lines = []
    for i, row in enumerate(result['rules']):
        y = 204 + i * 36
        label = labels.get(row['rule'], row['rule'])
        lines += [f'<text x="24" y="{y}">{html.escape(label)}</text>',
                  f'<text x="590" y="{y}" text-anchor="end">{row["post_break"]["mae_bp"]:.2f}</text>']
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="720" height="650" viewBox="0 0 720 650" role="img" aria-labelledby="title desc">
<title id="title">Only three holdout decisions: no predictive edge established</title>
<desc id="desc">Holdout mean absolute errors in basis points for eight retrospective policies. Hold has zero error; stated-tier proxy has 33.33. mNAV uses hindsight scaling.</desc>
<rect width="720" height="650" fill="#F5F5EF"/>
<g fill="#111214" font-family="IBM Plex Sans, sans-serif" font-size="23">
<text x="24" y="42" font-size="30" font-weight="600">Only 3 holdout decisions</text>
<text x="24" y="78">No predictive edge established</text>
<text x="24" y="118" fill="#52545A" font-size="20">Retrospective policy comparison · cutoff 2026-10-21</text>
<text x="24" y="162" fill="#52545A">Policy</text>
<text x="590" y="162" text-anchor="end" fill="#52545A">Holdout MAE (bp)</text>
<path d="M24 176H660" stroke="#C6C7BF"/>
''' + '\n'.join(lines) + '''
<text x="24" y="516" font-size="20">*mNAV is hindsight-scaled; daily notice closes may leak.</text>
<text x="24" y="548" font-size="20">Models and split were chosen after observing history.</text>
<text x="24" y="590" font-size="20" fill="#52545A">Source: results/fit.json · filings + market-price proxies</text>
<text x="24" y="624" font-size="20" fill="#52545A">Rahil Bhavan · Independent research</text>
</g></svg>
'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'assets/holdout.svg'
    svg = render()
    if args.check:
        if path.read_text() != svg:
            raise SystemExit('Result figure is stale; run python scripts/result_figure.py')
        print('Result figure matches results/fit.json: assets/holdout.svg')
    else:
        path.parent.mkdir(exist_ok=True)
        path.write_text(svg)

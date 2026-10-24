"""Draw STRC's filed rate resets against its daily price and write the reset-history table.

Reads only the frozen snapshot (run scripts/snapshot.py first). Every rate is re-extracted from its cached filing
by strc.history.load(), and the $99 to $100 band is checked against the cached 8-K text on every run.

    python3 scripts/reset_figure.py          (rewrite assets/resets.svg and the table in docs/reset-history.md)
    python3 scripts/reset_figure.py --check  (fail if either is stale)
"""
import argparse
import datetime as dt
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from strc.data import yahoo_bars  # noqa: E402
from strc.features import AS_OF, decisions  # noqa: E402
from strc.history import load  # noqa: E402
from strc.text import doc_text, edgar_url  # noqa: E402

FIGURE = ROOT / "assets/resets.svg"
TABLE_DOC = ROOT / "docs" / "reset-history.md"
START, END = "<!-- reset-table:start -->", "<!-- reset-table:end -->"
OBJECTIVE_DOC = "000105044626000036-mstr-20260730x8kxex991.htm"
OBJECTIVE = "Our objective is for STRC to trade over time at $99 to $100."
BAND = (99.0, 100.0)

INK, GRAY, RULE, SURFACE, ACCENT = "#111214", "#52545A", "#C6C7BF", "#F5F5EF", "#FFE500"
W, H = 960, 820
X0, X1 = 76, 846
PRICE_Y, PRICE_LO, PRICE_HI = (150, 380), 70.0, 102.0
RATE_Y, RATE_LO, RATE_HI = (448, 628), 8.5, 12.5


def objective_url():
    if OBJECTIVE not in doc_text(OBJECTIVE_DOC).replace("\n", " "):
        raise SystemExit(f"objective sentence not found in {OBJECTIVE_DOC}")
    return edgar_url(OBJECTIVE_DOC)


def accession(url):
    digits = re.search(r"/data/\d+/(\d{18})/", url).group(1)
    return f"{digits[:10]}-{digits[10:12]}-{digits[12:]}"


def resets():
    """One row per filed announcement, joined to the price the stated tiers measure for that notice."""
    measured = {d.notice: d for d in decisions()}
    rows = []
    for a in load():
        d = measured.get(a.notice)
        rows.append({"notice": a.notice, "start": a.start, "end": a.end, "rate": a.rate, "change_bp": a.change_bp,
                     "kind": "pending" if a.regime == "daily_proposed" else a.kind, "url": a.source_url,
                     "vwap": d.vwap if d else None, "window": d.window if d else None,
                     "tier_bp": d.framework_bp if d else None})
    return rows


def closes():
    return [(b.date, b.close) for b in yahoo_bars("STRC") if b.date <= AS_OF]


def summary(rows):
    made = [r for r in rows if r["kind"] in ("increase", "hold")]
    raised = [r for r in made if r["kind"] == "increase"]
    holds = [r for r in made if r["kind"] == "hold"]
    in_band = [r for r in holds if r["vwap"] >= BAND[0]]
    below = [r for r in holds if r["vwap"] < BAND[0]]
    return {"decisions": len(made), "raised": len(raised), "holds": len(holds), "in_band": in_band, "below": below,
            "first": rows[0]["rate"], "last": made[-1]["rate"]}


def headline(s):
    return (f"Strategy raised STRC's rate in {s['raised']} of {s['decisions']} decisions, "
            f"{s['first']:.2f}% to {s['last']:.2f}%")


def fmt_day(d):
    return f"{d:%b} {d.day}, {d.year}"


def svg(rows, prices, objective):
    s = summary(rows)
    if s["holds"] != len(s["in_band"]) + len(s["below"]) or not s["in_band"] or not s["below"]:
        raise SystemExit("hold annotations no longer describe the data; revise the figure text")
    shown = [r for r in rows if r["kind"] != "pending"]
    day0, day1 = shown[0]["start"], shown[-1]["end"] + dt.timedelta(days=1)

    def x(d):
        return X0 + (X1 - X0) * (d - day0).days / (day1 - day0).days

    def py(v):
        return PRICE_Y[1] - (PRICE_Y[1] - PRICE_Y[0]) * (v - PRICE_LO) / (PRICE_HI - PRICE_LO)

    def ry(v):
        return RATE_Y[1] - (RATE_Y[1] - RATE_Y[0]) * (v - RATE_LO) / (RATE_HI - RATE_LO)

    def text(px, pyy, body, size=18, fill=INK, anchor="start", weight=None):
        w = f' font-weight="{weight}"' if weight else ""
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        return f'<text x="{px:.1f}" y="{pyy:.1f}" font-size="{size}" fill="{fill}"{a}{w}>{html.escape(body)}</text>'

    out = [f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>',
           text(24, 44, headline(s), 28, weight="600"),
           text(24, 78, "The rate resets each month. Strategy's stated tiers raise it when the price is below $99", 19,
                GRAY),
           text(24, 102, "and expect no change from $99 to $100.99. Rate steps sit on the dates each rate starts.", 19,
                GRAY),
           text(24, 138, "STRC daily close, $ per share (axis starts at $70)", 18, GRAY)]

    lo, hi = py(BAND[1]), py(BAND[0])
    out.append(f'<rect x="{X0}" y="{lo:.1f}" width="{X1 - X0}" height="{hi - lo:.1f}" fill="{RULE}"/>')
    out.append(text(x(dt.date(2025, 8, 4)), lo - 10, "Company objective, $99 to $100", 18, GRAY))
    for v in (70, 80, 90, 100):
        out.append(text(X0 - 10, py(v) + 6, f"${v}", 18, GRAY, "end"))
    out.append(f'<path d="M{X0} {PRICE_Y[0]}V{PRICE_Y[1]}" stroke="{RULE}"/>')
    pts = " ".join(f"{x(d):.1f},{py(v):.1f}" for d, v in prices)
    out.append(f'<polyline points="{pts}" fill="none" stroke="{INK}" stroke-width="2" stroke-linejoin="round"/>')
    low_day, low = min(prices, key=lambda p: p[1])
    out.append(text(x(low_day) + 10, py(low) + 6, f"${low:.2f} on {fmt_day(low_day)}", 18))
    end_day, end = prices[-1]
    out.append(text(X1 + 8, py(end) + 22, f"${end:.2f}", 18))
    out.append(text(X1 + 8, py(end) + 40, f"{end_day:%b} {end_day.day}", 18, GRAY))

    key_y = RATE_Y[0] - 30
    out += [text(24, key_y, "Dividend rate, % per year (axis starts at 8.5%)", 18, GRAY),
            f'<circle cx="532" cy="{key_y - 6}" r="6" fill="{ACCENT}" stroke="{INK}" stroke-width="1.5"/>',
            text(544, key_y, "raised, change in bp", 18, GRAY),
            f'<circle cx="752" cy="{key_y - 6}" r="5.5" fill="{SURFACE}" stroke="{INK}" stroke-width="1.5"/>',
            text(764, key_y, "held", 18, GRAY)]
    for v in (9, 10, 11, 12):
        out.append(text(X0 - 10, ry(v) + 6, f"{v}%", 18, GRAY, "end"))
    out.append(f'<path d="M{X0} {RATE_Y[0]}V{RATE_Y[1]}" stroke="{RULE}"/>')
    step = f"M{x(shown[0]['start']):.1f} {ry(shown[0]['rate']):.1f}"
    for r in shown:
        step += f"V{ry(r['rate']):.1f}H{x(r['end'] + dt.timedelta(days=1)):.1f}"
    out.append(f'<path d="{step}" fill="none" stroke="{INK}" stroke-width="2"/>')
    out.append(text(x(shown[0]["start"]) + 4, ry(shown[0]["rate"]) + 24, f"{shown[0]['rate']:.2f}% at issue", 18))
    for r in shown:
        cx, cy = x(r["start"]), ry(r["rate"])
        if r["kind"] == "increase":
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{ACCENT}" stroke="{INK}" stroke-width="1.5"/>')
            label = f"+{r['change_bp']:.0f}" + (" bp" if r is shown[1] else "")
            out.append(text(cx, cy - 12, label, 18, anchor="middle"))
        elif r["kind"] == "hold":
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="{SURFACE}" stroke="{INK}" '
                       'stroke-width="1.5"/>')
    out.append(text(X1 + 8, ry(s["last"]) + 6, f"{s['last']:.2f}%", 18))

    band_holds, low_holds = s["in_band"], s["below"]
    tiers = sorted({r["tier_bp"] for r in low_holds})
    out.append(text(x(band_holds[0]["start"]) - 6, ry(band_holds[0]["rate"]) + 26,
                    f"{len(band_holds)} holds with the price in the band", 18, anchor="start"))
    hx = x(low_holds[0]["start"]) - 14
    out += [text(hx, ry(10.3), f"{len(low_holds)} holds with the price", 18, anchor="start"),
            text(hx, ry(10.3) + 20, f"below $99, where the tiers", 18, anchor="start"),
            text(hx, ry(10.3) + 40, f"called for +{tiers[0]:.0f} to +{tiers[-1]:.0f} bp", 18, anchor="start")]

    year_ticks = [dt.date(y, m, 1) for y, m in ((2025, 8), (2025, 11), (2026, 2), (2026, 5), (2026, 8),
                                                (2026, 11))]
    out.append(f'<path d="M{X0} {RATE_Y[1] + 8}H{X1}" stroke="{RULE}"/>')
    for d in year_ticks:
        out.append(f'<path d="M{x(d):.1f} {RATE_Y[1] + 8}v6" stroke="{GRAY}"/>')
        label = f"{d:%b} {d.year}" if d in (year_ticks[0], year_ticks[2]) else f"{d:%b}"
        out.append(text(x(d), RATE_Y[1] + 32, label, 18, GRAY, "middle"))

    pending = next(r for r in rows if r["kind"] == "pending")
    last_filing = shown[-1]["notice"]
    out += [text(24, 704, f"Rates: {len({r['url'] for r in shown})} SEC filings, {fmt_day(shown[0]['notice'])} to "
                 f"{fmt_day(last_filing)}, each linked in docs/reset-history.md.", 18, GRAY),
            text(24, 728, f"Objective: 8-K exhibit 99.1, Jul 30, 2026 ({accession(objective)}).", 18, GRAY),
            text(24, 752, f"Price: Yahoo daily close (secondary data) to {fmt_day(prices[-1][0])}.", 18, GRAY),
            text(24, 776, f"Not shown: the {pending['start']:%b %Y} rate, pending the Oct 28, 2026 vote.", 18, GRAY),
            text(24, 800, "scripts/reset_figure.py · Rahil Bhavan · Independent research", 18, GRAY)]

    held = ", ".join(f"{r['start']:%b %Y}" for r in band_holds + low_holds)
    desc = (f"Two panels on one time axis, {fmt_day(day0)} to {fmt_day(shown[-1]['end'])}. Top: STRC daily close "
            f"against the company's $99 to $100 objective, falling to ${low:.2f} on {fmt_day(low_day)} and "
            f"ending at ${end:.2f}. Bottom: the filed dividend rate, raised {s['raised']} times from "
            f"{s['first']:.2f}% to {s['last']:.2f}% and held {s['holds']} times ({held}).")
    title = headline(s)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
            'aria-labelledby="title desc">\n'
            f'<title id="title">{html.escape(title)}</title>\n<desc id="desc">{html.escape(desc)}</desc>\n'
            '<g font-family="IBM Plex Sans, sans-serif">\n' + "\n".join(out) + "\n</g></svg>\n")


def table(rows, objective):
    def change(r):
        if r["kind"] == "initial":
            return "at issue"
        if r["kind"] == "carry":
            return "carried, not a decision"
        if r["kind"] == "pending":
            return "pending vote, excluded"
        return "held" if r["change_bp"] == 0 else f"+{r['change_bp']:.0f} bp"

    def price(r):
        return "n/a" if r["vwap"] is None else f"${r['vwap']:.2f} ({'5-day' if r['window'] == '5d' else 'month'})"

    def tier(r):
        return "n/a" if r["tier_bp"] is None else ("no change" if r["tier_bp"] == 0 else f"+{r['tier_bp']:.0f} bp")

    lines = [START, "<details>", "<summary>Every reset in the chart, with its filing</summary>", "",
             "| Notice | Rate period | Rate | Change | Measured price | Stated tier | SEC filing |",
             "|---|---|--:|---|--:|---|---|"]
    for r in rows:
        lines.append(f"| {r['notice']} | {r['start']} to {r['end']} | {r['rate']:.2f}% | {change(r)} | {price(r)} | "
                     f"{tier(r)} | [{accession(r['url'])}]({r['url']}) |")
    lines += ["",
              "Measured price is a daily typical-price VWAP proxy over the window the stated tiers name. Stated tier is "
              "the minimum change those tiers recommend. The $99 to $100 objective is from "
              f"[8-K exhibit 99.1, {accession(objective)}]({objective}). Generated by `scripts/reset_figure.py`.",
              "", "</details>", END]
    return "\n".join(lines)


def with_table(text, block):
    head, sep, rest = text.partition(START)
    _, sep2, tail = rest.partition(END)
    if not (sep and sep2):
        raise SystemExit(f"docs/reset-history.md is missing the {START} ... {END} markers")
    return head + block + tail


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="fail if the figure or reset table is stale")
    args = parser.parse_args()
    rows, objective = resets(), objective_url()
    figure = svg(rows, closes(), objective)
    readme = TABLE_DOC.read_text()
    new_readme = with_table(readme, table(rows, objective))
    if args.check:
        stale = [p.name for p, new, old in ((FIGURE, figure, FIGURE.read_text() if FIGURE.exists() else ""),
                                            (TABLE_DOC, new_readme, readme)) if new != old]
        if stale:
            raise SystemExit(f"Stale: {', '.join(stale)}; run python3 scripts/reset_figure.py")
        print("Reset figure and docs/reset-history.md table match the cached filings: assets/resets.svg")
        return
    FIGURE.write_text(figure)
    TABLE_DOC.write_text(new_readme)
    print("Wrote assets/resets.svg and the docs/reset-history.md table")


if __name__ == "__main__":
    main()

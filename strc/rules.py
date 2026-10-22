"""STRC reset rules, encoded from the certificates of designations, and the company's stated framework.

Contract (binding) versus framework (stated intention) are kept separate:

* `contract_floor` / `clamp` encode the "Monthly Regular Dividend Rate Per Annum" (original) and
  "Regular Dividend Rate Per Annum" (amended and restated) definitions. A new rate cannot be
  (i) negative, (ii) below the prior rate minus 25 bp minus any decline in Monthly SOFR over a
  look-back window, or (iii) below Monthly SOFR on the business day before the notice. A
  reduction is allowed only if all accumulated dividends are paid. Increases are uncapped.
* `framework_change_bp` encodes the "Dividend Adjustment Framework" price tiers, which the
  company calls its current intention, subject to change in its sole discretion.

Sources (cached in data/raw/edgar):
  original CoD  https://www.sec.gov/Archives/edgar/data/1050446/000119312525167987/d43815dex31.htm
  A&R CoD       https://www.sec.gov/Archives/edgar/data/1050446/000119312526270366/d144149dex31.htm
  proposed 2nd A&R CoD (Annex in the Oct 5, 2026 proxy; vote Oct 28, 2026; not yet in force)
                https://www.sec.gov/Archives/edgar/data/1050446/000119312526413159/d503578ddef14a.htm
  framework     https://www.sec.gov/Archives/edgar/data/1050446/000095017025100916/mstr-ex99_1.htm (2025-07-31)
                https://www.sec.gov/Archives/edgar/data/1050446/000119312525190363/d18414d8k.htm (2025-08-28)
                https://www.sec.gov/Archives/edgar/data/1050446/000105044626000012/mstr-20260205.htm (2026-02-05)
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

STEP_BP = 25.0
SOFR_PROXY_NOTE = ("Monthly SOFR in the contract is CME One-Month Term SOFR, which is licensed. This project "
                   "uses NY Fed overnight SOFR as a proxy; differences are not bounded here.")


def _month_add(d: dt.date, n: int) -> dt.date:
    y, m = divmod(d.month - 1 + n, 12)
    return dt.date(d.year + y, m + 1, 1)


def _month_end(d: dt.date) -> dt.date:
    return _month_add(d, 1) - dt.timedelta(days=1)


@dataclass(frozen=True)
class Regime:
    name: str
    effective: dt.date   # first rate period governed by this version
    source: str


REGIMES = {
    "original": Regime("original", dt.date(2025, 7, 29),
                       "https://www.sec.gov/Archives/edgar/data/1050446/000119312525167987/d43815dex31.htm"),
    "semi_monthly": Regime("semi_monthly", dt.date(2026, 6, 30),
                           "https://www.sec.gov/Archives/edgar/data/1050446/000119312526270366/d144149dex31.htm"),
    "daily_proposed": Regime("daily_proposed", dt.date(2026, 11, 1),
                             "https://www.sec.gov/Archives/edgar/data/1050446/000119312526413159/d503578ddef14a.htm"),
}


def sofr_window(regime: str, period_start: dt.date) -> tuple[dt.date, dt.date]:
    """Calendar span whose Monthly SOFR decline loosens the reduction cap for a rate period.

    original:       the rate period is a calendar month M; window = month M-1 (the preceding period).
    semi_monthly:   the rate period runs from the 16th of M to the 15th of M+1; the window runs from the first
                    business day of the 3rd preceding semi-monthly period (1st-15th of M-1) to the last business
                    day of the 2nd preceding one (16th-end of M-1), i.e. calendar month M-1.
    daily_proposed: the rate period is calendar month M; window = the 2nd calendar month preceding, M-2.
    """
    if regime == "original":
        a = _month_add(period_start.replace(day=1), -1)
    elif regime == "semi_monthly":
        if period_start.day != 16:
            raise ValueError("semi-monthly rate periods start on the 16th")
        a = _month_add(period_start.replace(day=1), -1)
    elif regime == "daily_proposed":
        a = _month_add(period_start.replace(day=1), -2)
    else:
        raise KeyError(regime)
    return a, _month_end(a)


def notice_deadline(regime: str, period_start: dt.date, business_days: list[dt.date]) -> dt.date:
    """Last calendar day on which notice of a new rate can be given for a period."""
    if regime == "daily_proposed":
        return _month_add(period_start.replace(day=1), -1).replace(day=15)   # "on or before the 15th"
    anchor = period_start.replace(day=1)          # original: the period itself; A&R: the 1st-15th period before it
    first_bd = min(d for d in business_days if d >= anchor)
    return first_bd - dt.timedelta(days=1)       # "before the first Business Day"


def sofr_decline(sofr: dict[dt.date, float], window: tuple[dt.date, dt.date]) -> float:
    """Excess of SOFR on the window's first business day over the window minimum, in percent (>= 0)."""
    days = sorted(d for d in sofr if window[0] <= d <= window[1])
    if not days:
        raise ValueError(f"no SOFR observations in {window}")
    return max(0.0, sofr[days[0]] - min(sofr[d] for d in days))


def contract_floor(prev_rate: float, sofr_decline_pct: float, sofr_before_notice: float) -> float:
    """Lowest rate (percent) the company may set for the next period."""
    return max(0.0, prev_rate - (STEP_BP / 100 + sofr_decline_pct), sofr_before_notice)


@dataclass(frozen=True)
class Clamped:
    rate: float
    floor: float
    bound: str   # "none", "reduction_cap", "sofr_floor", "arrears"


def clamp(proposed: float, prev_rate: float, sofr_decline_pct: float, sofr_before_notice: float,
          arrears_paid: bool = True) -> Clamped:
    """Apply the contract to a proposed rate. Increases always pass."""
    if proposed >= prev_rate:
        return Clamped(proposed, contract_floor(prev_rate, sofr_decline_pct, sofr_before_notice), "none")
    if not arrears_paid:
        return Clamped(prev_rate, prev_rate, "arrears")
    floor = contract_floor(prev_rate, sofr_decline_pct, sofr_before_notice)
    if proposed >= floor:
        return Clamped(proposed, floor, "none")
    cap = prev_rate - (STEP_BP / 100 + sofr_decline_pct)
    return Clamped(floor, floor, "sofr_floor" if sofr_before_notice >= cap else "reduction_cap")


# ---- the company's stated framework ---------------------------------------------------------------

FRAMEWORK_VERSIONS = [
    # (first notice it applies to, measurement window, tiers as (lower bound of VWAP, change in bp))
    (dt.date(2025, 7, 31), "5d", "https://www.sec.gov/Archives/edgar/data/1050446/000095017025100916/mstr-ex99_1.htm"),
    (dt.date(2025, 8, 28), "5d", "https://www.sec.gov/Archives/edgar/data/1050446/000119312525190363/d18414d8k.htm"),
    (dt.date(2026, 2, 5), "month", "https://www.sec.gov/Archives/edgar/data/1050446/000105044626000012/mstr-20260205.htm"),
]


def framework_window(notice: dt.date) -> str:
    """'5d': VWAP of the five trading days before the month's last trading day. 'month': VWAP for the month."""
    kind = "5d"
    for start, k, _ in FRAMEWORK_VERSIONS:
        if notice >= start:
            kind = k
    return kind


def framework_change_bp(vwap: float) -> float:
    """Minimum change the stated framework recommends for a measured VWAP.

    Below $95: +50 bp or more. $95.00-$98.99: +25 bp (or more, from Aug 28, 2025). $99.00-$100.99: no change
    anticipated (management may move 25 bp either way). $101.00 and above: -25 bp, or more if SOFR fell, subject
    to the contract cap.
    """
    if vwap < 95.0:
        return 50.0
    if vwap < 99.0:
        return 25.0
    if vwap < 101.0:
        return 0.0
    return -25.0

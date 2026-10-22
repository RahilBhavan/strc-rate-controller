"""STRC rate announcements, each tied to the cached filing that states it.

`ANNOUNCEMENTS` names the filing and a phrase; `load()` re-reads the cached filing text and extracts
the rate, so the table is checked against the source on every run (see tests/test_history.py).
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from .text import doc_text, edgar_url

D = dt.date.fromisoformat


@dataclass(frozen=True)
class Spec:
    notice: str        # date the company announced the rate
    start: str         # first day the rate accrues
    end: str           # last day of the announced period
    doc: str           # cached filing document (data/raw/edgar/<doc>)
    pattern: str       # regex whose group(1) is the new rate in percent
    kind: str          # "initial", "increase", "hold", "carry" (contractual carry-forward, not a decision)
    regime: str        # reset-rule version in force for this period (see strc/rules.py)
    note: str = ""


ANNOUNCEMENTS = [
    Spec("2025-07-29", "2025-07-29", "2025-08-31", "000119312525167987-d43815dex31.htm",
         r"Initial Issue Date, a rate per annum equal to nine percent \((\d+\.\d+)%\)", "initial", "original",
         "Certificate of designations; IPO priced 2025-07-24 at $90."),
    Spec("2025-08-31", "2025-09-01", "2025-09-30", "000119312525193487-d80677d8k.htm",
         r"from 9\.00% to (\d+\.\d+)% effective for monthly periods commencing on or after September 1, 2025",
         "increase", "original"),
    Spec("2025-09-30", "2025-10-01", "2025-10-31", "000119312525225038-d939712d8k.htm",
         r"from 10\.00% to (\d+\.\d+)% effective for monthly periods commencing on or after October 1, 2025",
         "increase", "original"),
    Spec("2025-10-30", "2025-11-01", "2025-11-30", "000119312525258690-mstr-20251030.htm",
         r"from 10\.25% to (\d+\.\d+)% effective for monthly periods commencing on or after November 1, 2025",
         "increase", "original"),
    Spec("2025-11-30", "2025-12-01", "2025-12-31", "000119312525303157-d69948d8k.htm",
         r"December 1, 2025 from 10\.50% to (\d+\.\d+)%", "increase", "original"),
    Spec("2025-12-31", "2026-01-01", "2026-01-31", "000119312526000264-mstr-20251117.htm",
         r"January 1, 2026 from 10\.75% to (\d+\.\d+)%", "increase", "original"),
    Spec("2026-01-31", "2026-02-01", "2026-02-28", "000119312526032731-mstr-20260131.htm",
         r"February 1, 2026 from 11\.00% to (\d+\.\d+)%", "increase", "original"),
    Spec("2026-02-28", "2026-03-01", "2026-03-31", "000119312526084264-mstr-20260228.htm",
         r"March 1, 2026 from 11\.25% to (\d+\.\d+)%", "increase", "original"),
    Spec("2026-03-31", "2026-04-01", "2026-04-30", "000119312526135765-mstr-20250902.htm",
         r"on or after April 1, 2026 at (\d+\.\d+)%", "hold", "original"),
    Spec("2026-04-30", "2026-05-01", "2026-05-31", "000119312526199155-mstr-20250902.htm",
         r"on or after May 1, 2026 at (\d+\.\d+)%", "hold", "original"),
    Spec("2026-05-31", "2026-06-01", "2026-06-30", "000119312526249768-mstr-20260530.htm",
         r"on or after June 1, 2026 at (\d+\.\d+)%", "hold", "original"),
    Spec("2026-06-15", "2026-07-01", "2026-07-15", "000119312526270366-d144149d8k.htm",
         r"semi-monthly period ending July 15, 2026 represents a per annum dividend rate of (\d+\.\d+)%",
         "carry", "semi_monthly",
         "Transition half-month: the amended certificate carries the June rate into Jul 1-15."),
    Spec("2026-06-29", "2026-07-16", "2026-08-15", "000119312526286871-mstr-20260629.htm",
         r"record dates on or after July 1, 2026, to (\d+\.\d+)%", "increase", "semi_monthly"),
    Spec("2026-07-31", "2026-08-16", "2026-09-15", "000119312526329565-mstr-20260803.htm",
         r"on or after August 16, 2026 at (\d+\.\d+)%", "hold", "semi_monthly"),
    Spec("2026-08-31", "2026-09-16", "2026-10-15", "000119312526377583-mstr-20260831.htm",
         r"on or after September 16, 2026 at (\d+\.\d+)%", "hold", "semi_monthly"),
    Spec("2026-09-30", "2026-10-16", "2026-11-15", "000119312526409863-mstr-20260930.htm",
         r"on or after October 16, 2026 at (\d+\.\d+)%", "hold", "semi_monthly"),
    Spec("2026-10-15", "2026-11-01", "2026-11-30", "000119312526423400-mstr-20261015.htm",
         r"November 1, 2026 through November 30, 2026 will be (\d+\.\d+)%", "hold", "daily_proposed",
         "Contingent on the Oct 28, 2026 special meeting approving daily dividends."),
]


@dataclass(frozen=True)
class Announcement:
    notice: dt.date
    start: dt.date
    end: dt.date
    rate: float        # percent per annum
    prev_rate: float | None
    kind: str
    regime: str
    source_url: str
    quote: str
    note: str

    @property
    def change_bp(self) -> float | None:
        return None if self.prev_rate is None else round((self.rate - self.prev_rate) * 100, 6)


def load() -> list[Announcement]:
    out: list[Announcement] = []
    prev = None
    for s in ANNOUNCEMENTS:
        text = doc_text(s.doc).replace("\n", " ")
        m = re.search(s.pattern, text)
        if not m:
            raise ValueError(f"rate phrase not found in {s.doc}: {s.pattern}")
        rate = float(m.group(1))
        out.append(Announcement(D(s.notice), D(s.start), D(s.end), rate, prev, s.kind, s.regime,
                                edgar_url(s.doc), m.group(0), s.note))
        prev = rate
    return out


def rate_on(day: dt.date, anns: list[Announcement] | None = None) -> float:
    """Announced rate accruing on a given day."""
    anns = [a for a in (anns or load()) if a.regime != "daily_proposed"]
    for a in anns:
        if a.start <= day <= a.end:
            return a.rate
    if day < anns[0].start:
        raise ValueError("before STRC issuance")
    raise ValueError("outside unconditional announced periods; supply a scenario explicitly")

"""Load cached market data into simple Python structures (no pandas)."""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from .fetch import RAW

NY = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class Bar:
    date: dt.date
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def typical(self) -> float:
        return (self.high + self.low + self.close) / 3


def yahoo_bars(symbol: str) -> list[Bar]:
    """Daily bars from the cached Yahoo chart response. Rows with a missing close are dropped."""
    res = json.loads((RAW / "prices" / f"yahoo-{symbol}.json").read_text())["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    tz = ZoneInfo(res["meta"]["exchangeTimezoneName"])  # BTC-USD bars are stamped 00:00 UTC
    out = []
    for i, ts in enumerate(res["timestamp"]):
        if q["close"][i] is None:
            continue
        d = dt.datetime.fromtimestamp(ts, tz).date()
        out.append(Bar(d, q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i] or 0.0))
    return out


def yahoo_meta(symbol: str) -> dict:
    return json.loads((RAW / "prices" / f"yahoo-{symbol}.json.meta.json").read_text())


def sofr() -> dict[dt.date, float]:
    """Overnight SOFR, percent, by effective date (NY Fed)."""
    d = json.loads((RAW / "rates" / "nyfed-sofr.json").read_text())
    return {dt.date.fromisoformat(r["effectiveDate"]): r["percentRate"] for r in d["refRates"]}


def sofr_on(series: dict[dt.date, float], day: dt.date) -> float:
    """Latest published SOFR on or before day."""
    best = max(d for d in series if d <= day)
    return series[best]


def strategy_snapshot(endpoint: str, date: str = "2026-10-21") -> dict:
    d = json.loads((RAW / "strategy" / f"{endpoint}-{date}.json").read_text())
    return d[0] if isinstance(d, list) else d["results"]


def vwap(bars: list[Bar]) -> float:
    """Volume-weighted typical price. A proxy: true VWAP needs intraday trades."""
    v = sum(b.volume for b in bars)
    if v <= 0:
        raise ValueError("no volume in window")
    return sum(b.typical * b.volume for b in bars) / v

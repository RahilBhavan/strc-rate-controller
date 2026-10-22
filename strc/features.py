"""One row per rate decision: what the controller could see at notice time."""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, asdict

from . import rules
from .data import Bar, sofr, sofr_on, strategy_snapshot, vwap, yahoo_bars
from .history import Announcement, load

AS_OF = dt.date(2026, 10, 20)   # last full Yahoo bar for STRC in the cached pull


@dataclass(frozen=True)
class Decision:
    notice: dt.date
    period_start: dt.date
    prev_rate: float
    rate: float
    change_bp: float
    window: str          # "5d" or "month"
    vwap: float          # framework-window VWAP proxy
    gap: float           # 100 - vwap, dollars
    close: float         # STRC close on or before the notice
    btc_ret_1m: float    # log return of BTC over the month to notice
    mnav_proxy: float    # MSTR/BTC ratio scaled to Strategy's mNAV on 2026-10-21 (see mnav_proxy())
    sofr: float
    framework_bp: float  # the stated framework's minimum recommendation for this VWAP
    regime: str
    source_url: str

    def row(self) -> dict:
        d = asdict(self)
        return {k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in d.items()}


def bars_upto(bars: list[Bar], day: dt.date) -> list[Bar]:
    return [b for b in bars if b.date <= day]


def window_bars(bars: list[Bar], notice: dt.date, kind: str) -> list[Bar]:
    """Trading days the framework measures for a notice date."""
    if kind == "5d":
        month = [b for b in bars if b.date <= notice and (b.date.year, b.date.month) == (notice.year, notice.month)]
        return month[-6:-1]                     # the 5 days before the month's last trading day
    start = notice.replace(day=1) - dt.timedelta(days=1)      # "VWAP for the month": the month that ends at the notice
    return [b for b in bars if start < b.date <= notice]


def close_on(series: dict[dt.date, float], day: dt.date) -> float:
    return series[max(d for d in series if d <= day)]


def mnav_proxy_series() -> tuple[dict[dt.date, float], dict]:
    """mNAV proxy: Strategy's own mNAV on 2026-10-21 scaled by the MSTR/BTC price ratio.

    Assumes a constant BTC per share and constant debt and preferred; both drifted over the sample, so the proxy
    is rougher the further back it goes. Strategy's mNAV is enterprise-value based and company-defined.
    """
    snap = strategy_snapshot("bitcoinKpis")
    mstr = strategy_snapshot("mstrKpiData")
    ratio_now = mstr["ufPrice"] / snap["ufPrice"]
    m = {b.date: b.close for b in yahoo_bars("MSTR")}
    btc = {b.date: b.close for b in yahoo_bars("BTC-USD")}
    out = {d: snap["mNav"] * (m[d] / close_on(btc, d)) / ratio_now for d in m}
    return out, {"mnav_2026_10_21": snap["mNav"], "mstr_price": mstr["ufPrice"], "btc_price": snap["ufPrice"]}


def decisions(anns: list[Announcement] | None = None) -> list[Decision]:
    anns = anns or load()
    strc = [b for b in yahoo_bars("STRC") if b.date <= AS_OF]
    btc = {b.date: b.close for b in yahoo_bars("BTC-USD")}
    S = sofr()
    mnav, _ = mnav_proxy_series()
    closes = {b.date: b.close for b in strc}
    out = []
    for a in anns:
        if a.kind in ("initial", "carry") or a.regime == "daily_proposed":
            continue
        kind = rules.framework_window(a.notice)
        w = window_bars(strc, a.notice, kind)
        v = vwap(w)
        out.append(Decision(
            a.notice, a.start, a.prev_rate, a.rate, a.change_bp, kind, v, 100 - v, close_on(closes, a.notice),
            math.log(close_on(btc, a.notice) / close_on(btc, a.notice - dt.timedelta(days=30))),
            close_on(mnav, a.notice), sofr_on(S, a.notice), rules.framework_change_bp(v), a.regime, a.source_url))
    return out

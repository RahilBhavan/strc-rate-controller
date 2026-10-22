"""Market-implied STRC yield and a BTC-driven credit spread model.

Implied yield (assumption: holders price STRC as a perpetual paying today's rate forever):
    y = rate x 100 / price            (percent; this is Strategy's "effective yield" definition)
Spread over the risk-free proxy (overnight SOFR):
    s = y - SOFR
Two candidate spread models, both driven by the BTC price B relative to the 1x-coverage price
B* = (debt + preferred notional) / BTC held (where BTC value just equals senior-plus-preferred claims):
    log:      s = a + b x ln(B / B*)
    distance: s = a + k / (B / B* - 1)      (spread grows without bound as B approaches B*)
B* is taken from Strategy's KPI API on 2026-10-21 and held fixed over the sample. That assumes the ratio of
liabilities to BTC held stayed constant; it did not exactly, so historical B / B* is approximate.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass

from .data import sofr, sofr_on, strategy_snapshot, yahoo_bars
from .features import AS_OF, close_on
from .fit import lstsq
from .history import load, rate_on


def coverage_point() -> dict:
    """B*: BTC price at which BTC holdings equal debt plus preferred notional (company figures, 2026-10-21)."""
    btc = strategy_snapshot("bitcoinKpis")
    mstr = strategy_snapshot("mstrKpiData")
    holdings = float(btc["btcHoldings"].replace(",", ""))
    debt = float(mstr["debt"].replace(",", "")) * 1e6
    pref = float(mstr["pref"].replace(",", "")) * 1e6
    return {"holdings_btc": holdings, "debt_usd": debt, "pref_usd": pref,
            "b_star": (debt + pref) / holdings, "btc_price": btc["ufPrice"],
            "debt_pref_by_bn_pct": btc["debtPrefByBN"],
            "source": "https://api.strategy.com/btc/bitcoinKpis and /btc/mstrKpiData, fetched 2026-10-21"}


@dataclass(frozen=True)
class Obs:
    date: dt.date
    price: float
    rate: float
    y: float
    sofr: float
    btc: float

    @property
    def spread(self) -> float:
        return self.y - self.sofr


def observations(until: dt.date = AS_OF) -> list[Obs]:
    anns = load()
    S = sofr()
    btc = {b.date: b.close for b in yahoo_bars("BTC-USD")}
    out = []
    for b in yahoo_bars("STRC"):
        if b.date > until:
            continue
        c = rate_on(b.date, anns)
        out.append(Obs(b.date, b.close, c, c * 100 / b.close, sofr_on(S, b.date), close_on(btc, b.date)))
    return out


def monthly(obs: list[Obs]) -> list[Obs]:
    """Month-end observations: lowers serial correlation for honest fit statistics."""
    last = {}
    for o in obs:
        last[(o.date.year, o.date.month)] = o
    return [last[k] for k in sorted(last)]


@dataclass(frozen=True)
class SpreadModel:
    form: str           # "log" or "distance"
    a: float
    b: float
    b_star: float

    def x(self, btc: float) -> float:
        r = btc / self.b_star
        if self.form == "log":
            return math.log(r)
        if r <= 1.0:
            return math.inf
        return 1.0 / (r - 1.0)

    def spread(self, btc: float) -> float:
        x = self.x(btc)
        return math.inf if math.isinf(x) else self.a + self.b * x


def fit_spread(obs: list[Obs], form: str, b_star: float) -> SpreadModel:
    m = SpreadModel(form, 0.0, 0.0, b_star)
    a, b = lstsq([[1.0, m.x(o.btc)] for o in obs], [o.spread for o in obs])
    return SpreadModel(form, a, b, b_star)


def stats(model: SpreadModel, obs: list[Obs]) -> dict:
    """Fit quality in spread points and in STRC price dollars (price implied = 100 x rate / (SOFR + s))."""
    es = [o.spread - model.spread(o.btc) for o in obs]
    ep = [o.price - 100 * o.rate / (o.sofr + model.spread(o.btc)) for o in obs]
    mean = sum(o.spread for o in obs) / len(obs)
    tss = sum((o.spread - mean) ** 2 for o in obs)
    return {"n": len(obs), "rmse_spread_pp": math.sqrt(sum(e * e for e in es) / len(es)),
            "r2": 1 - sum(e * e for e in es) / tss if tss else float("nan"),
            "rmse_price_usd": math.sqrt(sum(e * e for e in ep) / len(ep)),
            "max_abs_price_err_usd": max(abs(e) for e in ep)}

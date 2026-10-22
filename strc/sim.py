"""Closed-loop simulator: STRC price <- required yield <- BTC; rate <- controller(price), clamped by the contract.

Model (all assumptions, monthly steps):
  required yield   y_t = SOFR_t + s(B_t) + shock_t
  price            P_t = min(cap, 100 x c_t / y_t)     perpetual at the current rate; cap = $101 optional redemption
  controller       c_{t+1} = clamp(c_t + policy(P_t))   policy sees the month's price as its VWAP
  dividend cost    notional x c_t per year              notional held constant (buybacks and issuance ignored)
The spread slope comes from history (strc.credit); its level is anchored so that the model reproduces today's
observed implied yield (Strategy's "effective yield", 12.10% on 2026-10-21).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from . import rules
from .credit import SpreadModel

PAR_BAND = 99.0      # company objective: "for STRC to trade over time at $99 to $100" (Q2 2026 release)
PRICE_CAP = 101.0    # optional redemption price; the company also intends to issue only at $99-$101


def framework_policy(price: float, rate: float, y: float, sofr_decline: float) -> float:
    """Stated framework tiers; above $101 the framework allows the 25 bp cut plus any SOFR decline."""
    bp = rules.framework_change_bp(price)
    return bp - 100 * sofr_decline if bp < 0 else bp


def fast_policy(price: float, rate: float, y: float, sofr_decline: float) -> float:
    """Framework tiers with the largest observed monthly hike (+100 bp, Aug 31, 2025) below $95."""
    return 100.0 if price < 95.0 else framework_policy(price, rate, y, sofr_decline)


def hold_policy(price: float, rate: float, y: float, sofr_decline: float) -> float:
    """Post-July-2026 stated policy: keep 12.00% until sustained trading near $100 (cuts allowed above $101)."""
    return framework_policy(price, rate, y, sofr_decline) if price >= 101.0 else 0.0


def oracle_policy(price: float, rate: float, y: float, sofr_decline: float) -> float:
    """Benchmark: knows the required yield and moves straight to it. Only the contract can slow it down."""
    return 100 * (y - rate) if math.isfinite(y) else 0.0


POLICIES: dict[str, Callable[[float, float, float, float], float]] = {
    "framework": framework_policy, "framework_fast": fast_policy, "hold_12": hold_policy, "oracle": oracle_policy}


@dataclass
class Scenario:
    name: str
    btc_shock: float = 0.0             # fractional move applied at t=0 and held (-0.4 = BTC down 40%)
    spread_shock_pp: float = 0.0       # exogenous widening, percentage points, held
    sofr_path: list[float] | None = None   # SOFR by month; default flat at today's value
    policy: str = "framework"
    months: int = 24


@dataclass
class Path:
    scenario: Scenario
    rate: list[float] = field(default_factory=list)
    price: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    bound: list[str] = field(default_factory=list)
    months_to_par: int | None = None
    required_rate: float = math.nan
    saturated: bool = False

    def row(self, notional: float) -> dict:
        r = self.required_rate
        return {
            "scenario": self.scenario.name, "policy": self.scenario.policy,
            "horizon_months": self.scenario.months,
            "btc_shock_pct": round(self.scenario.btc_shock * 100, 1),
            "spread_shock_pp": self.scenario.spread_shock_pp,
            "required_rate_pct": None if math.isinf(r) else round(r, 3),
            "start_price": round(self.price[0], 2),
            "months_to_par_band": self.months_to_par,
            f"rate_after_{self.scenario.months}m_pct": round(self.rate[-1], 3),
            f"saturated_{self.scenario.months}m": self.saturated,
            "annual_cost_at_required_usd_m": None if math.isinf(r) else round(notional * r / 100 / 1e6, 1),
            f"annual_cost_at_{self.scenario.months}m_rate_usd_m": round(notional * self.rate[-1] / 100 / 1e6, 1),
            "months_reduction_cap_bound": sum(b == "reduction_cap" for b in self.bound),
            "months_sofr_floor_bound": sum(b == "sofr_floor" for b in self.bound),
            "months_paying_above_required": sum(c > y + 1e-9 for c, y in zip(self.rate[:-1], self.y[:-1])),
            "excess_dividends_usd_m": round(sum(max(0.0, c - y) for c, y in zip(self.rate[:-1], self.y[:-1])
                                                if math.isfinite(y)) / 100 * notional / 12 / 1e6, 1),
        }


def anchor(model: SpreadModel, btc0: float, sofr0: float, y0: float) -> SpreadModel:
    """Shift the intercept so that SOFR + s(btc0) equals the observed yield y0."""
    return SpreadModel(model.form, model.a + (y0 - sofr0 - model.spread(btc0)), model.b, model.b_star)


def required_rate(model: SpreadModel, btc: float, sofr: float, shock: float = 0.0) -> float:
    """Rate at which the modeled price equals $100 (= the required yield). Infinite at or below B*."""
    s = model.spread(btc)
    return math.inf if math.isinf(s) else sofr + s + shock


def run(sc: Scenario, model: SpreadModel, btc0: float, sofr0: float, rate0: float) -> Path:
    if (not -1 < sc.btc_shock or sc.months < 1 or sc.policy not in POLICIES
            or not all(math.isfinite(x) for x in (sc.btc_shock, sc.spread_shock_pp, btc0, sofr0, rate0))
            or btc0 <= 0 or rate0 < 0 or (sc.sofr_path is not None and
                (not sc.sofr_path or not all(math.isfinite(x) for x in sc.sofr_path)))):
        raise ValueError("invalid scenario inputs")
    policy = POLICIES[sc.policy]
    btc = btc0 * (1 + sc.btc_shock)
    sofr_path = sc.sofr_path or [sofr0] * (sc.months + 1)
    p = Path(sc)
    p.required_rate = required_rate(model, btc, sofr_path[0], sc.spread_shock_pp)
    c = rate0
    for t in range(sc.months + 1):
        sofr_t = sofr_path[min(t, len(sofr_path) - 1)]
        y = required_rate(model, btc, sofr_t, sc.spread_shock_pp)
        if y <= 0:
            raise ValueError("assumed required yield must be positive")
        price = 0.0 if math.isinf(y) else min(PRICE_CAP, 100 * c / y)
        p.rate.append(c)
        p.price.append(price)
        p.y.append(y)
        if p.months_to_par is None and price >= PAR_BAND:
            p.months_to_par = t
        if t == sc.months:
            break
        # SOFR decline over the look-back month (first value minus the minimum); flat paths give zero.
        decline = max(0.0, sofr_path[min(max(0, t - 1), len(sofr_path) - 1)] - sofr_t)
        proposed = c + policy(price, c, y, decline) / 100
        cl = rules.clamp(proposed, c, decline, sofr_t)
        p.bound.append(cl.bound)
        c = cl.rate
    p.saturated = p.months_to_par is None
    return p


def breakeven_drawdown(model: SpreadModel, btc0: float, sofr0: float, target_rate: float) -> float | None:
    """BTC move (fraction) at which the required rate reaches target_rate. None if never on (-100%, 0]."""
    lo, hi = -0.999, 0.0
    f = lambda x: required_rate(model, btc0 * (1 + x), sofr0) - target_rate  # noqa: E731
    if f(hi) >= 0:
        return 0.0
    if not math.isinf(f(lo)) and f(lo) < 0:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        v = f(mid)
        if math.isinf(v) or v > 0:
            lo = mid
        else:
            hi = mid
    return hi


def months_needed(required: float, rate0: float, policy: str = "framework", cap_months: int = 600) -> int | None:
    """Months for the policy to lift the rate from rate0 until the price reaches the par band (no BTC change)."""
    if math.isinf(required):
        return None
    c = rate0
    for t in range(cap_months + 1):
        price = min(PRICE_CAP, 100 * c / required)
        if price >= PAR_BAND:
            return t
        c += POLICIES[policy](price, c, required, 0.0) / 100
    return None

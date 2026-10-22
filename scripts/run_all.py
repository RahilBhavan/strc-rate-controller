"""Rebuild every derived table and result from the cached raw data.

Run: python3 scripts/run_all.py
Writes data/derived/*.csv and results/*.json. Reads only data/raw/ (no network).

One custom stress, printed only (no files written):
    python3 scripts/run_all.py --btc-shock -40 --spread-shock 100
"""
import argparse
import csv
import datetime as dt
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from strc import credit, evaluation, fit, rules, sim  # noqa: E402
from strc.data import sofr, strategy_snapshot  # noqa: E402
from strc.features import AS_OF, decisions, mnav_proxy_series  # noqa: E402
from strc.history import load  # noqa: E402

DER = ROOT / "data" / "derived"
RES = ROOT / "results"
STRATEGY_API = "https://api.strategy.com/btc/strcKpiData (fetched 2026-10-21)"


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def dump(name, obj):
    RES.mkdir(exist_ok=True)
    (RES / name).write_text(json.dumps(obj, indent=1, default=str) + "\n")


def framework_consistent(d) -> bool:
    """Within the stated framework, reading "or more" and the $99-$100.99 discretion literally."""
    if d.vwap < 95:
        return d.change_bp >= 50
    if d.vwap < 99:
        return d.change_bp >= 25 if d.notice >= dt.date(2025, 8, 28) else d.change_bp == 25
    if d.vwap < 101:
        return abs(d.change_bp) <= 25
    return d.change_bp <= -25


SLOPE_MULTIPLIERS = (0.5, 1.0, 1.5)
BTC_SHOCK_RANGE_PCT = (-95.0, 400.0)
SPREAD_SHOCK_RANGE_BP = (-500.0, 2000.0)


def shock_rows(models, btc0, sofr0, y0, rate0, notional, btc_shock, spread_pp=0.0, name="custom"):
    """Framework-policy stress for each spread form and assumed slope multiplier, reanchored to today's yield."""
    out = []
    for form, m in models.items():
        for slope_multiplier in SLOPE_MULTIPLIERS:
            am = sim.anchor(credit.SpreadModel(form, m.a, m.b * slope_multiplier, m.b_star), btc0, sofr0, y0)
            path = sim.run(sim.Scenario(name, btc_shock=btc_shock, spread_shock_pp=spread_pp), am, btc0, sofr0, rate0)
            out.append({"form": form, "assumed_slope_multiplier": slope_multiplier, **path.row(notional)})
    return out


def stress_setup(obs, cp):
    """Full-sample month-end spread models plus today's anchors (rate, price, BTC, SOFR, notional)."""
    mo = credit.monthly(obs)
    models = {form: credit.fit_spread(mo, form, cp["b_star"]) for form in ("log", "distance")}
    snap = strategy_snapshot("strcKpiData")
    rate0 = snap["currentDividend"]
    return {"models": models, "btc0": cp["btc_price"], "sofr0": sofr()[max(sofr())],
            "y0": rate0 * 100 / snap["ufPrice"], "rate0": rate0, "notional": float(snap["notional"])}


def bounded(name, lo, hi):
    def parse(text):
        try:
            value = float(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{name} must be a number, got {text!r}") from None
        if not (math.isfinite(value) and lo <= value <= hi):
            raise argparse.ArgumentTypeError(f"{name} must be between {lo:g} and {hi:g}, got {text}")
        return value
    return parse


def fmt(value, spec, missing="n/a"):
    return missing if value is None else format(value, spec)


def print_custom(btc_pct, spread_bp):
    st = stress_setup(credit.observations(), credit.coverage_point())
    rows = shock_rows(st["models"], st["btc0"], st["sofr0"], st["y0"], st["rate0"], st["notional"],
                      btc_pct / 100, spread_bp / 100)
    print(f"Assumed stress: BTC {btc_pct:+g}% (${st['btc0']:,.0f} to ${st['btc0'] * (1 + btc_pct / 100):,.0f}), "
          f"spread {spread_bp:+g} bp, stated-tier policy, 24 months.")
    print(f"Start: rate {st['rate0']:.2f}%, SOFR {st['sofr0']:.2f}%, market data through {AS_OF}.")
    print(f"{'spread form':<11} {'slope x':>7} {'required rate':>13} {'price':>7} {'months to $99':>13} "
          f"{'annual cost':>12}")
    for r in rows:
        rate = r["required_rate_pct"]
        print(f"{r['form']:<11} {r['assumed_slope_multiplier']:>7g} "
              f"{'unbounded' if rate is None else f'{rate:.3f}%':>13} "
              f"{r['start_price']:>7.2f} {fmt(r['months_to_par_band'], 'd', '>24'):>13} "
              f"{fmt(r['annual_cost_at_required_usd_m'], ',.0f'):>8} $m")
    if any(r["required_rate_pct"] is None for r in rows):
        b_star = next(iter(st["models"].values())).b_star
        print(f"unbounded: BTC at or below the ${b_star:,.0f} coverage price, where the distance form has no "
              "finite yield.")
    print("Assumptions, not forecasts: fitted spread slopes, fixed notional, $101 price ceiling, "
          "discretionary resets.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--btc-shock", metavar="PCT", type=bounded("--btc-shock", *BTC_SHOCK_RANGE_PCT),
                        help="BTC move in percent, applied at t=0 and held (e.g. -40)")
    parser.add_argument("--spread-shock", metavar="BP", type=bounded("--spread-shock", *SPREAD_SHOCK_RANGE_BP),
                        help="extra required-yield spread in basis points, held (e.g. 200)")
    args = parser.parse_args()
    if args.btc_shock is not None or args.spread_shock is not None:
        try:
            print_custom(args.btc_shock or 0.0, args.spread_shock or 0.0)
        except ValueError as exc:
            parser.exit(2, f"run_all.py: error: {exc} (the shock makes the assumed required yield invalid)\n")
        return
    anns = load()
    write_csv(DER / "announcements.csv", [{
        "notice_date": a.notice, "rate_start": a.start, "rate_end": a.end, "rate_pct": a.rate,
        "change_bp": a.change_bp, "kind": a.kind, "rule_version": a.regime, "source_url": a.source_url,
        "quote": a.quote, "note": a.note} for a in anns])

    rows = decisions(anns)
    write_csv(DER / "decisions.csv", [r.row() | {"framework_consistent": framework_consistent(r)} for r in rows])

    obs = credit.observations()
    mnav, mnav_meta = mnav_proxy_series()
    write_csv(DER / "daily.csv", [{
        "date": o.date, "strc_close": round(o.price, 4), "rate_pct": o.rate, "implied_yield_pct": round(o.y, 4),
        "sofr_pct": o.sofr, "spread_pp": round(o.spread, 4), "btc_close": round(o.btc, 2),
        "mnav_proxy": round(mnav.get(o.date, math.nan), 4)} for o in obs])

    # ---- fit ----------------------------------------------------------------------------------
    dump("evaluation.json", evaluation.chronological_report(rows))
    ev = fit.evaluate(rows)
    pre = [r for r in rows if r.notice < fit.BREAK]
    post = [r for r in rows if r.notice >= fit.BREAK]
    dump("fit.json", {
        "n_decisions": len(rows), "n_pre_break": len(pre), "n_post_break": len(post),
        "break": fit.BREAK, "actual_bp": [r.change_bp for r in rows],
        "framework_consistent": {"pre": sum(map(framework_consistent, pre)),
                                 "post": sum(map(framework_consistent, post))},
        "rules": ev})

    # ---- credit model ---------------------------------------------------------------------------
    cp = credit.coverage_point()
    split = dt.date(2026, 4, 1)
    mo = credit.monthly(obs)
    cres = {"coverage_point": cp, "split": split, "n_daily": len(obs), "n_month_end": len(mo), "models": {}}
    models = {}
    for form in ("log", "distance"):
        tr = [o for o in mo if o.date < split]
        te = [o for o in mo if o.date >= split]
        m_tr = credit.fit_spread(tr, form, cp["b_star"])
        m_full = credit.fit_spread(mo, form, cp["b_star"])
        d_full = credit.fit_spread(obs, form, cp["b_star"])
        models[form] = m_full
        cres["models"][form] = {
            "month_end_full": {"a": m_full.a, "b": m_full.b, **credit.stats(m_full, mo)},
            "month_end_train_to_2026_03": {"a": m_tr.a, "b": m_tr.b, **credit.stats(m_tr, tr)},
            "month_end_test_from_2026_04": credit.stats(m_tr, te),
            "daily_full": {"a": d_full.a, "b": d_full.b, **credit.stats(d_full, obs)},
        }
    dump("credit.json", cres)

    # ---- simulator ------------------------------------------------------------------------------
    snap = strategy_snapshot("strcKpiData")
    notional = float(snap["notional"])
    sofr0 = sofr()[max(sofr())]
    btc0 = cp["btc_price"]
    rate0 = snap["currentDividend"]
    y0 = rate0 * 100 / snap["ufPrice"]
    out = {"inputs": {
        "notional_usd": notional, "notional_source": STRATEGY_API, "rate0_pct": rate0, "strc_price0": snap["ufPrice"],
        "implied_yield0_pct": y0, "strategy_eff_yield_pct": snap["effYield"], "btc0": btc0, "sofr0_pct": sofr0,
        "sofr_date": max(sofr()), "b_star": cp["b_star"], "coverage_btc_price_usd": cp["b_star"],
        "coverage_btc_price_note": "b_star: BTC price at which BTC holdings equal debt plus preferred notional",
        "as_of": "2026-10-21",
        "strategy_duration": snap.get("duration"), "model_duration_1_over_y": 100 / y0},
        "scenarios": {}, "required_rate_grid": {}, "breakevens": {}}
    scenarios = [
        sim.Scenario("base"),
        sim.Scenario("btc_-20", btc_shock=-0.2), sim.Scenario("btc_-40", btc_shock=-0.4),
        sim.Scenario("btc_-60", btc_shock=-0.6),
        sim.Scenario("spread_+200bp", spread_shock_pp=2.0), sim.Scenario("spread_+400bp", spread_shock_pp=4.0),
        sim.Scenario("btc_-40_hold12", btc_shock=-0.4, policy="hold_12"),
        sim.Scenario("btc_-40_fast", btc_shock=-0.4, policy="framework_fast"),
        sim.Scenario("btc_+50_framework", btc_shock=0.5),
        sim.Scenario("btc_+50_oracle", btc_shock=0.5, policy="oracle"),
        sim.Scenario("btc_+50_sofr_-150bp_oracle", btc_shock=0.5, policy="oracle",
                     sofr_path=[sofr0 - min(t, 6) * 0.25 for t in range(25)]),
    ]
    for form, m in models.items():
        am = sim.anchor(m, btc0, sofr0, y0)
        rows_out, paths = [], {}
        for sc in scenarios:
            p = sim.run(sc, am, btc0, sofr0, rate0)
            rows_out.append(p.row(notional))
            paths[sc.name] = {"rate": p.rate, "price": p.price}
        grid = []
        for k in range(0, 76, 5):
            x = -k / 100
            r = sim.required_rate(am, btc0 * (1 + x), sofr0)
            grid.append({"btc_move_pct": -k, "btc": round(btc0 * (1 + x)),
                         "required_rate_pct": None if math.isinf(r) else round(r, 3),
                         "annual_strc_cost_usd_m": None if math.isinf(r) else round(notional * r / 100 / 1e6, 1),
                         "months_to_par_framework": sim.months_needed(r, rate0, "framework")})
        be = {f"rate_{t}pct": sim.breakeven_drawdown(am, btc0, sofr0, t) for t in (13, 15, 20, 25, 30)}
        be["coverage_1x_move"] = cp["b_star"] / btc0 - 1
        out["scenarios"][form] = rows_out
        out["required_rate_grid"][form] = grid
        out["breakevens"][form] = be
        out.setdefault("anchored_models", {})[form] = {"a": am.a, "b": am.b, "b_star": am.b_star}
        out.setdefault("paths", {})[form] = paths
    out["status"] = "Assumed stress responses; no causal identification or default probability"
    out["btc_minus40_sensitivity"] = shock_rows(models, btc0, sofr0, y0, rate0, notional, -0.4,
                                                name="btc_-40_sensitivity")
    # README stress table: every BTC shock across forms and assumed slope multipliers (scripts/readme_table.py).
    out["btc_shock_sensitivity"] = [row for shock in (-0.2, -0.4, -0.6)
                                    for row in shock_rows(models, btc0, sofr0, y0, rate0, notional, shock,
                                                          name=f"btc_{round(shock * 100):+d}_sensitivity")]
    dump("scenarios.json", out)
    print(f"announcements {len(anns)}, decisions {len(rows)}, daily obs {len(obs)}, as of {AS_OF}")


if __name__ == "__main__":
    main()

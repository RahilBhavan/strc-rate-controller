"""Dated, retrospective policy comparisons; no prospective forecasting claim."""
from __future__ import annotations

import math
from dataclasses import replace
from statistics import median

from .features import Decision
from .fit import BREAK, RULES, Rule, snap

BASELINES = [
    Rule("prior-change", 0, lambda rows: None, lambda p, r, h: h[-1].change_bp,
         "Repeat the most recent observed change, updating after each notice."),
    Rule("historical-median", 1, lambda rows: median(r.change_bp for r in rows),
         lambda p, r, h: p, "Median change in the fitting prefix; frozen in fixed holdout."),
]


def _status(name):
    if name in ("hold", "prior-change", "historical-median"):
        return "Prior dated outcomes only; policy chosen retrospectively."
    if name == "proportional+mNAV":
        return "Hindsight-scaled to 2026-10-21 mNAV; not point-in-time."
    return "Notice-close daily proxies; intraday availability unverified."


def _summary(ledger):
    errors = [r["absolute_error_bp"] for r in ledger]
    deltas = [r["error_minus_hold_bp"] for r in ledger]
    n = len(errors)
    total = sum(errors)
    omitted = [(total - e) / (n - 1) for e in errors] if n > 1 else []
    return {
        "n": n, "mae_bp": total / n,
        "raw_mae_bp": sum(abs(r["raw_pred_bp"] - r["actual_bp"]) for r in ledger) / n,
        "exact": sum(e == 0 for e in errors),
        "mae_minus_hold_bp": sum(deltas) / n,
        "wins_vs_hold": sum(d < 0 for d in deltas),
        "ties_vs_hold": sum(d == 0 for d in deltas),
        "losses_vs_hold": sum(d > 0 for d in deltas),
        "losing_notice_dates": [r["notice_date"] for r in ledger if r["error_minus_hold_bp"] > 0],
        "omit_one_date_mae_range_bp": [min(omitted), max(omitted)] if omitted else None,
    }


def _policy(rule, rows, start, expanding):
    frozen = rule.fit(rows[:start])
    ledger = []
    for i in range(start, len(rows)):
        train = rows[:i] if expanding else rows[:start]
        params = rule.fit(train) if expanding else frozen
        target = rows[i]
        # Predictors need features and past outcomes, never the target outcome.
        features = replace(target, change_bp=0.0, rate=target.prev_rate)
        raw = rule.predict(params, features, rows[:i])
        if not math.isfinite(raw):
            raise ValueError(f"nonfinite prediction for {rule.name} at {target.notice}")
        predicted = snap(raw)
        error = abs(predicted - target.change_bp)
        ledger.append({
            "notice_date": target.notice.isoformat(), "source_url": target.source_url,
            "fit_n": len(train), "fit_through": train[-1].notice.isoformat(),
            "history_n": i, "history_through": rows[i - 1].notice.isoformat(),
            "params": params, "actual_bp": target.change_bp,
            "raw_pred_bp": raw, "pred_bp": predicted,
            "absolute_error_bp": error, "hold_absolute_error_bp": abs(target.change_bp),
            "error_minus_hold_bp": error - abs(target.change_bp),
        })
    return {"policy": rule.name, "description": rule.description,
            "feature_status": _status(rule.name), "summary": _summary(ledger), "ledger": ledger}


def chronological_report(rows: list[Decision]) -> dict:
    """Validate an ordered decision-table boundary and compare identical scored dates.

    Fixed holdout freezes fit parameters; past holdout outcomes enter subsequent
    prediction history. Expanding replay refits only on the prefix before target.
    """
    if any(a.notice >= b.notice for a, b in zip(rows, rows[1:])):
        raise ValueError("decision notice dates must be unique and strictly increasing")
    if any(r.regime == "daily_proposed" for r in rows):
        raise ValueError("conditional decisions cannot enter evaluation")
    if any(not math.isfinite(v) for r in rows for v in
           (r.change_bp, r.gap, r.btc_ret_1m, r.mnav_proxy, r.framework_bp)):
        raise ValueError("evaluation features and outcomes must be finite")
    start = sum(r.notice < BREAK for r in rows)
    if start < 6 or start == len(rows):
        raise ValueError("need at least six pre-break decisions and a nonempty holdout")
    splits = [("fixed_holdout", start, False)] + [
        (f"expanding_{n}", n, True) for n in (6, 8, 10) if n < len(rows)]
    return {
        "schema_version": 1, "financial_as_of": "2026-10-21", "n_decisions": len(rows),
        "break_date": BREAK.isoformat(), "n_holdout": len(rows) - start,
        "interpretation": "Retrospective diagnostics; no predictive edge established.",
        "protocol": {
            "fixed_holdout": "Fit before break, freeze parameters; update observed history after each notice.",
            "expanding": "Refit on all strictly earlier decisions; overlapping windows are not replications.",
            "rounding": "25 bp nearest grid; Python ties-to-even. Raw MAE also reported.",
            "omit_one_date": "Remove each scored error without refitting; range is not a confidence interval.",
            "constraints": "Unclamped descriptive changes; filed constraints remain in rules.py.",
            "selection": "Split, candidate policies and sensitivity choices made after observing history.",
            "availability": "Chronological targets do not remove feature leakage or establish intraday availability.",
        },
        "splits": [{"name": name, "initial_training_n": n,
                    "policies": [_policy(rule, rows, n, expanding) for rule in [*RULES, *BASELINES]]}
                   for name, n, expanding in splits],
    }

"""Candidate reset policies, fitted to the decision table and scored honestly.

There are 14 unconditional decisions (Aug 2025 to Sep 2026 notices). Every rule is scored three ways:
  * in-sample on the 11 decisions before the July 2026 policy change ("pre-break"),
  * leave-one-out (LOO) on those 11, refitting the parameters each time,
  * out-of-sample on the 3 decisions from Jul 31, 2026 on, with parameters fitted on the 11.
Predictions are rounded to the 25 bp grid the company has always used before scoring "exact".
"""
from __future__ import annotations

import datetime as dt
import itertools
from dataclasses import dataclass
from typing import Callable

from .features import Decision

BREAK = dt.date(2026, 7, 30)   # Q2 results (Jul 30, 2026): "maintain the 12.00% rate until STRC demonstrates
                              # sustained, healthy trading near $100" and STRC buybacks begin


def lstsq(X: list[list[float]], y: list[float], ridge: float = 0.0) -> list[float]:
    """Ordinary least squares by normal equations (Gauss-Jordan). Small k only."""
    k = len(X[0])
    A = [[sum(r[i] * r[j] for r in X) + (ridge if i == j else 0.0) for j in range(k)] for i in range(k)]
    b = [sum(r[i] * t for r, t in zip(X, y)) for i in range(k)]
    M = [row + [bi] for row, bi in zip(A, b)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12:
            raise ValueError("singular design matrix")
        M[c], M[p] = M[p], M[c]
        for r in range(k):
            if r != c:
                f = M[r][c] / M[c][c]
                M[r] = [a - f * bb for a, bb in zip(M[r], M[c])]
    return [M[i][k] / M[i][i] for i in range(k)]


def snap(bp: float) -> float:
    return 25.0 * round(bp / 25.0)


@dataclass
class Rule:
    name: str
    n_params: int
    fit: Callable[[list[Decision]], object]
    predict: Callable[[object, Decision, list[Decision]], float]   # (params, row, history before row) -> bp
    description: str


def _cum_gap(hist: list[Decision]) -> float:
    return sum(d.gap for d in hist)


def _linear(features: Callable[[Decision, list[Decision]], list[float]]):
    def fit(rows):
        X = [features(r, rows[:i]) for i, r in enumerate(rows)]
        return lstsq(X, [r.change_bp for r in rows])

    def predict(p, r, hist):
        return sum(a * b for a, b in zip(p, features(r, hist)))
    return fit, predict


def _threshold_fit(rows):
    grid = [x / 4 for x in range(-8, 61)]          # gap thresholds from -$2 to +$15 in $0.25 steps
    best = None
    for t1, t2 in itertools.combinations(grid, 2):
        err = sum(abs(_threshold_pred((t1, t2), r, []) - r.change_bp) for r in rows)
        key = (err, t1, t2)
        if best is None or key < best:
            best = key
    return best[1:]


def _threshold_pred(p, r, hist):
    t1, t2 = p
    return 25.0 * (r.gap > t1) + 25.0 * (r.gap > t2)


RULES = [
    Rule("hold", 0, lambda rows: None, lambda p, r, h: 0.0, "Never change the rate."),
    Rule("framework", 0, lambda rows: None, lambda p, r, h: r.framework_bp,
         "Strategy's stated tiers, minimum recommendation (no fitted parameters)."),
    Rule("proportional", 1, *_linear(lambda r, h: [r.gap]), "change_bp = kp x (100 - VWAP)."),
    Rule("proportional+bias", 2, *_linear(lambda r, h: [1.0, r.gap]), "change_bp = b + kp x (100 - VWAP)."),
    Rule("PI", 2, *_linear(lambda r, h: [r.gap, _cum_gap(h)]),
         "change_bp = kp x gap + ki x sum of past gaps (integral term)."),
    Rule("proportional+BTC", 2, *_linear(lambda r, h: [r.gap, r.btc_ret_1m]),
         "change_bp = kp x gap + kb x 1-month BTC log return."),
    Rule("proportional+mNAV", 2, *_linear(lambda r, h: [r.gap, r.mnav_proxy - 1.0]),
         "change_bp = kp x gap + km x (mNAV proxy - 1)."),
    Rule("threshold", 2, _threshold_fit, _threshold_pred,
         "+25 bp when gap > t1, another +25 bp when gap > t2; thresholds fitted on a $0.25 grid."),
]


def score(rule: Rule, rows: list[Decision], params=None) -> dict:
    """Score a rule. If params is None the rule is fitted on rows (in-sample)."""
    p = rule.fit(rows) if params is None else params
    preds = [rule.predict(p, r, rows[:i]) for i, r in enumerate(rows)]
    return _metrics(rows, preds) | {"params": p}


def _metrics(rows, preds):
    errs = [snap(p) - r.change_bp for p, r in zip(preds, rows)]
    return {
        "n": len(rows),
        "mae_bp": sum(abs(e) for e in errs) / len(rows),
        "exact": sum(e == 0 for e in errs),
        "pred_bp": [round(snap(p), 1) for p in preds],
        "raw_pred_bp": [round(p, 2) for p in preds],
    }


def loo(rule: Rule, rows: list[Decision]) -> dict:
    preds = []
    for i, r in enumerate(rows):
        train = rows[:i] + rows[i + 1:]
        p = rule.fit(train)
        preds.append(rule.predict(p, r, rows[:i]))
    return _metrics(rows, preds)


def evaluate(all_rows: list[Decision]) -> list[dict]:
    pre = [r for r in all_rows if r.notice < BREAK]
    post = [r for r in all_rows if r.notice >= BREAK]
    out = []
    for rule in RULES:
        ins = score(rule, pre)
        oos_preds = [rule.predict(ins["params"], r, all_rows[:len(pre) + i]) for i, r in enumerate(post)]
        out.append({
            "rule": rule.name, "description": rule.description, "n_params": rule.n_params,
            "params": ins["params"],
            "in_sample": {k: ins[k] for k in ("n", "mae_bp", "exact", "pred_bp")},
            "expanding_replay": _metrics(all_rows[6:], [rule.predict(rule.fit(all_rows[:i]), r, all_rows[:i])
                for i, r in enumerate(all_rows) if i >= 6]),
            "loo": {k: v for k, v in loo(rule, pre).items() if k != "raw_pred_bp"},
            "post_break": {k: v for k, v in _metrics(post, oos_preds).items() if k != "raw_pred_bp"},
        })
    return out

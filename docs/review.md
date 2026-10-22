# Correctness review and remaining limits

Scope: existing Python CLI v1 at `5d32e24`, including frozen sources and optional fetch helpers. Applied code-reviewer's prove-then-fix workflow. Baseline: 18 tests passed. Swept correctness, error handling, security, accessibility (CLI/static figure), performance, dead code and project conventions. No measured performance defect, reachable injection or private source artifact was established. No code was removed as dead merely because another repository might consume it.

## Fixed and proven

- `strc/sim.py`: `Scenario('short', sofr_path=[4])` crashed at month 2 because only the current SOFR lookup was extended. Prior-month lookup now holds the final value too. Regression compares the short path with 25 explicit constant observations.
- `strc/sim.py`: holding 12% against 11.9% required yield on $1.2bn for 24 months reported $2.5m excess instead of $2.4m. Cost and paying-month counts now exclude the terminal observation. The failing $2.5m result was observed before the fix.
- `strc/rules.py`: `clamp(4, 3, 0, 5)` returned 4 despite the elected-rate SOFR floor of 5. The certificate restricts an elected different rate, not just reductions. Regression now returns 5, preserves unchanged carry at 3, and permits an increase with arrears. Increases still have no ceiling. This is a proxy implementation, not legal compliance certification.
- `strc/sim.py`: a one-month scenario used `24m` result labels. Custom horizons now carry `horizon_months` and matching field names; default 24-month keys remain intact. Regression proved the missing horizon label first.

Each fix was followed by the full suite. Final suite: 26 tests, including source hashes, parsing, temporal exclusion of conditional declarations, holdout-target perturbation, invalid scenarios, fetch cache reuse, retry after HTTP 429, and failure without a false success file after HTTP 403.

## Evaluation evidence added

`results/fit.json` exposes dated holdout predictions, actual changes, per-observation absolute errors and expanding-replay initial-size sensitivity (6/8/10). These are retrospective diagnostics. The 3 holdout observations all hold rates; the zero-error hold baseline does not prove a forecasting edge. Candidate policies, breakpoint and evaluation design were chosen after seeing the data. mNAV is a hindsight-scaled ratio; same-day closes and SOFR effective dates do not establish intraday availability. No prospective-clean feature set is claimed.

The frozen daily-dividend declaration stays conditional and excluded. BTC -40% paths, slope multipliers, fixed capital structure and price ceiling are assumptions. No causal, calibrated-default or security-certification claim is made. Full legal calendar, term SOFR, point-in-time balance sheets and actual funding/arrears checks remain outside scope.

## Independent review

One T3 read-only reviewer completed the scout. It supplied the elected-rate floor and horizon-label cases above, confirmed all 770 archive members were regular source bodies or metadata in expected directories, and raised the third-party rights limitation now recorded in `sources.md`. No extra agents or sibling edits were used.

## Next

A longer, point-in-time sample is required before any prospective forecasting evaluation.

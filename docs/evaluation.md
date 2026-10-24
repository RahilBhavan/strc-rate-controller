# Auditable chronological policy comparison

Implemented 2026-10-22 on the unchanged frozen financial snapshot (cutoff
2026-10-21; market bars end 2026-10-20). No observations were added. This is a
retrospective comparison of discretionary changes in basis points, not investment
performance or a prospective policy validation.

## Five-minute offline example

From a clone, Python 3.12+ and standard library only:

```bash
python3 scripts/snapshot.py
python3 scripts/run_all.py
python3 scripts/evaluate_policies.py --policy framework
python3 scripts/evaluate_policies.py --split expanding_6 --policy prior-change
python3 scripts/validate.py
python3 scripts/result_figure.py --check
```

The first command restores the hash-verified cache; none needs credentials or a
network. `results/evaluation.json` contains the full report and is intentionally
ignored by Git. The print command recomputes from frozen inputs rather than
trusting a possibly stale JSON. Invalid split/policy arguments exit 2 via argparse.
Local verification (re-run 2026-10-24): 45 tests passed; seven output hashes matched
across two full demo runs. Exact hashes are in validation.md/json.

## Protocol and output

The same ten policies are scored on the same dates: eight existing candidates,
plus prior-change (repeat the immediately preceding observed change) and
historical-median (median of fitting outcomes). Hold always proposes zero change.
These simple baselines require only prior dated outcomes. They are still chosen
retrospectively, so their performance does not prove an edge.

Fixed holdout fits on eleven notices strictly before 2026-07-30 and freezes those
parameters. The ledger scores July 31, August 31 and September 30, 2026. History
updates after each scored notice, so prior-change can use the July outcome to
predict August. This is sequential one-step evaluation, not a three-step forecast
issued at the split. Historical-median remains frozen throughout fixed holdout.
Expanding replay refits at each notice using only its preceding prefix. Initial
sizes 6/8/10 yield 8/6/4 scored dates; these overlap and are not replications.

Every ledger row carries the notice source URL, actual outcome, full-precision raw
prediction, 25 bp snapped prediction, absolute error, fitting count/cutoff,
parameters, and history count/cutoff. Date order must be strictly increasing and
unique. Conditional decisions, nonfinite evaluation inputs and insufficient
training/holdout samples fail explicitly. Prediction receives masked current
outcome fields. Tests perturb current/future outcomes, assert frozen holdout fits,
and reproduce the old eight policies' holdout and replay predictions exactly.

Summaries report raw and snapped MAE, exact matches, and paired wins/ties/losses
against hold. Positive `mae_minus_hold_bp` means worse than hold. All losing dates
are retained, including losses by fitted candidates. Rounding uses Python's
nearest 25 bp with ties-to-even; raw MAE exposes dependence on that choice.
`omit_one_date_mae_range_bp` removes each scored error once without refitting and
reports the min/max remaining MAE. It is a sample-composition sensitivity, not
leave-one-out fitting, a confidence interval or additional observations. A
single scored observation has no such range (`null`). No policy is auto-selected.

## Measured losing cases and limits

All three holdout outcomes are zero. Hold MAE is 0 bp; prior-change 16.67 bp;
historical-median 25 bp; stated-tier proxy 33.33 bp. The stated-tier proxy proposes
50/25/25 bp against zero and loses on all three dates. Its omit-one-date MAE range
is 25–37.5 bp. Prior-change loses July 31 after the preceding 50 bp increase,
then matches the next two holds. In expanding replay from six observations,
hold MAE is 9.375 bp and prior-change is 15.625 bp, with losses on March 31 and
July 31. These are errors on the frozen dataset, not claims about future behavior.

Chronological training prevents later targets from fitting earlier predictions;
it cannot repair covariate availability. Daily notice-close features may postdate
an intraday decision. Historical mNAV uses MSTR/BTC scaled to the company's
2026-10-21 mNAV, with fixed capital-structure assumptions; it is explicitly
hindsight-scaled, not reconstructed point in time. Candidate models, breakpoint,
rounding and sensitivity choices were made after observing history. There are
only fourteen unconditional decisions and three holdout observations, all holds.
A longer sample with dated information-availability records and historical
capital structure is the unresolved input for prospective validation.

Predictions remain unclamped descriptive proposals. Filed reduction restrictions
in `rules.py` and discretionary price-tier guidance remain distinct. The overnight
SOFR substitute cannot certify term-SOFR contractual compliance. No statutory,
contractual or simulated stress behavior was changed.

## Evidence and provenance

Primary pages reopened on 2026-10-22, without replacing the frozen cache:

- [Strategy's July 30, 2026 results](https://www.strategy.com/press/strategy-announces-second-quarter-2026-financial-results_07-30-2026),
  Digital Credit Capital Framework Summary: states an intention to maintain 12%
  pending sustained trading near par. This supports the existing retrospective
  breakpoint; it does not make the split a pre-registered forecast.
- [Amended certificate](https://www.sec.gov/Archives/edgar/data/1050446/000119312526270366/d144149dex31.htm),
  Regular Dividend Rate Per Annum definition: discretionary election of a different
  rate subject to nonnegative/reduction/SOFR restrictions and dividend conditions.
  This supports retaining the distinction between guidance and constraints.

Dated notice sources are attached to each prediction; fetched dates and SHA-256
inventories remain in `provenance/sources-*.csv`. See [sources.md](sources.md) for
Yahoo's secondary daily bars and snapshot rights/coverage. Web pages were read as
evidence only; no new vendor bodies, quotes or datasets were added to Git.

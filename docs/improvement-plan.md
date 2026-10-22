# Chronological policy evaluation improvement

Scope authorized 2026-10-22: add an auditable, retrospective comparison to simple
policies using only the existing fourteen dated unconditional decisions. Initial
checkout was clean at d8ab6a1; baseline: 26 tests pass. Read AGENTS.md, CLAUDE.md,
DESIGN.md, README, spec, methodology, sources and review. This repo has no glossary
or ADR directory; those terms and decisions live in the existing methodology.

Done conditions:

1. An offline JSON report contains all eight existing policies plus prior-change
   and historical-median baselines on identical dates: the fixed 11/3 split and
   expanding windows starting at 6, 8 and 10. No observations are added.
2. Every prediction records notice/source, actual, raw and snapped prediction,
   error, fitting cutoff/count and observed-history cutoff/count. Fitting and
   history strictly precede the target. Reject unordered/duplicate dates and
   unusable samples; current outcome fields are masked before prediction.
3. Every policy reports paired wins/ties/losses against hold, all losing dates,
   raw versus 25 bp rounded MAE, and leave-one-date-out MAE ranges (sensitivity,
   not confidence intervals). Never choose a winner or claim predictive edge.
4. Perturbation tests prove current/future outcomes do not affect earlier
   predictions and fixed holdout parameters do not change. Real-source tests
   reconstruct summary metrics and verify the three holdout dates.
5. Document a five-minute offline example, measured results and source review;
   pass full source/tests/repeated-output/figure/build checks, commit, push and
   inspect the resulting CI.

Non-goals: point-in-time market reconstruction, new data, prospective forecasts,
contract changes, visual changes, portfolio returns or statistical significance.
The existing mNAV feature remains hindsight-scaled; notice-close availability is
unverified. Candidate policies and the split are retrospective. Filed restrictions
remain separate from discretionary guidance; predictions are not clamped into a
claim of compliance. Existing fit.json and SVG behavior stays stable.

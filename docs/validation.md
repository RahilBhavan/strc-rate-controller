# Offline validation evidence

Financial cutoff: 2026-10-21; market bars through 2026-10-20. Local validation uses Python 3.14.7 and only the standard library. No NumPy or sibling environment is needed.

```bash
python3 scripts/snapshot.py
python3 scripts/validate.py
python3 scripts/result_figure.py --check
python3 -m compileall -q strc scripts tests
```

Observed: 26 tests passed; 385 source bodies matched the committed inventory; 6 CSV/JSON output hashes matched across two identical demos. Exact hashes and interpreter are in [validation.json](validation.json). Floating-point output identity is measured within an environment, not guaranteed across Python/platform versions.

The CI workflow pins checkout/setup-python by full commit SHA and Python 3.12.12/3.14.7 on Ubuntu 24.04, with read-only repository permissions. After runtime setup, checks are offline: snapshot restoration, source verification, real behavior tests, repeated demo hashes, result-figure freshness and byte compilation. Python is dynamically typed; compilation is not claimed as static typechecking.

Clean-copy and fresh-clone commands/results are recorded in [publication.md](publication.md). Tests cover fetch cache replay, bounded retry on HTTP 429, nonretryable HTTP 403, invalid input, conditional declarations, holdout targets, proxy restrictions and stress behavior. They do not certify issuer data or actual contractual compliance. The pre-commit hook remains enabled and rejects any staged file above 20,000 bytes (5,000 estimated tokens).

`assets/holdout.svg` is generated from actual `results/fit.json` with `scripts/result_figure.py`. It was rendered in the T3 browser at desktop and phone widths. Typography uses IBM Plex Sans when available and a sans-serif fallback; no font binaries are bundled. The table uses the Rahil light figure palette, plain numeric cells and visible sample/leakage caveats. No investment edge is claimed.

# Publication receipt

Target: https://github.com/RahilBhavan/strc-rate-controller. Financial snapshot: 2026-10-21; market bars through 2026-10-20. Source review started from `5d32e24` and preserves its ancestry. Public creation/push is explicitly authorized for this project only.

Status: local review and clean-copy verification complete; remote publication and CI verification pending.

A cold copy under `~/scratch/strc-rate-controller/clean-copy` restored the archive, passed all 26 tests, ran the demo twice and matched all six working-tree output hashes. Intentional corruption of a source body and of an archive part was rejected with integrity errors. No pre-existing raw cache, generated outputs or installed dependency environment was copied.

Local evidence: 26 passing tests; 385 source hashes verified; 17 parsed announcements, 14 unconditional decisions and 309 daily observations; six generated output hashes repeat. Commands: `python3 scripts/snapshot.py`, `python3 scripts/validate.py`, `python3 scripts/result_figure.py --check`, `python3 -m compileall -q strc scripts tests`.

The reachable-history/source inspection is recorded in [publication-safety.json](publication-safety.json). No credential-pattern hits, oversized blobs or unexpected archive members were found. Manual inspection covered source metadata, tracked paths, history, contacts and binary archive contents. Full third-party redistribution rights are not certified; [sources.md](sources.md) records that limit. No code license was invented.

The result figure was rendered at 720px and 400px in T3. It uses a numeric table because the eight errors are lookup values, not a shape claim. Browser fallback fonts were used; no font redistribution is involved. Figure integrity: no area/length encoding, no implied confidence interval, explicit tiny-sample and leakage warnings. Agent visual review found no clipping or collisions; no independent human reader test was performed.

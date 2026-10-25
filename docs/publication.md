# Publication receipt

Target: https://github.com/RahilBhavan/strc-rate-controller. Financial snapshot: 2026-10-21; market bars through 2026-10-20. Source review started from `5d32e24` and preserves its ancestry. Public creation/push is explicitly authorized for this project only.

Dated receipt: test counts below describe the commits named here, not the current suite (45 tests on 2026-10-24).

Status: published publicly; default branch `main`. Verified source commit: `2a4f8fed6edcca13d66a26ba1db8305d06093a5e`, descended from `5d32e24`. Remote `refs/heads/main` matched the intended local commit. The subsequent receipt/badge commit changes documentation only; its hash is available with `git log -1 -- docs/publication.md`.

[GitHub Actions run 39718405905](https://github.com/RahilBhavan/strc-rate-controller/actions/runs/39718405905) passed on Python 3.12.12 and 3.14.7, including source verification, all 26 tests, repeated demos, figure freshness and compilation. No PR was created, no force push was used, and no deployment was made. Repository About text and five topics describe the research CLI.

Fresh-clone verification used `git clone https://github.com/RahilBhavan/strc-rate-controller.git ~/scratch/strc-rate-controller/fresh-clone`, then the commands below. Python 3.14.7 reproduced all six working-tree hashes, verified 385 sources and passed 26 tests. Scratch checkouts were removed after the evidence was saved. The repository itself needs no dependencies or credentials for this demo.

A cold copy under `~/scratch/strc-rate-controller/clean-copy` restored the archive, passed all 26 tests, ran the demo twice and matched all six working-tree output hashes. Intentional corruption of a source body and of an archive part was rejected with integrity errors. No pre-existing raw cache, generated outputs or installed dependency environment was copied.

Local evidence: 26 passing tests; 385 source hashes verified; 17 parsed announcements, 14 unconditional decisions and 309 daily observations; six generated output hashes repeat. Commands: `python3 scripts/snapshot.py`, `python3 scripts/validate.py`, `python3 scripts/result_figure.py --check`, `python3 -m compileall -q strc scripts tests`.

The reachable-history/source inspection is recorded in [publication-safety.json](publication-safety.json). No credential-pattern hits, oversized blobs or unexpected archive members were found. Manual inspection covered source metadata, tracked paths, history, contacts and binary archive contents. Full third-party redistribution rights are not certified; [sources.md](sources.md) records that limit. No code license was invented.

The result figure was rendered at 720px and 400px in T3. It uses a numeric table because the eight errors are lookup values, not a shape claim. Browser fallback fonts were used; no font redistribution is involved. Figure integrity: no area/length encoding, no implied confidence interval, explicit tiny-sample and leakage warnings. Agent visual review found no clipping or collisions; no independent human reader test was performed.

## Update 2026-10-22: license

The MIT license was added in `LICENSE`. It covers this project's code only. Earlier statements in this record that no license file existed describe the state at publication.

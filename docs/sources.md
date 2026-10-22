# Source coverage and verification

As of 2026-10-21. `provenance/sources-*.csv` inventories 385 cached response bodies with URL, fetch time, bytes and SHA-256. Many are filing index/cover pages rather than independent observations. `snapshot/index.json` hashes the complete compressed cache; parts are <=18,000 bytes. Restore with `python scripts/snapshot.py`; verify with `python scripts/verify_sources.py`. Original URL metadata is restored alongside each response. Results are generated locally and ignored by Git.

Primary documents checked on their owners' sites during this continuation:

- [Original STRC certificate](https://www.sec.gov/Archives/edgar/data/1050446/000119312525167987/d43815dex31.htm): initial terms; cached and extracted by the history loader.
- [June amended certificate](https://www.sec.gov/Archives/edgar/data/1050446/000119312526270366/d144149dex31.htm): semi-monthly periods and discretionary resets with reduction limits.
- [July 30 results](https://www.strategy.com/press/strategy-announces-second-quarter-2026-financial-results_07-30-2026): announced intention to hold 12% pending sustained trading near $100.
- [October proxy](https://www.sec.gov/Archives/edgar/data/1050446/000119312526413159/d503578ddef14a.htm): October 28 vote is pending; proposed daily terms are not enacted on October 21.
- [Conditional declaration](https://www.strategy.com/press/strategy-declares-conditional-daily-dividends-on-strc-for-november-2026_10-16-2026): conditional status, excluded from fitted decisions.
- [STRC information](https://www.strategy.com/strc/learn) and company KPI API cache: current semi-monthly rate. The browser could not open the API endpoint itself; cached API values are hash-preserved and compared to the company page, not claimed independently audited.
- [NY Fed SOFR](https://www.newyorkfed.org/markets/reference-rates/sofr): overnight reference rate; not the contract's term SOFR.

Yahoo chart responses supply daily STRC, MSTR and BTC bars. Yahoo is a secondary market-data provider. They are frozen and attributed; no exchange-grade/intraday reconciliation was performed. Refresh helpers in `scripts/fetch_*.py` are optional and require a locally configured `SEC_USER_AGENT` with contact email for EDGAR. Refresh changes the research sample; it is not part of deterministic reproduction.

Publication source review re-opened the amended certificate, July 30 policy release and October proxy at their primary URLs. The amended certificate's definition of Regular Dividend Rate Per Annum restricts any elected **different** rate, including an increase, while allowing the prior rate to carry. The implemented floor remains an overnight-SOFR approximation. Its arrears flag abstracts both payment and the certificate's declared-and-sufficient-consideration-set-aside alternative; it does not inspect dividend funding.

## Source rights

The cache preserves public response bodies for attributed, reproducible research; it is not a licensed market-data feed. SEC-hosted issuer filings and company/Yahoo responses remain third-party material. Some filing HTML includes a Donnelley copyright notice. Attribution and public availability do not establish a blanket redistribution license, and none is asserted here. Hash inventories prove byte identity, not permission, truth or completeness. Downstream commercial reuse needs its own rights review. No account, private financial record, authenticated response or private hub export was found in the publication inventory.

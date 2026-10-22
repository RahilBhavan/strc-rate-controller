"""Download market data into data/raw/ (no credentials needed).

- Yahoo Finance chart API: STRC, MSTR, BTC-USD daily OHLCV since STRC listing. Unofficial, undocumented
  endpoint; values can be revised and the API can change without notice.
- New York Fed Markets API: overnight SOFR (primary source). Used as a labeled proxy for One-Month
  Term SOFR, which CME licenses and does not publish as a free history.
- Strategy KPI API (api.strategy.com): current STRC notional, monthly VWAP, dividend history, mNAV.
  Current snapshot only; the API keeps no history, so each fetch is saved under its date.

Run: python3 scripts/fetch_market.py [--refresh]
"""
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from strc.fetch import get  # noqa: E402

START = int(dt.datetime(2025, 7, 1, tzinfo=dt.timezone.utc).timestamp())
END = int(dt.datetime(2026, 10, 22, tzinfo=dt.timezone.utc).timestamp())


def main(refresh=False):
    for sym in ("STRC", "MSTR", "BTC-USD"):
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1={START}&period2={END}"
               f"&interval=1d&events=div")
        get(url, "prices", f"yahoo-{sym}.json", refresh)
    get("https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?startDate=2025-06-01&endDate=2026-10-21",
        "rates", "nyfed-sofr.json", refresh)
    today = dt.date.today().isoformat()
    for ep in ("strcKpiData", "mstrKpiData", "bitcoinKpis"):
        get(f"https://api.strategy.com/btc/{ep}", "strategy", f"{ep}-{today}.json", refresh)
    print("market data cached")


if __name__ == "__main__":
    main("--refresh" in sys.argv)

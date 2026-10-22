"""Download Strategy filings that can carry STRC terms or rate announcements into data/raw/edgar.

Run: SEC_USER_AGENT="<name> <email>" python3 scripts/fetch_filings.py
Fetches each 8-K and 8-K/A since STRC's launch (2025-07-21), plus every exhibit, the STRC
prospectus supplements and the 10-Q/10-K/proxy documents named in strc/sources.py.
"""
import json
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from strc.fetch import get  # noqa: E402

CIK = "1050446"
FORMS = {"8-K", "8-K/A", "424B5", "10-Q", "10-K", "DEF 14A"}


def filing_docs(acc: str) -> list[str]:
    nodash = acc.replace("-", "")
    idx = json.loads(get(f"https://www.sec.gov/Archives/edgar/data/{CIK}/{nodash}/index.json",
                         "edgar", f"{nodash}-index.json"))
    return [i["name"] for i in idx["directory"]["item"]
            if re.search(r"\.htm$", i["name"]) and "index" not in i["name"]]


def main():
    sub = json.loads(get("https://data.sec.gov/submissions/CIK0001050446.json", "edgar", "submissions.json"))
    r = sub["filings"]["recent"]
    n = 0
    for i, form in enumerate(r["form"]):
        if form not in FORMS or r["filingDate"][i] < "2025-07-21":
            continue
        # big periodic filings: only the primary document
        acc = r["accessionNumber"][i]
        nodash = acc.replace("-", "")
        docs = [r["primaryDocument"][i]] if form in {"10-Q", "10-K", "DEF 14A"} else filing_docs(acc)
        if form == "424B5":
            docs = [r["primaryDocument"][i]]
        for doc in docs:
            get(f"https://www.sec.gov/Archives/edgar/data/{CIK}/{nodash}/{doc}", "edgar", f"{nodash}-{doc}")
            n += 1
    print("documents cached:", n)


if __name__ == "__main__":
    main()

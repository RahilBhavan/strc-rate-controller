"""Cached fetching from primary sources.

Every response is stored under data/raw/ with a sidecar .meta.json that records the URL and
fetch time. Later runs read the cache; pass refresh=True to refetch.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
# SEC fair-access policy rejects agents without a contact email (HTTP 403 observed 2026-10-21 for
# the bare project string). Set SEC_USER_AGENT to "<name> <email>" for EDGAR fetches.
UA = "RahilBhavan-research (github.com/RahilBhavan)"


def _agent(url: str) -> str:
    if "sec.gov" in url:
        ua = os.environ.get("SEC_USER_AGENT", "")
        if "@" not in ua:
            raise RuntimeError("EDGAR needs SEC_USER_AGENT with a contact email; cached files need none")
        return ua
    return UA
_last = [0.0]


def _path_for(url: str, sub: str, name: str | None) -> pathlib.Path:
    if name is None:
        name = hashlib.sha1(url.encode()).hexdigest()[:16]
    return RAW / sub / name


def get(url: str, sub: str = "edgar", name: str | None = None, refresh: bool = False) -> bytes:
    """Return the body for url, from cache when present. Throttled to <= 4 req/s."""
    path = _path_for(url, sub, name)
    meta = path.with_name(path.name + ".meta.json")
    if path.exists() and not refresh:
        return path.read_bytes()
    wait = 0.4 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": _agent(url), "Accept-Encoding": "identity"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503) or attempt == 4:
                raise
            time.sleep(2 * 2 ** attempt)
    _last[0] = time.time()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    meta.write_text(json.dumps({"url": url, "fetched_utc": dt.datetime.now(dt.timezone.utc)
                                .isoformat(timespec="seconds"), "bytes": len(body)}, indent=1) + "\n")
    return body


def meta(sub: str, name: str) -> dict:
    return json.loads((RAW / sub / (name + ".meta.json")).read_text())

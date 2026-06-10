"""HTTP client for BFCL leaderboard data — no parsing, just transport."""

from __future__ import annotations

import time
import urllib.error
import urllib.request

BFCL_CSV_URL = (
    "https://raw.githubusercontent.com/ShishirPatil/gorilla"
    "/gh-pages/data_overall.csv"
)

_MAX_RETRIES = 3
_HEADERS = {"User-Agent": "prudent-ai-p2-bfcl/1.0 (research)"}


class BFCLClient:
    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def fetch_csv(self) -> str:
        """Return raw CSV text from BFCL gh-pages."""
        return self._get_text(BFCL_CSV_URL)

    def _get_text(self, url: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                req = urllib.request.Request(url, headers=_HEADERS)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                    encoding = resp.headers.get_content_charset("utf-8")
                    return raw.decode(encoding)
            except urllib.error.HTTPError as exc:
                if exc.code in (404, 403):
                    raise FileNotFoundError(f"HTTP {exc.code}: {url}") from exc
                last_exc = exc
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
        raise RuntimeError(f"Failed to fetch {url}: {last_exc}") from last_exc

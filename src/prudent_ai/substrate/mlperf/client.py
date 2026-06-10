"""HTTP client for MLPerf Inference results — no parsing, just transport."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

MLPERF_VERSION = "v5.0"
SUMMARY_URL = (
    "https://raw.githubusercontent.com/mlcommons"
    f"/inference_results_{MLPERF_VERSION}/main/summary_results.json"
)
LOG_BASE_URL = (
    "https://raw.githubusercontent.com/mlcommons"
    f"/inference_results_{MLPERF_VERSION}/main/"
)

_MAX_RETRIES = 3
_HEADERS = {"User-Agent": "prudent-ai-p2-mlperf/1.0 (research)"}


class MLPerfClient:
    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def fetch_summary(self) -> list[dict]:
        """Fetch summary_results.json → list of result dicts."""
        return self._get_json(SUMMARY_URL)

    def fetch_log(self, location: str) -> str:
        """Fetch mlperf_log_summary.txt for a given Location path.

        Args:
            location: The 'Location' field from summary_results.json,
                e.g. "closed/AMD/results/8xMI325X.../llama2-70b-99/Server"
        """
        url = LOG_BASE_URL + location + "/performance/run_1/mlperf_log_summary.txt"
        return self._get_text(url)

    def _get_json(self, url: str) -> list[dict]:
        text = self._get_text(url)
        return json.loads(text)

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

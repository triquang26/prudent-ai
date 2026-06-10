"""HTTP client for HELM Lite data on Google Cloud Storage.

All network I/O is isolated here. No parsing, no DB logic.

GCS layout:
  crfm-helm-public/lite/benchmark_output/runs/{version}/{run_name}/
  Files per run: stats.json, run_spec.json, scenario.json, ...

List API:
  GET https://storage.googleapis.com/storage/v1/b/crfm-helm-public/o
      ?prefix=lite/benchmark_output/runs/{version}/&delimiter=/
      Returns { "prefixes": ["lite/.../run_name/", ...] }
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

GCS_BASE = "https://storage.googleapis.com/crfm-helm-public"
GCS_API = "https://storage.googleapis.com/storage/v1/b/crfm-helm-public/o"
_RUN_PREFIX = "lite/benchmark_output/runs"


class HelmLiteClient:
    """Thin GCS HTTP client — enumerate runs and fetch stats/spec files.

    Args:
        timeout: Per-request timeout in seconds.
        max_retries: Number of retries on transient errors (5xx, network).
        retry_delay: Initial retry delay in seconds (doubles on each retry).
    """

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_run_names(self, version: str) -> list[str]:
        """Return all run directory names (just the suffix, no trailing slash).

        E.g. ["gsm:model=openai_gpt-4-0613", "math:model=...", ...]
        Handles GCS pagination automatically.
        """
        prefix = f"{_RUN_PREFIX}/{version}/"
        names: list[str] = []
        page_token: str | None = None

        while True:
            params = f"prefix={urllib.parse.quote(prefix)}&delimiter=/&maxResults=1000"
            if page_token:
                params += f"&pageToken={urllib.parse.quote(page_token)}"
            url = f"{GCS_API}?{params}"
            data = self._get_json(url)

            for p in data.get("prefixes", []):
                # p = "lite/benchmark_output/runs/v1.0.0/gsm:model=.../
                run_name = p.removeprefix(prefix).rstrip("/")
                if run_name:
                    names.append(run_name)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return names

    def fetch_stats(self, version: str, run_name: str) -> list[dict]:
        """Fetch and return the raw stats.json array for one run."""
        url = f"{GCS_BASE}/{_RUN_PREFIX}/{version}/{run_name}/stats.json"
        return self._get_json(url)  # type: ignore[return-value]

    def fetch_run_spec(self, version: str, run_name: str) -> dict:
        """Fetch run_spec.json (adapter params, groups, metric specs)."""
        url = f"{GCS_BASE}/{_RUN_PREFIX}/{version}/{run_name}/run_spec.json"
        return self._get_json(url)  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_json(self, url: str) -> dict | list:
        delay = self.retry_delay
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(
                    url, headers={"Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise FileNotFoundError(f"Not found: {url}") from exc
                if exc.code < 500:
                    raise
                last_err = exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_err = exc

            if attempt < self.max_retries - 1:
                time.sleep(delay)
                delay *= 2

        raise RuntimeError(f"Failed after {self.max_retries} retries: {url}") from last_err

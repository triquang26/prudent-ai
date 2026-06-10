"""HTTP client for any HELM-family suite on crfm-helm-public GCS (prefix-parameterized).

Generalizes `helm_lite.client.HelmLiteClient` to an arbitrary suite by taking the run
prefix (e.g. ``medhelm/benchmark_output/runs``). All network I/O is isolated here.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

GCS_BASE = "https://storage.googleapis.com/crfm-helm-public"
GCS_API = "https://storage.googleapis.com/storage/v1/b/crfm-helm-public/o"


class HelmSuiteClient:
    """Thin GCS client for a HELM suite identified by its run prefix."""

    def __init__(
        self,
        suite_prefix: str,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> None:
        # e.g. "medhelm/benchmark_output/runs"
        self.suite_prefix = suite_prefix.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def list_versions(self) -> list[str]:
        """Return the version sub-directories under the suite run prefix (e.g. v2.0.0)."""
        prefix = f"{self.suite_prefix}/"
        data = self._get_json(
            f"{GCS_API}?prefix={urllib.parse.quote(prefix)}&delimiter=/&maxResults=1000"
        )
        out = []
        for p in data.get("prefixes", []):
            v = p.removeprefix(prefix).rstrip("/")
            if v:
                out.append(v)
        return sorted(out)

    def list_run_names(self, version: str) -> list[str]:
        """All run directory names under a version (handles pagination)."""
        prefix = f"{self.suite_prefix}/{version}/"
        names: list[str] = []
        page_token: str | None = None
        while True:
            params = f"prefix={urllib.parse.quote(prefix)}&delimiter=/&maxResults=1000"
            if page_token:
                params += f"&pageToken={urllib.parse.quote(page_token)}"
            data = self._get_json(f"{GCS_API}?{params}")
            for p in data.get("prefixes", []):
                run_name = p.removeprefix(prefix).rstrip("/")
                if run_name:
                    names.append(run_name)
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return names

    def fetch_stats(self, version: str, run_name: str) -> list[dict]:
        """Fetch stats.json for one run (raises FileNotFoundError if absent)."""
        url = (
            f"{GCS_BASE}/{self.suite_prefix}/{version}/"
            f"{urllib.parse.quote(run_name)}/stats.json"
        )
        return self._get_json(url)

    # ------------------------------------------------------------------

    def _get_json(self, url: str):
        last_exc: Exception | None = None
        delay = self.retry_delay
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise FileNotFoundError(url) from exc
                last_exc = exc
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last_exc = exc
            if attempt < self.max_retries:
                time.sleep(delay)
                delay *= 2
        raise RuntimeError(f"GCS request failed after retries: {url}") from last_exc

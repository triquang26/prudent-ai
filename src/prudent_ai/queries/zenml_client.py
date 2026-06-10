"""HTTP client for the ZenML LLMOps Database — transport only, no parsing.

Source: https://www.zenml.io/llmops-database — a curated corpus of real-world LLM
deployment case studies. Mirrored as the HuggingFace dataset
`zenml/llmops-database` (1716 rows, split=train). We read it through the
HuggingFace datasets-server rows API (no auth needed for this public dataset).

Each row carries: title, industry, year, company, application_tags, tools_tags,
techniques_tags, short_summary, full_summary. We use the tag fields + industry to
derive (archetype, binding-axis) queries — see query_prior.py.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

DATASET = "zenml/llmops-database"
CONFIG = "default"
SPLIT = "train"
ROWS_URL = (
    "https://datasets-server.huggingface.co/rows"
    f"?dataset={DATASET}&config={CONFIG}&split={SPLIT}"
)
PAGE = 100   # datasets-server max rows per request

_MAX_RETRIES = 4
_HEADERS = {"User-Agent": "prudent-ai-zenml/1.0 (research)"}


class ZenMLClient:
    """Paginate the ZenML LLMOps Database rows."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def fetch_all_rows(
        self, limit: int | None = None, cache_path: str | Path | None = None
    ) -> list[dict]:
        """Return all (or up to *limit*) row dicts from the dataset.

        If *cache_path* is given and exists, the frozen snapshot is loaded from
        disk (C3: reproducible, versioned corpus — and avoids re-hammering the
        datasets-server). Otherwise the dataset is fetched and, if *cache_path* is
        given, written there as the snapshot.
        """
        if cache_path is not None:
            p = Path(cache_path)
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                return data[:limit] if limit is not None else data

        rows = self._fetch_all_rows_network(limit)

        if cache_path is not None:
            p = Path(cache_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(rows), encoding="utf-8")
        return rows

    def _fetch_all_rows_network(self, limit: int | None = None) -> list[dict]:
        rows: list[dict] = []
        offset = 0
        while True:
            page = self._fetch_page(offset, PAGE)
            batch = [r["row"] for r in page.get("rows", [])]
            if not batch:
                break
            rows.extend(batch)
            offset += PAGE
            if limit is not None and len(rows) >= limit:
                return rows[:limit]
            # datasets-server reports num_rows_total; stop when exhausted
            total = page.get("num_rows_total")
            if total is not None and offset >= total:
                break
        return rows

    def _fetch_page(self, offset: int, length: int) -> dict:
        url = f"{ROWS_URL}&offset={offset}&length={length}"
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                req = urllib.request.Request(url, headers=_HEADERS)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                # 502/503 transient; 429 rate-limit — retry with backoff.
                if exc.code in (404, 401, 403):
                    raise
                last_exc = exc
                # 429 needs a longer cool-off than transient 5xx.
                if exc.code == 429 and attempt < _MAX_RETRIES - 1:
                    time.sleep(10 * (attempt + 1))
                    continue
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"Failed to fetch {url}: {last_exc}") from last_exc

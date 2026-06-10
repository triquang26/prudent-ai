"""HTTP client for ML.ENERGY leaderboard data — no parsing, just transport."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

GITHUB_API_BASE = "https://api.github.com/repos/ml-energy/leaderboard"
RAW_BASE = "https://raw.githubusercontent.com/ml-energy/leaderboard/master"
INDEX_URL = f"{RAW_BASE}/public/data/index.json"
MODELS_DIR_URL = f"{GITHUB_API_BASE}/contents/public/data/models"

_MAX_RETRIES = 3
_HEADERS = {"User-Agent": "prudent-ai-p2-mlenergy/1.0 (research)"}


class MLEnergyClient:
    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def fetch_index(self) -> dict:
        """Fetch index.json with models, tasks, architectures metadata."""
        return self._get_json(INDEX_URL)

    def list_model_files(self) -> list[str]:
        """Return list of filenames in public/data/models/ via GitHub API."""
        items = self._get_json(MODELS_DIR_URL)
        return [item["name"] for item in items if item.get("type") == "file"
                and item["name"].endswith(".json")]

    def fetch_model_task(self, filename: str) -> dict:
        """Fetch one {model}__{task}.json file by filename."""
        url = f"{RAW_BASE}/public/data/models/{filename}"
        return self._get_json(url)

    def _get_json(self, url: str) -> dict | list:
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

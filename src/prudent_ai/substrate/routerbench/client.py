"""RouterBench transport — download the pickle once and freeze it (C3).

The dataset ships as pandas pickles on HuggingFace (withmartian/routerbench).
We use the 0-shot split. The pickle is fetched once to a local snapshot and
reused (C3 reproducibility; the file is ~99 MB). Loading requires pandas.

Security note: `pd.read_pickle` executes pickle opcodes. We load only the
official RouterBench artifact (DOI 10.57967/hf/1996) downloaded from its
canonical HuggingFace URL — documented provenance, not arbitrary input.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

RESOLVE_URL = (
    "https://huggingface.co/datasets/withmartian/routerbench"
    "/resolve/main/routerbench_0shot.pkl"
)
DEFAULT_SNAPSHOT = "data/routerbench_0shot.pkl"
_HEADERS = {"User-Agent": "prudent-ai-routerbench/1.0 (research)"}


class RouterBenchClient:
    """Fetch + load the RouterBench 0-shot DataFrame."""

    def __init__(self, snapshot_path: str | Path = DEFAULT_SNAPSHOT, timeout: int = 240) -> None:
        self.snapshot_path = Path(snapshot_path)
        self.timeout = timeout

    def ensure_snapshot(self) -> Path:
        """Download the pickle to the snapshot path if not already present."""
        if not self.snapshot_path.exists():
            self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(RESOLVE_URL, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                self.snapshot_path.write_bytes(resp.read())
        return self.snapshot_path

    def load_dataframe(self) -> pd.DataFrame:
        """Return the RouterBench 0-shot DataFrame (downloads on first call)."""
        import pandas as pd

        path = self.ensure_snapshot()
        return pd.read_pickle(path)

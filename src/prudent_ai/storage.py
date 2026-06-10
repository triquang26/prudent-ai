"""HuggingFace bucket interface for prudent-ai.

Bucket: hf://buckets/twanghcmut/prudent-ai-bucket
Root folder: PrudentAI/

Folder conventions
------------------
  PrudentAI/Plan/            planning docs & specs (pull-only; source of truth is the bucket)
  PrudentAI/Paper/           reference PDFs
  PrudentAI/shared/<name>/   datasets or artifacts shared across experiments
  PrudentAI/exp/<id>-<slug>/ per-experiment data, mirroring the git branch name

Usage
-----
  bucket = BucketStorage()
  bucket.pull("Plan", local="docs/plan")             # sync down Plan/ → docs/plan/
  bucket.push("exp/a87-baseline", local="data/a87")  # sync up data/a87/ → …/exp/a87-baseline/
  bucket.ls()                                         # list top-level remote folders
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

BUCKET_URI = "hf://buckets/twanghcmut/prudent-ai-bucket"
BUCKET_ROOT = "PrudentAI"


@dataclass
class BucketStorage:
    """Thin wrapper around `hf sync` / `hf buckets` for this project's bucket.

    All remote paths are relative to ``BUCKET_ROOT`` (``PrudentAI/``).  Local
    paths default to ``data/<remote_prefix>/``.
    """

    bucket_uri: str = BUCKET_URI
    root: str = BUCKET_ROOT
    local_base: Path = field(default_factory=lambda: Path("data"))

    # ----- helpers ---------------------------------------------------------

    def _remote(self, prefix: str) -> str:
        """Full ``hf://`` URI for a prefix inside the bucket root."""
        return f"{self.bucket_uri}/{self.root}/{prefix.strip('/')}"

    def _local(self, prefix: str, local: str | Path | None) -> Path:
        if local is not None:
            return Path(local)
        return self.local_base / prefix.strip("/")

    # ----- public API ------------------------------------------------------

    def pull(
        self,
        remote_prefix: str,
        *,
        local: str | Path | None = None,
        dry_run: bool = False,
        delete: bool = False,
    ) -> None:
        """Download remote_prefix → local dir (``hf sync`` pull direction).

        Args:
            remote_prefix: Path inside ``PrudentAI/``, e.g. ``"Plan"`` or
                ``"exp/a87147-baseline"``.
            local: Local destination. Defaults to ``data/<remote_prefix>/``.
            dry_run: Print the sync plan without executing.
            delete: Pass ``--delete`` to mirror deletions (use with care).
        """
        src = self._remote(remote_prefix)
        dst = str(self._local(remote_prefix, local))
        self._sync(src, dst, dry_run=dry_run, delete=delete)

    def push(
        self,
        remote_prefix: str,
        *,
        local: str | Path | None = None,
        dry_run: bool = False,
        delete: bool = False,
    ) -> None:
        """Upload local dir → remote_prefix (``hf sync`` push direction).

        Use the experiment slug as remote_prefix to keep data co-located with
        the vault node, e.g. ``"exp/a87147-baseline"``.
        """
        src = str(self._local(remote_prefix, local))
        dst = self._remote(remote_prefix)
        self._sync(src, dst, dry_run=dry_run, delete=delete)

    def ls(self, remote_prefix: str = "", *, recursive: bool = False) -> list[str]:
        """List files/folders at remote_prefix. Returns raw hf output lines."""
        uri = self._remote(remote_prefix) if remote_prefix else f"{self.bucket_uri}/{self.root}"
        cmd = ["hf", "buckets", "list", uri]
        if recursive:
            cmd.append("-R")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return [line for line in result.stdout.splitlines() if line.strip()]

    # ----- internals -------------------------------------------------------

    def _sync(
        self,
        src: str,
        dst: str,
        *,
        dry_run: bool,
        delete: bool,
    ) -> None:
        cmd = ["hf", "sync", src, dst]
        if dry_run:
            cmd.append("--dry-run")
        if delete:
            cmd.append("--delete")
        subprocess.run(cmd, check=True)

"""Experiment configuration — a single, serializable source of truth per run.

Configs are dataclasses (not argparse flags) so a run is fully described by one
object that can be dumped to / loaded from YAML and committed next to results.
This is what makes a vault node reproducible: the node records the exact config.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class ExperimentConfig:
    """Everything needed to reproduce one experiment run.

    Extend with task-specific fields, but keep ``seed`` and ``name`` — the
    research-infra vault keys results off them.
    """

    name: str
    seed: int = 0
    output_dir: Path = field(default_factory=lambda: Path("outputs"))
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict view, with Path coerced to str for YAML round-tripping."""
        d = dataclasses.asdict(self)
        d["output_dir"] = str(self.output_dir)
        return d

    def save(self, path: str | Path) -> Path:
        """Write the config to YAML; returns the path written."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(self.to_dict(), sort_keys=False))
        return path

    @classmethod
    def load(cls, path: str | Path) -> ExperimentConfig:
        """Reconstruct a config from a YAML file written by :meth:`save`."""
        data = yaml.safe_load(Path(path).read_text())
        data["output_dir"] = Path(data.get("output_dir", "outputs"))
        return cls(**data)

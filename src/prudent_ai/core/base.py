"""Base class for experiments — the OOP contract every run subclasses.

The lifecycle (``setup`` → ``run`` → ``teardown``, orchestrated by ``execute``)
mirrors the research-infra node lifecycle: one ``Experiment`` instance ⇔ one
vault node ⇔ one ``exp/<id>-<slug>`` branch. Subclasses implement the abstract
hooks; ``execute`` guarantees the config is saved and the run is seeded first,
so results are reproducible by construction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from prudent_ai.config import ExperimentConfig
from prudent_ai.reproducibility import seed_everything


class Experiment(ABC):
    """Abstract experiment. Subclass and implement :meth:`run`.

    Example:
        >>> class MyRun(Experiment):
        ...     def run(self) -> dict[str, float]:
        ...         return {"metric": 1.0}
        >>> MyRun(ExperimentConfig(name="demo")).execute()["metric"]
        1.0
    """

    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config

    # ----- lifecycle hooks (override as needed) -----
    def setup(self) -> None:
        """Allocate resources, load data. Default: no-op."""

    @abstractmethod
    def run(self) -> dict[str, Any]:
        """Execute the experiment and return a metrics dict for `/exp-record`."""

    def teardown(self) -> None:
        """Release resources. Default: no-op. Runs even if :meth:`run` raises."""

    # ----- orchestration (don't override; reproducibility lives here) -----
    def execute(self) -> dict[str, Any]:
        """Seed → save config → setup → run → teardown. Returns run() metrics."""
        seed_everything(self.config.seed)
        self.config.save(self.config.output_dir / f"{self.config.name}.config.yaml")
        self.setup()
        try:
            return self.run()
        finally:
            self.teardown()

"""Smoke tests — prove the OOP skeleton wires together and stays reproducible."""

from __future__ import annotations

import random

from prudent_ai import ExperimentConfig, seed_everything
from prudent_ai.core import Experiment


class _Coin(Experiment):
    def run(self) -> dict[str, float]:
        return {"draw": random.random()}


def test_seed_is_reproducible() -> None:
    seed_everything(123)
    a = random.random()
    seed_everything(123)
    b = random.random()
    assert a == b


def test_config_roundtrip(tmp_path) -> None:
    cfg = ExperimentConfig(name="demo", seed=7, params={"lr": 0.1})
    path = cfg.save(tmp_path / "cfg.yaml")
    loaded = ExperimentConfig.load(path)
    assert loaded.name == "demo"
    assert loaded.seed == 7
    assert loaded.params == {"lr": 0.1}


def test_experiment_execute_is_deterministic(tmp_path) -> None:
    cfg = ExperimentConfig(name="coin", seed=42, output_dir=tmp_path)
    first = _Coin(cfg).execute()["draw"]
    second = _Coin(cfg).execute()["draw"]
    assert first == second

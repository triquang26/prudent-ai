"""Tests for the live acquisition loop (Tier-3): real measurement, refusal, frozen db."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from prudent_ai.analysis.validation_run import ValidationRunner
from prudent_ai.loop import LiveAcquisitionLoop, NoMeasurementPathError
from prudent_ai.solver.beliefs import Phi, aggregate
from prudent_ai.solver.query import make_query
from prudent_ai.substrate.substrate import Substrate
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskAndPredict, MaskedSubstrate

DB = "data/apt_substrate.db"
pytestmark = pytest.mark.skipif(not Path(DB).exists(), reason="frozen db absent")


def _oracle(bsub):
    def o(cid, axis):
        b = aggregate(bsub.cell(cid, axis), ("H",), Phi.POINT)
        return b.point if b.is_present else None
    return o


def _first_slice(sub):
    bench = ValidationRunner(sub).discover_routerbench_benchmarks()[0]
    bsub = BenchmarkSubstrate(sub, bench)
    mp = MaskAndPredict(bsub, kappa=("H",), phi=Phi.POINT)
    qs = mp.generate_queries("routerbench", ("quality", "cost"), pcts=(50,))
    return bsub, mp, qs


def test_loop_commits_after_measuring_quality() -> None:
    sub = Substrate(DB)
    try:
        bsub, mp, qs = _first_slice(sub)
        masked = MaskedSubstrate(bsub, "quality")
        loop = LiveAcquisitionLoop(_oracle(bsub))
        r = loop.run(masked, qs[0])
        assert r.action == "commit"
        assert "quality" in r.probes          # it acquired the blocking axis
        assert mp.true_feasible(qs[0], r.committed_config)  # commit is truly feasible
    finally:
        sub.close()


def test_governance_loop_raises() -> None:
    sub = Substrate(DB)
    try:
        bsub, _, _ = _first_slice(sub)
        masked = MaskedSubstrate(bsub, "quality")
        q = make_query("routerbench", [("governance", ">=", 1.0)], label="bind:gov")
        loop = LiveAcquisitionLoop(_oracle(bsub))
        with pytest.raises(NoMeasurementPathError):
            loop.run(masked, q)
    finally:
        sub.close()


def test_loop_does_not_mutate_frozen_db() -> None:
    before = hashlib.md5(Path(DB).read_bytes()).hexdigest()
    sub = Substrate(DB)
    try:
        bsub, _, qs = _first_slice(sub)
        masked = MaskedSubstrate(bsub, "quality")
        LiveAcquisitionLoop(_oracle(bsub)).run(masked, qs[0])
    finally:
        sub.close()
    assert hashlib.md5(Path(DB).read_bytes()).hexdigest() == before

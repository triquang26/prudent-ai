"""Tests for calibrated transfer (Tier-1): refusal, determinism, injection, guarantee."""

from __future__ import annotations

from pathlib import Path

import pytest

from prudent_ai.analysis.empirical_prior_map import UNMEASURABLE_AXES
from prudent_ai.solver.beliefs import Phi, aggregate
from prudent_ai.solver.decidability import classify_query
from prudent_ai.solver.query import make_query
from prudent_ai.substrate.substrate import Substrate
from prudent_ai.transfer import CalibratedTransfer, OverlayedSubstrate, apply_transfer

DB = "data/apt_substrate.db"
PKL = Path("data/routerbench_0shot.pkl")
pytestmark = pytest.mark.skipif(
    not Path(DB).exists() or not PKL.exists(), reason="frozen artifacts absent"
)


@pytest.fixture(scope="module")
def transfer() -> CalibratedTransfer:
    return CalibratedTransfer.fit_from_pkl(PKL)


def test_structural_axes_refuse(transfer: CalibratedTransfer) -> None:
    cid = next(iter(transfer._point))  # any fitted RouterBench config
    for axis in UNMEASURABLE_AXES:
        assert transfer.predict_interval(cid, axis, 0.05) is None
    # cost is measurable-but-not-transferable here → also refuse
    assert transfer.predict_interval(cid, "cost", 0.05) is None
    # quality → an interval
    iv = transfer.predict_interval(cid, "quality", 0.05)
    assert iv is not None and iv[0] <= iv[1]
    assert 0.0 <= iv[0] and iv[1] <= 1.0  # clipped to quality domain


def test_unknown_config_refuses(transfer: CalibratedTransfer) -> None:
    assert transfer.predict_interval("rb-nonexistent-foo", "quality", 0.05) is None


def test_tau_monotone_in_alpha(transfer: CalibratedTransfer) -> None:
    # smaller α (more coverage) → wider interval
    assert transfer.tau(0.05) >= transfer.tau(0.10) >= transfer.tau(0.20)


def test_overlay_injects_interval(transfer: CalibratedTransfer) -> None:
    sub = Substrate(DB)
    try:
        cid = next(iter(transfer._point))
        iv = transfer.predict_interval(cid, "quality", 0.10)
        # an empty cell to overlay: use a guaranteed-⊥ axis cell but register quality on a
        # config whose quality we first blank via a masked proxy is overkill — instead
        # pick a structural axis cell (always ⊥) and force-register an interval to prove
        # the synthesis path; aggregate must yield exactly [lo, hi].
        ov = OverlayedSubstrate(sub, {(cid, "governance"): iv})
        obs = ov.cell(cid, "governance")
        assert len(obs) == 2
        bel = aggregate(obs, phi=Phi.INTERVAL)
        assert not bel.is_bottom
        assert abs(bel.lo - iv[0]) < 1e-9 and abs(bel.hi - iv[1]) < 1e-9
    finally:
        sub.close()


def test_overlay_never_overwrites_measured(transfer: CalibratedTransfer) -> None:
    sub = Substrate(DB)
    try:
        cid = next(iter(transfer._point))
        base = sub.cell(cid, "quality")  # measured (confidence H)
        assert base, "expected a measured quality cell"
        ov = OverlayedSubstrate(sub, {(cid, "quality"): (0.0, 1.0)})
        assert ov.cell(cid, "quality") == base  # measured cell untouched
    finally:
        sub.close()


def test_empty_overlay_is_bit_identical(transfer: CalibratedTransfer) -> None:
    """Transfer-OFF determinism: empty overlay → identical verdicts to the base."""
    sub = Substrate(DB)
    try:
        ov = OverlayedSubstrate(sub, {})
        q = make_query("routerbench", [("quality", ">=", 0.6), ("cost", "<=", 0.01)])
        r_base = classify_query(sub, q)
        r_ov = classify_query(ov, q)
        assert r_base.label == r_ov.label
        assert r_base.blocking_axes == r_ov.blocking_axes
        assert r_base.argmin_config == r_ov.argmin_config
        # apply_transfer(enabled=False) returns the substrate object unchanged
        assert apply_transfer(sub, transfer, 0.05, enabled=False) is sub
    finally:
        sub.close()


def test_frozen_db_unchanged(transfer: CalibratedTransfer) -> None:
    """Fitting + overlaying must not mutate the frozen snapshot."""
    import hashlib

    def md5(p: str) -> str:
        return hashlib.md5(Path(p).read_bytes()).hexdigest()

    before = md5(DB)
    sub = Substrate(DB)
    try:
        ov = OverlayedSubstrate(sub, transfer.build_overlays(0.10))
        cid = next(iter(transfer._point))
        ov.cell(cid, "governance")  # exercise synthesis
    finally:
        sub.close()
    assert md5(DB) == before

"""Gate test for P1: test_interface_invariance.

Property: on the same query, both solvers make an identical multiset of
substrate calls (candidates / cell / required_fields).  This proves C7
holds: phi, kappa, and the certifier are solver-side; the substrate is
solver-agnostic.

Four tests:
  test_interface_invariance       — C7 gate: multiset equality of substrate calls.
  test_is_missing_kappa_sensitivity — is_missing() depends on kappa, not substrate.
  test_multi_obs_per_cell         — cell() returns multiple observations.
  test_required_fields_is_syntactic — required_fields() is purely structural.
"""

from __future__ import annotations

from collections import Counter

import pytest

from prudent_ai.substrate import Constraint, Substrate, is_missing
from prudent_ai.substrate.solvers_stub import Query, solve_chance_constrained, solve_lexicographic

# ---------------------------------------------------------------------------
# Fixture: in-memory substrate with 3 configs
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_substrate(tmp_path):
    """In-memory substrate with 3 configs, quality observations for 2 of them.

    Layout:
      cfg-gpt4    (general-qa)  — 2 quality obs: confidence M + H, differing context
      cfg-llama   (general-qa)  — 1 quality obs: confidence M
      cfg-mistral (general-qa)  — 0 quality obs  → ⊥ under any kappa
    """
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    from prudent_ai.substrate.orm import Component, Config, ConfigComponent, Source
    from prudent_ai.substrate.orm import Observation as ObsORM

    sub = Substrate(":memory:")

    def _i(session, model, **kw):
        session.execute(sqlite_insert(model).values(**kw).on_conflict_do_nothing())

    s = sub._session
    _i(s, Source, evidence_id="src-1", source_type="leaderboard",
       citation="HELM 2023", snapshot_version="2023-11")
    _i(s, Component, id="m-gpt4", kind="model", name="GPT-4")
    _i(s, Component, id="m-llama", kind="model", name="Llama-2-70B")
    _i(s, Component, id="m-mistral", kind="model", name="Mistral-7B")
    _i(s, Config, id="cfg-gpt4", tau="general-qa")
    _i(s, Config, id="cfg-llama", tau="general-qa")
    _i(s, Config, id="cfg-mistral", tau="general-qa")
    _i(s, ConfigComponent, config_id="cfg-gpt4", component_id="m-gpt4")
    _i(s, ConfigComponent, config_id="cfg-llama", component_id="m-llama")
    _i(s, ConfigComponent, config_id="cfg-mistral", component_id="m-mistral")
    _i(s, ObsORM, obs_id="o1", config_id="cfg-gpt4", axis="quality",
       value_num=0.864, value_cat=None, confidence="M", evidence_id="src-1",
       hardware_tier="openai-api", dataset="mmlu",
       split="test", decoding_cfg="temperature-0.0", obs_date="2023-11")
    _i(s, ObsORM, obs_id="o3", config_id="cfg-gpt4", axis="quality",
       value_num=0.871, value_cat=None, confidence="H", evidence_id="src-1",
       hardware_tier="openai-api", dataset="mmlu",
       split="test", decoding_cfg="greedy", obs_date="2023-11")
    _i(s, ObsORM, obs_id="o2", config_id="cfg-llama", axis="quality",
       value_num=0.686, value_cat=None, confidence="M", evidence_id="src-1",
       hardware_tier="aws-a100", dataset="mmlu",
       split="test", decoding_cfg="temperature-0.0", obs_date="2023-11")
    s.commit()
    return sub


# ---------------------------------------------------------------------------
# Call-recording helper
# ---------------------------------------------------------------------------


def _record_substrate_calls(
    sub: Substrate,
    solver_fn,
    *args,
    **kwargs,
) -> list[tuple[str, tuple]]:
    """Monkey-patch sub's three interface methods to record every call.

    Returns a list of (method_name, normalised_args) tuples in call order.
    For required_fields, args are normalised to a sorted tuple of (axis, op)
    pairs so that bundle identity is checked structurally, not by object id.
    """
    calls: list[tuple[str, tuple]] = []

    orig_candidates = sub.candidates
    orig_cell = sub.cell
    orig_required_fields = sub.required_fields

    def wrap_candidates(tau: str):
        calls.append(("candidates", (tau,)))
        return orig_candidates(tau)

    def wrap_cell(x: str, a: str):
        calls.append(("cell", (x, a)))
        return orig_cell(x, a)

    def wrap_required_fields(bundle):
        normalised = tuple(sorted((c.axis, c.op) for c in bundle))
        calls.append(("required_fields", normalised))
        return orig_required_fields(bundle)

    sub.candidates = wrap_candidates
    sub.cell = wrap_cell
    sub.required_fields = wrap_required_fields

    try:
        solver_fn(sub, *args, **kwargs)
    finally:
        sub.candidates = orig_candidates
        sub.cell = orig_cell
        sub.required_fields = orig_required_fields

    return calls


# ---------------------------------------------------------------------------
# Gate test: C7 — substrate call multisets are identical across solvers
# ---------------------------------------------------------------------------


def test_interface_invariance(seeded_substrate: Substrate) -> None:
    """Both solvers make an identical multiset of substrate calls (C7).

    Verifies that phi (interval vs distribution) and the solver-specific
    alpha parameter do not influence *which* calls are issued to the
    substrate, only how the returned observations are aggregated.
    """
    sub = seeded_substrate
    q = Query(
        tau="general-qa",
        bundle=(Constraint(axis="quality", op="ge", value=0.7),),
    )
    kappa = ("H", "M")

    calls1 = _record_substrate_calls(sub, solve_lexicographic, q, kappa)
    calls2 = _record_substrate_calls(sub, solve_chance_constrained, q, kappa, alpha=0.1)

    assert Counter(calls1) == Counter(calls2), (
        "Substrate call multisets differ — C7 violated.\n"
        f"Solver 1 (lexicographic):       {calls1}\n"
        f"Solver 2 (chance-constrained):  {calls2}"
    )

    # Structural sanity: all three interface methods must have been called.
    call_names = {name for name, _ in calls1}
    assert "candidates" in call_names, "candidates() was never called"
    assert "required_fields" in call_names, "required_fields() was never called"
    assert "cell" in call_names, "cell() was never called"

    # Exactly one candidates() call and one required_fields() call per solver.
    assert sum(1 for name, _ in calls1 if name == "candidates") == 1
    assert sum(1 for name, _ in calls1 if name == "required_fields") == 1

    # cell() called once per (candidate, axis) pair — 3 cands × 1 axis = 3 calls.
    cell_calls = [args for name, args in calls1 if name == "cell"]
    assert len(cell_calls) == 3, f"Expected 3 cell() calls, got {len(cell_calls)}"


# ---------------------------------------------------------------------------
# is_missing: kappa sensitivity
# ---------------------------------------------------------------------------


def test_is_missing_kappa_sensitivity(seeded_substrate: Substrate) -> None:
    """is_missing() result depends on kappa, not on what is stored in the DB.

    Demonstrates that missingness is a solver-side policy decision, not a
    substrate-side property.
    """
    sub = seeded_substrate

    # cfg-mistral has no observations → ⊥ under any kappa
    obs_mistral = sub.cell("cfg-mistral", "quality")
    assert is_missing(obs_mistral, ("H", "M")) is True
    assert is_missing(obs_mistral, ("H", "M", "L")) is True

    # cfg-gpt4 has H and M observations → present under H+M
    obs_gpt4 = sub.cell("cfg-gpt4", "quality")
    assert is_missing(obs_gpt4, ("H", "M")) is False

    # cfg-gpt4 has no L observations; filter to L-only → ⊥ (kappa sensitivity)
    assert is_missing(obs_gpt4, ("L",)) is True


# ---------------------------------------------------------------------------
# Multi-observation cell demo
# ---------------------------------------------------------------------------


def test_multi_obs_per_cell(seeded_substrate: Substrate) -> None:
    """At least one cell returns multiple observations (gate requirement).

    Ensures that cell() faithfully returns all rows without collapsing them,
    and that multiple observations for the same (config, axis) are stored and
    retrievable.
    """
    sub = seeded_substrate
    obs = sub.cell("cfg-gpt4", "quality")

    assert len(obs) >= 2, (
        f"Expected at least 2 observations for cfg-gpt4/quality, got {len(obs)}"
    )

    # Differing decoding context distinguishes the two observations.
    contexts = {o.context.decoding_cfg for o in obs}
    assert len(contexts) > 1, (
        "Multi-obs cell should have at least two distinct decoding_cfg values; "
        f"got: {contexts}"
    )

    # Differing confidences (M and H were inserted).
    confidences = {o.confidence for o in obs}
    assert {"H", "M"}.issubset(confidences), (
        f"Expected H and M confidence tiers in multi-obs cell; got: {confidences}"
    )


# ---------------------------------------------------------------------------
# required_fields is purely syntactic
# ---------------------------------------------------------------------------


def test_required_fields_is_syntactic(seeded_substrate: Substrate) -> None:
    """required_fields() is purely structural — it never queries the DB.

    The returned set is exactly {c.axis for c in bundle}, regardless of which
    axes actually have observations.  Axes absent from the bundle are excluded,
    even if they have ⊥ status semantically.
    """
    sub = seeded_substrate

    bundle = (
        Constraint(axis="quality", op="ge", value=0.7),
        Constraint(axis="latency_p95", op="le", value=500),
    )
    fields = sub.required_fields(bundle)
    assert fields == {"quality", "latency_p95"}

    # 'governance' is not in the bundle → not in required_fields,
    # even though it has no observations (⊥) in the DB.
    assert "governance" not in fields

    # Empty bundle → empty set.
    assert sub.required_fields(()) == set()

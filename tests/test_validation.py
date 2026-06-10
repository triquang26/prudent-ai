"""P5 V1 gate tests — the C2 demonstration on a controlled slice.

Constructs a slice where the cheapest config is the WORST on quality (cheap=bad),
masks quality (the binding axis), and asserts the C2 pattern:
  - observed-Pareto (B2) / imputation (B3) / cost-accuracy (B6) commit and
    HIDDEN-VIOLATE the true quality constraint;
  - the selective rule ABSTAINS → zero hidden violations;
  - the oracle (B5) never violates.
Plus: masking enforcement (no rule except the oracle can read the masked axis).
"""

from __future__ import annotations

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from prudent_ai.solver import Phi
from prudent_ai.substrate import Substrate
from prudent_ai.substrate.orm import (
    Component,
    Config,
    ConfigComponent,
    Source,
)
from prudent_ai.substrate.orm import (
    Observation as ObsORM,
)
from prudent_ai.validation import ALL_RULES, MaskAndPredict
from prudent_ai.validation.harness import BenchmarkSubstrate, MaskedSubstrate


def _i(session, model, **kw):
    session.execute(sqlite_insert(model).values(**kw).on_conflict_do_nothing())


def _seed(sub: Substrate) -> None:
    """tau='gt': cheap config is low-quality; dear config is high-quality.

    (cost, quality): cheap=(1.0, 0.50), mid=(5.0, 0.80), dear=(9.0, 0.95).
    A query quality≥0.8 is satisfied only by mid/dear; masking quality makes a
    cost-minimizer pick 'cheap' (q=0.50) → violates the true quality floor.
    """
    s = sub._session
    _i(s, Source, evidence_id="gt", source_type="benchmark", citation="gt",
       snapshot_version="1")
    for cid, cost, q in [("cheap", 1.0, 0.50), ("mid", 5.0, 0.80), ("dear", 9.0, 0.95)]:
        _i(s, Component, id=f"m-{cid}", kind="model", name=cid)
        _i(s, Config, id=cid, tau="gt")
        _i(s, ConfigComponent, config_id=cid, component_id=f"m-{cid}")
        for axis, val, oid in (("cost", cost, f"{cid}-c"), ("quality", q, f"{cid}-q")):
            _i(s, ObsORM, obs_id=oid, config_id=cid, axis=axis, value_num=val,
               value_cat=None, confidence="H", evidence_id="gt", hardware_tier="hw",
               dataset="d", split="test", decoding_cfg="x", obs_date="2026")
    s.commit()


def _queries(h):
    # bind quality only; threshold 0.8 (cheap fails, mid/dear pass)
    from prudent_ai.solver import make_query
    return [make_query("gt", [("quality", ">=", 0.8)], label="q-bound")]


def test_c2_masking_quality_baselines_violate_selective_abstains():
    sub = Substrate(":memory:")
    _seed(sub)
    h = MaskAndPredict(sub, kappa=("H",), phi=Phi.POINT)
    qs = _queries(h)
    rep = h.run(ALL_RULES, "gt", ("quality",), "quality", queries=qs)
    sub.close()
    r = rep.rules

    # Baselines that commit-while-blind violate the true quality floor.
    assert r["B2_observed_pareto"]["hidden_violation_rate"] == 1.0
    assert r["B3_imputation"]["hidden_violation_rate"] == 1.0
    assert r["B6_cost_accuracy"]["hidden_violation_rate"] == 1.0
    # Selective abstains → no commit, no violation.
    assert r["selective"]["n_commit"] == 0
    assert r["selective"]["hidden_violation_rate"] == 0.0
    # Oracle never violates.
    assert r["B5_oracle"]["hidden_violation_rate"] == 0.0


def test_masking_is_enforced():
    """MaskedSubstrate hides the axis from cell(); candidates() unaffected."""
    sub = Substrate(":memory:")
    _seed(sub)
    masked = MaskedSubstrate(sub, "quality")
    # quality hidden, cost visible
    assert masked.cell("cheap", "quality") == []
    assert len(masked.cell("cheap", "cost")) == 1
    assert len(masked.candidates("gt")) == 3
    sub.close()


def test_masking_latency_does_not_falsely_bite():
    """Sanity: with a benign masked axis (cost here is the objective, mask nothing
    binding badly), the oracle and a correct rule agree — guards against the harness
    flagging violations everywhere."""
    sub = Substrate(":memory:")
    _seed(sub)
    h = MaskAndPredict(sub, kappa=("H",), phi=Phi.POINT)
    from prudent_ai.solver import make_query
    # quality≥0.4 — cheap (0.5) already satisfies, so masking quality should NOT
    # force a violation (cheap is genuinely feasible).
    qs = [make_query("gt", [("quality", ">=", 0.4)], label="loose")]
    rep = h.run(ALL_RULES, "gt", ("quality",), "quality", queries=qs)
    sub.close()
    # B2 commits 'cheap' which truly satisfies quality≥0.4 → no violation
    assert rep.rules["B2_observed_pareto"]["hidden_violation_rate"] == 0.0


class _Cand:
    def __init__(self, cid: str) -> None:
        self.id = cid


class _StubSub:
    """Minimal substrate stub: candidates(tau) by τ, delegating cell/etc."""

    def __init__(self, cands_by_tau: dict[str, list[str]]) -> None:
        self._by_tau = cands_by_tau
        self.sentinel = "ok"

    def candidates(self, tau):
        return [_Cand(c) for c in self._by_tau.get(tau, [])]

    def cell(self, x, a):
        return [("cell", x, a)]

    def required_fields(self, bundle):
        return ("rf", bundle)


def test_benchmark_substrate_filters_to_one_benchmark():
    """BenchmarkSubstrate restricts a routerbench τ to config_ids ending -{bench}."""
    ids = [
        "rb-claude-v2-mmlu",
        "rb-gpt-4-1106-preview-mmlu",
        "rb-mistralai-mistral-7b-chat-hellaswag",
        "rb-meta-llama-2-70b-chat-arc-challenge",
        "rb-zero-one-ai-yi-34b-chat-mmlu",
    ]
    stub = _StubSub({"routerbench": ids, "function-calling": ["bfcl-a", "bfcl-b"]})

    bs = BenchmarkSubstrate(stub, "mmlu")
    got = sorted(c.id for c in bs.candidates("routerbench"))
    assert got == [
        "rb-claude-v2-mmlu",
        "rb-gpt-4-1106-preview-mmlu",
        "rb-zero-one-ai-yi-34b-chat-mmlu",
    ]
    # every returned config really ends with the benchmark suffix
    assert all(c.id.endswith("-mmlu") for c in bs.candidates("routerbench"))

    # a benchmark with a hyphen in its name is matched as a whole suffix
    bs_arc = BenchmarkSubstrate(stub, "arc-challenge")
    assert [c.id for c in bs_arc.candidates("routerbench")] == [
        "rb-meta-llama-2-70b-chat-arc-challenge"
    ]

    # non-routerbench τ is delegated unchanged (no filtering)
    assert [c.id for c in bs.candidates("function-calling")] == ["bfcl-a", "bfcl-b"]

    # cell / required_fields / __getattr__ all delegate to the wrapped substrate
    assert bs.cell("x", "quality") == [("cell", "x", "quality")]
    assert bs.required_fields("bundle") == ("rf", "bundle")
    assert bs.sentinel == "ok"

# 9 Reproducibility, Responsible-AI Metadata, and Talk

This section is the artifact half of the submission. It documents how every number in
§§5–7 is regenerated from a clean checkout, what was frozen and where it lives, and the
Responsible-AI metadata the Evaluation-track norms require; it closes with the talk
outline. The governing principle is the same C7 firewall that organizes the code: a
reviewer should be able to reproduce a claim *without* reading raw evidence — only the
solver and validation layers ever touch the substrate, so a re-run reads exactly what the
paper reads.

## 9.1 Repository layout — four layers, one firewall

The codebase is `src/prudent_ai/`, an OOP src-layout package under a uv-managed,
project-local `.venv` (Python pinned to 3.12 via `.python-version`; dependencies pinned in
`pyproject.toml`). Four subpackages realize the four-layer separation the formalism (§3.3)
demands, and the dependency arrows run **strictly one way** — analysis → solver/validation
→ substrate — never the reverse:

| Layer | Module | Responsibility | Reads substrate? |
|---|---|---|---|
| **Substrate** | `prudent_ai.substrate` | the evidential store: observations with provenance, $\bot$-via-absence under $\kappa$ (§4) | owns it |
| **Solver** | `prudent_ai.solver` | `classify_query`, `right_size`, `voi_for_axis`, `Phi`, `make_query`, `REGIME_LADDER`, `ALL_AXES`, `FULL`; the **C7 interface** `candidates` / `cell` / `required_fields` | only via the interface |
| **Validation** | `prudent_ai.validation` | the baseline grid `ALL_RULES` (B1–B6 + selective), `MaskAndPredict`, `MaskedSubstrate` | only via solver |
| **Analysis** | `prudent_ai.analysis` | `decidability_map`, `empirical_prior_map`, `procedure_eval`, `validation_run.ValidationRunner` — the scripts that emit `outputs/p3…p5/` | never directly |

The **C7 firewall** (the immutable substrate$\leftrightarrow$solver interface) is the
reproducibility guarantee made structural: because no analysis script can issue a raw read,
a re-run cannot silently impute a missing axis. `⊥` stays `⊥`. Any multi-query analysis
wraps the store as `CachedSubstrate(Substrate('data/apt_substrate.db'))` — the cache is a
pure read-through accelerator (a bare `Substrate` re-opens the connection per cell and a
1716-query battery will hang), so it changes wall-clock time, never a result.

## 9.2 Frozen snapshots and bucket paths

Every claim is read off **frozen** inputs; nothing in the paper depends on a live network
fetch. There are three frozen tiers, mirrored to the HuggingFace bucket
`hf://buckets/twanghcmut/prudent-ai-bucket` (root `PrudentAI/`):

1. **The substrate snapshot** — `data/apt_substrate.db`: **182 configurations** over three
   archetypes (function-calling = 109 BFCL configs; inference-serving = 42 MLPerf + ML.ENERGY;
   general-qa = 31 HELM), carrying **3392 observations** (478 H / 2666 M / 248 L) on **5 of 8
   axes** — `governance`, `reviewer_burden`, `memory_hw` are $\bot$ everywhere. The DB is
   **not reseeded**; it is the single committed artifact §§4–7 read.
2. **The real-traffic query prior** — the **1716**-deployment **ZenML** empirical prior,
   loaded from its frozen on-disk snapshot via `load_prior()` (no network). This is the
   distribution over which the decidability map (§5) and the procedure action-rates (§6) are
   evaluated.
3. **The RouterBench corpus** — the frozen `routerbench` `.pkl` snapshot used by the V1
   validation grid as the H-confidence (but cross-benchmark-confounded; §7.6) slice.

Bucket conventions (per the data interface, `prudent_ai.storage.BucketStorage`): `Plan/` and
`Paper/` are pull-only; per-experiment artifacts live under `exp/<id>-<slug>/`; shared
datasets under `shared/<name>/`. To reproduce from scratch:

```bash
uv venv --python 3.12 .venv && uv sync --extra dev
export PYTHONNOUSERSITE=1
bucket.pull("shared/apt_substrate")          # if the DB is not in the checkout
PYTHONNOUSERSITE=1 uv run python -m prudent_ai.analysis.decidability_map    # → outputs/p3
PYTHONNOUSERSITE=1 uv run python -m prudent_ai.analysis.empirical_prior_map # → outputs/p3
PYTHONNOUSERSITE=1 uv run python -m prudent_ai.analysis.procedure_eval      # → outputs/p4
PYTHONNOUSERSITE=1 uv run python -m prudent_ai.analysis.validation_run      # → outputs/p5
```

`PYTHONNOUSERSITE=1` is mandatory before every command — it keeps `~/.local` packages out of
the pinned env, the single most common source of a non-reproducing run. `outputs/` is
gitignored; results are pushed to the bucket, never committed, so the repo stays a
*recipe* and the bucket holds the *artifacts*.

## 9.3 Determinism

All stochasticity is funnelled through one seed. Every bootstrap, VoI tie-break, and V2
acquisition draw is **locally seeded `Random(12345)`**; there is no process-global RNG and no
unseeded call site. Concretely: the P3 decidability fractions use $\varphi$=point,
$\kappa$=H+M, percentile bootstrap $n{=}1000$ under `Random(12345)`; the P4 procedure and VoI
ranking run at $\lambda{=}1.0$, seed 12345 (coverage–risk on a seeded subsample of 600 of the
1716); the P5 `ValidationRunner` V2 acquisition draws under seed 12345. Two consequences a
reviewer can check: (i) re-running any analysis byte-reproduces the JSON in `outputs/`; (ii)
the exact identity $\mathrm{VoI}(a^\*)=\Delta(R)=\delta\lambda/(\delta+\lambda)$ is pinned by a
unit test, not asserted — it holds analytically, so no seed can perturb it.

## 9.4 Test suite

The suite is **43 tests**, all passing
(`PYTHONNOUSERSITE=1 uv run pytest tests/ -q` → `43 passed`). They are not smoke tests;
each guards a load-bearing claim:

| File | Guards |
|---|---|
| `test_smoke.py` | config YAML round-trip + `Experiment.execute` determinism (the reproducible lifecycle) |
| `test_invariance.py` | the C7 firewall — solver reads only via `candidates`/`cell`/`required_fields` |
| `test_decidability.py` | DV1 classifier: decidable / underdetermined / infeasible-under-$E$ verdicts |
| `test_query_prior.py` | the 1716-deployment ZenML prior loads from snapshot and binds the expected axes |
| `test_procedure.py` | the three-state rule **and** the exact identity `test_voi_equals_delta_R` ($\mathrm{VoI}(a^\*){=}\Delta(R)$) |
| `test_guarantee.py` | the distribution-free coverage guarantee $P(\text{correct}\mid\text{commit})\ge 1-\alpha$ |
| `test_validation.py` | the V1 baseline grid B1–B6 + selective; hidden-violation accounting |
| `test_routerbench.py` | the RouterBench frozen-snapshot slice and its documented confound |

The single command above is the acceptance gate: green = the paper's machinery is intact.

## 9.5 The experiment DAG (provenance of the result)

The research is a DAG of vault nodes, one git branch per node; the paper is the leaf. The
spine from interface to write-up:

```
P1 1pc3v3 (interface kit, C7)
  → P2 d5fnki (scoped extraction → substrate)
    → P3 u483mt (decidability map, C1)
      → Q2 ana6e6 (real-traffic query prior, 91.1%)
        → P4 8v9cvt (selective procedure + VoI + guarantee, C3)
          → RB 4iezqz (RouterBench slice)
            → P5 jal8id (validation V1/V2, C2)
              → P6 worcj5 (paper + scale)  ← this submission
```

Each edge is a real branch transition; a reviewer reading `/exp-traverse up` from `worcj5`
recovers the exact lineage of every number. The DAG is the audit trail: no claim in the
paper exists without a node that produced it.

## 9.6 Responsible-AI metadata (Evaluation-track norms)

- **Intended use.** A *pre-deployment, evidential* right-sizing aid: it answers "does the
  evidence identify the minimum-sufficient configuration?" and, when it does not, names what
  to measure. It is **not** a runtime router and **not** a safety certifier — the coverage
  guarantee is over *evidential identification*, not real-world outcome.
- **Data provenance & licenses.** All evidence is public benchmark output — BFCL, MLPerf,
  ML.ENERGY, HELM, RouterBench — ingested under each corpus's own license with `source_type`,
  `citation`, and `snapshot_version` carried on **every** observation (the FK to `source` is
  enforced at the storage layer). The ZenML deployment prior is aggregate query structure, not
  user data. **No human-subjects data, no PII.**
- **Known limitations / failure modes.** (i) Three axes (`governance`, `reviewer_burden`,
  `memory_hw`) are $\bot$ across the entire corpus, so the procedure can only *name* them as
  blocking, never certify them — the central honest limitation. (ii) RouterBench `cost` varies
  by *benchmark* not by configuration, a documented cross-benchmark confound (§7.6); it is
  reported as a no-bite case, not a win. (iii) Significance on the C2/C3 effects is on small
  biting slices (5 abstentions on the BFCL mask-quality case) — the scale-up is the open
  forward-looking item (§9.7 status).
- **Compute & environmental cost.** Negligible and CPU-only: the entire pipeline is SQLite
  queries plus seeded bootstraps; no model training or GPU inference occurs in producing any
  paper number. The energy *axis* is measured evidence ingested from ML.ENERGY, not consumed
  by us.
- **Misuse / dual-use.** The deliberate design choice "$\bot$ stays $\bot$" is itself a safety
  property: the system cannot be made to launder a missing governance or reviewer-burden axis
  into a confident commit. The risk to flag for deployers is *over-trust of a COMMIT* — the
  guarantee is conditional on the evidence being well-calibrated, which §7 stress-tests but a
  real regulated setting must re-validate.

## 9.7 Talk outline (one hook · one figure · one result · one forward)

A four-beat talk an outsider "gets" in two minutes (master plan §15, P6):

1. **Hook — "underdetermined."** Open on the uncomfortable fact: of **1716 real LLM
   deployments**, **91.1%** of the right-sizing decisions are *not identifiable from the
   evidence that exists*. Not "the estimate is noisy" — *the decision is non-identifiable*.
   And the cause is **structured**, not random: **55.6%** of deployments bind `governance` and
   **43.8%** bind `reviewer_burden`, two axes that are **100% $\bot$** in every public corpus.
   The community is sharpening estimates of axes nobody reports.
2. **Figure — the decidability map.** One slide: the DV1 map over
   {archetype $\times$ evidence-regime $\times$ confidence}, blocks shading from
   decidable→underdetermined→infeasible as you walk the regime ladder. It makes the abstract
   word "underdetermined" a picture, and shows the blind spots are a *column* (the same three
   axes), not scatter.
3. **Result — V1, C2, "x > y."** The painful demonstration: on the biting slice, the three
   commit-while-blind leaderboard rules **B2 / B3 / B6** hidden-violate on **100%** of their
   commits (5/5 each) — they answer confidently and are wrong on a hidden constraint — while
   the **selective rule's hidden-violation rate is 0.0**: it refuses precisely when it cannot
   see. `hidden-violation(selective) = 0.0 ≪ 1.0 = hidden-violation(B2) = B3 = B6`. A clean
   "must beat B2 and B3" pass.
4. **Forward — VoI.** Abstention is not the end: the procedure says *what to measure next*,
   ranked by value of information, and that ranking is exact —
   $\mathrm{VoI}(a^\*) = \Delta(R) = \delta\lambda/(\delta+\lambda)$ — so the value of an
   acquisition and the irreducible-regret floor are **one object**. The forward ask: scale the
   biting slices to oral-grade significance and close the governance/reviewer-burden evidence
   gap the map exposes.

# REPRODUCE.md — clean-checkout reproduction of the APT P1→P6 pipeline

This is the end-to-end reproduction package for **prudent-ai** (APT: Evidence-Decidability
of AI Deployment Right-Sizing). Starting from a clean checkout it (a) builds the evidential
substrate, (b) regenerates every published number in `outputs/`, (c) renders every paper
figure, and (d) passes the full test gate.

Everything here was run and verified on this host. Numbers are **deterministic** functions
of the frozen snapshots + fixed seeds (see [Determinism](#determinism)).

> **Always prefix every `uv`/`python` invocation with `PYTHONNOUSERSITE=1`** so `~/.local`
> packages never leak into the project venv. The one-liners below assume you `export` it once
> per shell.

---

## 0. Environment

Python is pinned to **3.12** (`.python-version`). Deps are pinned in `pyproject.toml`
(notably **pandas** and **matplotlib** were added for P5/P6 analysis + figures;
runtime: `matplotlib`, `numpy>=2`, `pandas`, `pyyaml`, `sqlalchemy>=2`; dev: `pytest`, `ruff`).

```bash
cd prudent-ai
export PYTHONNOUSERSITE=1          # keep ~/.local out of the venv (do this in every shell)
uv venv --python 3.12 .venv        # new, isolated venv
uv sync --extra dev                # install pinned runtime + dev deps
uv run pytest -q                   # smoke: should print "43 passed"
```

`uv run` auto-activates `.venv`; you do **not** need to `source` it. Never `pip install`
into the venv ad hoc — that breaks reproducibility. Add a dep via `pyproject.toml` + `uv sync`.

---

## 1. Get the data

The pipeline reads one SQLite file, `data/apt_substrate.db`, plus two frozen upstream
snapshots (`data/zenml_llmops_snapshot.json`, `data/routerbench_0shot.pkl`). You have **two
options**: pull the frozen artifacts from the HF bucket (fast, byte-identical), or regenerate
the substrate from the seeders (slower, still deterministic).

### Option A — pull frozen artifacts from the bucket (recommended)

Per-experiment data lives under `PrudentAI/exp/<id>-<slug>/` in the bucket
`hf://buckets/twanghcmut/prudent-ai-bucket`. The seeded substrate is the P2 node's artifact;
the frozen snapshots are attached to the P3-empirical / RouterBench nodes.

```python
# PYTHONNOUSERSITE=1 uv run python - <<'PY'
from prudent_ai.storage import BucketStorage
b = BucketStorage()
# Seeded substrate (HELM/BFCL/ML.ENERGY/MLPerf + RouterBench), frozen at P2/RB:
b.pull("exp/4iezqz-validation-data-routerbench", local="data/exp/4iezqz-validation-data-routerbench")
b.pull("exp/d5fnki-p2-scoped-extraction",        local="data/exp/d5fnki-p2-scoped-extraction")
# Frozen ZenML LLMOps snapshot (C3) used by the P3 empirical prior:
b.pull("exp/ana6e6-p3-empirical-query-prior",    local="data/exp/ana6e6-p3-empirical-query-prior")
PY
```

Then place the artifacts where the scripts expect them (script defaults are repo-root-relative):

```bash
cp data/exp/4iezqz-validation-data-routerbench/apt_substrate.db  data/apt_substrate.db
cp data/exp/4iezqz-validation-data-routerbench/routerbench_0shot.pkl data/routerbench_0shot.pkl
cp data/exp/ana6e6-p3-empirical-query-prior/zenml_llmops_snapshot.json data/zenml_llmops_snapshot.json
```

Equivalent raw `hf` form (no Python):

```bash
hf sync hf://buckets/twanghcmut/prudent-ai-bucket/PrudentAI/exp/4iezqz-validation-data-routerbench \
        ./data/exp/4iezqz-validation-data-routerbench
```

### Option B — regenerate the substrate from scratch

The substrate is reproducible from the source seeders. **P2 sources** (HELM Lite, BFCL,
ML.ENERGY, MLPerf) are seeded by one script; **RouterBench** has its own seeder; the **ZenML
LLMOps** corpus (used by the P3 empirical prior, not the substrate DB) auto-fetches and
**freezes itself** to `data/zenml_llmops_snapshot.json` on first run.

```bash
export PYTHONNOUSERSITE=1
# (1) P2: HELM Lite + BFCL + ML.ENERGY + MLPerf v5.0  ->  data/apt_substrate.db
uv run python scripts/seed_p2.py                    # optional: --db data/apt_substrate.db
# (2) RouterBench GT slice (tau='routerbench', snapshot 2024-03)  ->  same DB
uv run python -m prudent_ai.substrate.routerbench.seeder   # optional: --db ... / --quiet
```

The ZenML snapshot needs no explicit step: the first run of `scripts/run_p3_empirical.py`
calls `ZenMLClient.fetch_all_rows(cache_path="data/zenml_llmops_snapshot.json")`, which loads
the snapshot if present and otherwise fetches from the HF datasets-server and writes it
(C3-frozen). To reproduce the *exact* published prior, prefer pulling the snapshot (Option A);
a live re-fetch can drift if upstream changes.

Both seeders are **idempotent** (`INSERT OR IGNORE` / `on_conflict_do_nothing`), so re-running
them never duplicates rows — running A then B, or re-running B, converges to the same DB.

---

## 2. Reproduce each phase's numbers

All run scripts default to `DB_PATH = data/apt_substrate.db`, `φ = point`, and seed `12345`
where stochastic. Each writes a `.json` (numbers + provenance metadata) and a `.md`
(human-readable tables) into `outputs/<phase>/`. Run from repo root:

```bash
export PYTHONNOUSERSITE=1

# P3 — decidability map (DV1): %decidable/underdetermined/infeasible over the regime ladder.
uv run python scripts/run_p3_map.py
#   -> outputs/p3/decidability_map.json , decidability_map.md
#   (slowest script — bootstrap CIs over the full ladder × 3 use-cases)

# P3 — empirical query prior: weights the map by a real ZenML LLMOps query distribution.
uv run python scripts/run_p3_empirical.py
#   -> outputs/p3/empirical_prior_map.json , empirical_prior_map.md

# P4 — selective procedure eval (DV5 VoI lift): 1716-query battery, VoI = Δ(R) acquire-next.
uv run python scripts/run_p4_eval.py
#   -> outputs/p4/procedure_eval.json , procedure_eval.md

# P4 — coverage–risk guarantee (DV4): selective coverage at realized risk, α calibrations.
uv run python scripts/run_p4_guarantee.py
#   -> outputs/p4/coverage_risk.json , coverage_risk.md   (600-query operating curve)

# P5 — V1 validation (controlled C2 slice) + V2.
uv run python scripts/run_p5.py
#   -> outputs/p5/validation.json , validation.md

# P5 — scaled validation (the headline C2 result): 7 biting slices, 119 queries.
uv run python scripts/run_p5_scaled.py
#   -> outputs/p5/validation_scaled.json , validation_scaled.md
```

**Headline numbers you should see** (verified on this host):

- **P5 scaled (DV3 hidden-violation, C2):** pooled over 7 biting slices (BFCL + 6 RouterBench
  benchmarks: mmlu, hellaswag, arc-challenge, winogrande, mbpp, grade-school-math),
  **n = 119** queries. Both imputing baselines **B2 (observed-Pareto)** and **B3 (imputation)**
  hidden-violate at **0.882**, the **selective** rule at **0.000**
  (Δ = 0.882, 95% CI ≈ [0.824, 0.941], one-sided p ≈ 0, **significant**).
- **P4 eval:** battery of **1716** queries in the `full` regime; acquire-next ranks the omitted
  binding axis by VoI = Δ(R).
- **P4 guarantee:** **600**-query coverage–risk curve at zero realized risk on committed queries.

### P6 — render the paper figures

```bash
uv run python scripts/make_figures.py
#   -> docs/paper/figures/{fig_decidability_map, fig_regime_ladder, fig_coverage_risk,
#                          fig_hidden_violation, fig_voi_identity}.png
```

`make_figures.py` is a pure consumer of the `outputs/*.json` artifacts above (plus a live,
in-memory §8.2 gadget for the VoI panel). It uses the headless `Agg` backend. The VoI panel
re-derives VoI(latency) through the solver and asserts it equals the limit-theorem identity
**Δ(R) = δλ/(δ+λ)**; on this host max |implemented − theoretical| = **1.1e-16** (i.e. exact).
Figures are tracked in git (`docs/paper/figures/`); `outputs/` and `data/` are gitignored —
push results to the bucket, don't commit them.

---

## 3. Test gate

```bash
PYTHONNOUSERSITE=1 uv run pytest -q
# 43 passed
```

The four anchor tests that pin the implementation to the formalism:

| Test file | What it proves |
|---|---|
| `tests/test_invariance.py` | **C7 firewall.** On the same query, both solvers emit an *identical multiset* of substrate calls (`candidates`/`cell`/`required_fields`) — φ, κ, certifier are solver-side; the substrate is solver-agnostic and never imputed. |
| `tests/test_decidability.py` | **§8.2 two-world gadget.** With the binding axis (latency) outside the regime R={quality,cost} the query is UNDERDETERMINED; admitting latency makes it DECIDABLE and the argmin matches the world. Plus C7 read-only + determinism. |
| `tests/test_procedure.py` | **VoI = Δ(R).** On the §8.2 gadget the implemented VoI of the omitted binding axis equals Δ(R) = δλ/(δ+λ) exactly (the §8.7 identity / limit theorem). |
| `tests/test_validation.py` | **C2 demonstration.** On a controlled slice (cheapest config is worst on the masked quality axis) B2/B3/B6 commit and HIDDEN-VIOLATE while the selective rule ABSTAINS (zero hidden violations) and the oracle never violates; masking is enforced. |

(`test_guarantee.py`, `test_query_prior.py`, `test_routerbench.py`, `test_smoke.py` round out
the 43: P4 coverage math, the empirical prior, the RouterBench parser, and the
config/determinism round-trip.)

---

## 4. Experiment DAG (vault) and how skills find the current node

Research is a DAG of markdown nodes in the **vault** (`prudent-ai-vault`, reached via the
`.experiments` symlink — its own git repo). **1 experiment = 1 vault node = 1 `exp/<id>-<slug>`
git branch** in this code repo. The `/exp-*` skills resolve the "current node" from the
**current git branch** (`git checkout exp/<id>-<slug>` to switch experiments).

Lineage of this pipeline (parent → child):

```
P1 1pc3v3 p1-evidential-substrate
└─ P2 d5fnki p2-scoped-extraction
   └─ P3 u483mt p3-decidability-map
      └─ Q2 ana6e6 p3-empirical-query-prior
         └─ P4 8v9cvt p4-selective-procedure
            └─ RB 4iezqz validation-data-routerbench
               └─ P5 jal8id p5-validation-v1
                  └─ P6 worcj5 p6-paper-and-scale
                     └─ polish tfumqf p6-figures-ablation-review   ← current branch
```

Read-only navigation (safe to run anytime): `/exp-context`, `/exp-status`, `/exp-traverse`,
`/exp-compare`. State-changing skills follow the mandatory 4-step discipline
(Inspect → Preview → explicit `y`/`ok` → Execute). The vault is committed atomically by the
skills themselves — never `git add` the vault by hand.

The substrate, snapshots, and per-phase outputs above mirror the bucket layout
`PrudentAI/exp/<id>-<slug>/` (e.g. `d5fnki` → seeded DB, `ana6e6` → ZenML snapshot,
`8v9cvt` → P4 jsons, `jal8id` → P5 v1, `worcj5` → scaled validation).

---

## 5. Determinism

The pipeline is reproducible by construction:

- **Fixed seeds.** Stochastic steps use seed **12345**: bootstrap CIs in the decidability /
  empirical maps use a locally-constructed `random.Random(12345)`; the P4 VoI battery
  (`VOI_SEED`), P4 guarantee sampling (`SAMPLE_SEED`), P5 V2 (`V2_SEED`), and P5 scaled
  (`SEED`) all = 12345. The repo's `seed_everything` (`reproducibility.py`) is the single
  place new RNGs get seeded.
- **Frozen snapshots (C3).** The ZenML LLMOps corpus is pinned to
  `data/zenml_llmops_snapshot.json` and RouterBench to the `2024-03` snapshot
  (`data/routerbench_0shot.pkl`) — analyses load the frozen file rather than re-fetching, so
  numbers don't drift with upstream.
- **Idempotent seeding.** Both seeders use `INSERT OR IGNORE` / `on_conflict_do_nothing`, so
  re-seeding (or seeding P2 then RouterBench into the same DB) is a no-op on existing rows and
  converges to the same substrate.
- **C7 invariance.** No phase imputes a missing axis; `⊥` stays `⊥`. All substrate reads go
  through `candidates`/`cell` (multi-query runs wrap `CachedSubstrate(Substrate('data/apt_substrate.db'))`
  for memoization without changing results), which `test_invariance.py` enforces.

---

## 6. One-shot: clean checkout → all numbers + figures

Minimal sequence. Step (0) builds the env; (1) gets data — **pick A (pull) or B (regenerate)**;
(2) regenerates every number; (3) renders figures; (4) gates on tests.

```bash
# (0) Environment
cd prudent-ai
export PYTHONNOUSERSITE=1
uv venv --python 3.12 .venv
uv sync --extra dev

# (1) Data — choose ONE:
#   A) pull frozen artifacts (byte-identical, fast):
uv run python - <<'PY'
from prudent_ai.storage import BucketStorage
b = BucketStorage()
for node in ("exp/4iezqz-validation-data-routerbench",
             "exp/d5fnki-p2-scoped-extraction",
             "exp/ana6e6-p3-empirical-query-prior"):
    b.pull(node, local=f"data/{node}")
PY
cp data/exp/4iezqz-validation-data-routerbench/apt_substrate.db        data/apt_substrate.db
cp data/exp/4iezqz-validation-data-routerbench/routerbench_0shot.pkl   data/routerbench_0shot.pkl
cp data/exp/ana6e6-p3-empirical-query-prior/zenml_llmops_snapshot.json data/zenml_llmops_snapshot.json
#   B) OR regenerate from seeders instead of the two cp/pull blocks above:
# uv run python scripts/seed_p2.py
# uv run python -m prudent_ai.substrate.routerbench.seeder

# (2) Reproduce every phase number
uv run python scripts/run_p3_map.py
uv run python scripts/run_p3_empirical.py
uv run python scripts/run_p4_eval.py
uv run python scripts/run_p4_guarantee.py
uv run python scripts/run_p5.py
uv run python scripts/run_p5_scaled.py

# (3) Render the paper figures
uv run python scripts/make_figures.py

# (4) Test gate
uv run pytest -q          # expect: 43 passed
```

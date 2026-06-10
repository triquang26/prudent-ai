# P1_TASK — Claude Code harness: build the evidential substrate

**Goal.** Build P1 (the evidential substrate) to its gate. The gate is a single passing test
(`test_interface_invariance`), not a feature list. Read the two spec files in the repo *first*; they are
authoritative and the interface contract in them is **immutable**.

- `APT_P0_formalism_spine.md` — §3 observation model, §10 schema requirements.
- `APT_P1_interface_kit.md` — §2 contract, §3 reference schema, §4 baseline query, §5 stubs, §6 the gate test.

---

## Read first (seeded papers — extract the listed thing only)

| Paper | What to take | NOT to take |
|---|---|---|
| **HELM / HELM Lite** (2211.09110 + leaderboard) | the seed data: per (model, scenario), which fields are reportable → observation rows | — |
| AXCELL `2020.emnlp-main.692` · MOLE `2505.19800` · Computing-Resources `2510.13621` · NLP-repro `2023.acl-long.568` | **the lesson only**: auto-extraction is unreliable (F1 25.8, ~67%, sticky 60–89% omission) → seed semi-auto, log provenance + confidence, treat `⊥` as signal | their *pipelines* — do **not** build extraction tooling (that is P2) |

---

## ⚠ Scope guardrails (read twice)

1. **P1 = substrate + tiny HELM-Lite seed + invariance test.** NOT P2 (multi-source extraction, κ-tuning, AXCELL/MOLE tooling). Do **not** build an extraction pipeline.
2. **`⊥` stays `⊥`. Never impute, fill, default, or estimate a missing axis.** When HELM gives no evidence for energy / latency / governance / reviewer_burden, the cell is empty *on purpose* — that emptiness is the central finding the whole project measures. Filling it silently destroys the thesis. If tempted to "complete the data," stop.
3. **Do not change the interface contract** (`candidates` / `cell` / `required_fields`). It is fixed by `APT_P1_interface_kit.md §2`.
4. **First pass = lowest fidelity that passes the gate.** No indices, no schema hardening, no optimization. Mock `interval_satisfies` / `prob_satisfies` / `expected_cost` with the crudest logic — the gate test does not exercise their correctness.

---

## INPUT

- The two spec files above (in repo).
- HELM Lite leaderboard (read-only source for the seed).
- The seeded papers (read for the items in the table above).

## OUTPUT (deliverables, in repo)

- `schema.sql` — reference schema from kit §3, in SQLite; FKs enforced.
- `seed_helm_lite.py` — loads HELM Lite → `observation` rows, each with `evidence_id → source`, `confidence`, `source_type`, `context`. Semi-auto; log every value's origin.
- `substrate.py` — the three interface functions exactly per kit §2 (κ-free, φ-free).
- `baseline_query.sql` — Appendix-E reportability query (kit §4), runnable.
- `solvers_stub.py` — the two stubs + shared `belief()` (kit §5).
- `test_invariance.py` — `test_interface_invariance` (kit §6), **PASSING**.
- `data_dictionary.md` — one row per (table, column): meaning, type, source.

## REQUIREMENTS (= acceptance criteria; the gate)

- [ ] `observation` is the atomic unit — **many rows per (config, axis)** supported and demonstrated.
- [ ] ≥1 cell holds **multiple observations** with differing `confidence` and `context`.
- [ ] Every observation has provenance: `evidence_id` FK resolves to a `source` row. **No bare values** (C2).
- [ ] `required_fields(c)` is **syntactic** = `{ k.axis for k in c }`. Never solves, never returns "binding" axes.
- [ ] `is_missing(x, a | κ)` returns correct `⊥` under both `κ=(H,M)` and `κ=(H,M,L)`.
- [ ] Baseline query runs; its `is_missing` column is **non-degenerate** (some cells present, several `⊥`).
- [ ] **`test_invariance.py` PASSES** — the two solvers produce an identical multiset of substrate calls. ← THE gate.

## Investigate (figure out — do not wait to be told)

- Which HELM Lite columns map to which of the 8 axes; **which axes have *no* HELM evidence** (expect ~5–6 of 8 → confirm and leave them `⊥`, do not fill).
- A confidence policy by `source_type` (e.g. measured vs leaderboard vs paper_estimated). Pick one, **document the rule** in the data dictionary, justify from the extraction-paper lesson.
- `value_num` vs `value_cat` per axis (numeric for quality/cost/latency/energy; categorical for governance/hardware/privacy/review).

## Report back

- The decidability-relevant headline of the seed: of the 8 axes, how many are populated vs `⊥` from HELM alone, and which. (This previews DV1 — present it, do not act on it.)
- Confirmation the gate test passes, and the recorded substrate-call signatures from both solvers.

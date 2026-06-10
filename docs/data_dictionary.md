# Data Dictionary — APT Evidential Substrate (P1)

This document is the canonical reference for every table and column in the APT
evidential substrate (`schema.sql`).  It also defines the confidence policy and
the meaning of ⊥ (evidential absence).

---

## Confidence Policy

Confidence is assigned at ingestion time based on the **source_type** of the
observation's provenance record.  It encodes how much trust to place in the
reported value — not a statistical interval, but an evidence-quality tier.

| source_type | assigned confidence | justification |
|---|---|---|
| `measured` | **H** | Direct, reproducible measurement under controlled conditions with full methodology disclosure.  Highest epistemic warrant. |
| `leaderboard` | **M** | Auto-extracted or community-submitted values.  AXCELL automated extraction F1 ~25.8%; NLP reproducibility studies report sticky omission rates of 60–89%; MOLE reliability ~67%.  Meaningful uncertainty regardless of the leaderboard's reputation. |
| `paper_reported` | **M** | Author-reported results in a peer-reviewed or arXiv paper.  Methodology is disclosed but the value is not independently verified.  Reproduction gap is non-trivial (NLP-repro omission 60–89%). |
| `paper_estimated` | **L** | Value extrapolated or back-calculated from paper figures, tables, or text — not directly stated.  Estimation error compounds on top of paper-reported uncertainty. |
| `vendor_doc` | **L** | Sourced from vendor documentation, marketing material, or product pages.  Conditions of measurement are rarely disclosed; values may reflect best-case configurations. |

---

## Tables

### component

Represents a single deployable unit: a model, adapter, quantisation level,
hardware configuration, or any other separable part of a deployment stack.

| column | type | constraints | meaning | source / provenance |
|---|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | Stable, human-readable identifier for the component. Naming convention: `<kind>-<slug>`, e.g. `model-gpt-4`, `provider-openai`. | Assigned at ingestion; must be unique across all component kinds. |
| `kind` | TEXT | NOT NULL | Broad category of the component.  Examples: `model`, `provider`, `adapter`, `quant`, `hardware`. | Controlled vocabulary; extend as needed but keep orthogonal. |
| `name` | TEXT | NOT NULL | Human-readable display name.  May differ from `id` (e.g. `id = model-gpt-4`, `name = GPT-4`). | Free text; used for reporting only. |

---

### config

A deployment configuration — a specific combination of components evaluated
under a particular task archetype (`tau`).  The config is the unit of
comparison in the APT decision procedure.

| column | type | constraints | meaning | source / provenance |
|---|---|---|---|---|
| `id` | TEXT | PRIMARY KEY | Stable identifier for the configuration.  Typically a slug describing the primary model, e.g. `gpt4-0314`. | Assigned at ingestion; referenced by `config_component` and `observation`. |
| `tau` | TEXT | NOT NULL | Deployment-context tag (task archetype).  Groups configs that are compared against each other.  Example: `general-qa`, `code-completion`, `clinical-triage`. | Defined per seeder; determines which configs `candidates(tau)` returns. |

---

### config_component

Many-to-many join table that records which components make up a configuration.
A single config may include several components (e.g. a base model, a LoRA
adapter, and a quantisation scheme).

| column | type | constraints | meaning | source / provenance |
|---|---|---|---|---|
| `config_id` | TEXT | NOT NULL, FK → `config(id)`, PK part | The configuration this row belongs to. | Foreign key; referential integrity enforced by `PRAGMA foreign_keys = ON`. |
| `component_id` | TEXT | NOT NULL, FK → `component(id)`, PK part | A component that is part of this configuration. | Foreign key; referential integrity enforced by `PRAGMA foreign_keys = ON`. |
| *(PK)* | | `PRIMARY KEY (config_id, component_id)` | Composite primary key prevents duplicate links. | Enforced by SQLite. |

---

### source

Provenance record for a set of observations.  Every `observation` row must
reference exactly one `source` row.  This is the mechanism by which APT
enforces constraint C2 (provenance must be traceable to a citable source).

| column | type | constraints | meaning | source / provenance |
|---|---|---|---|---|
| `evidence_id` | TEXT | PRIMARY KEY | Stable identifier for this provenance record.  Naming convention: `<source-slug>-<snapshot>`, e.g. `helm-lite-2023-11`. | Assigned at ingestion; referenced by `observation.evidence_id`. |
| `source_type` | TEXT | NOT NULL | Category of evidence source.  One of: `measured`, `leaderboard`, `paper_reported`, `paper_estimated`, `vendor_doc`.  Drives confidence assignment — see Confidence Policy above. | Controlled vocabulary; must match confidence policy table. |
| `citation` | TEXT | | Human-readable citation or BibTeX key.  Examples: `"Liang et al. 2022, arxiv 2211.09110"`, `"internal eval run 2024-03-15"`. | Free text; included in every seeder. |
| `snapshot_version` | TEXT | | Version or date of the evaluation harness / dataset snapshot used.  Critical for reproducibility (C3): the same model may score differently under different benchmark versions. | ISO date string (e.g. `2023-11`) or a commit hash. |

---

### observation

The core evidential table.  Each row records a single measured (or reported)
value on one right-sizing axis for one configuration, anchored to a provenance
record and decorated with evaluation context.

| column | type | constraints | meaning | notes |
|---|---|---|---|---|
| `obs_id` | TEXT | PRIMARY KEY | Stable, deterministic identifier for this observation.  Convention: `obs-<config_id>-<axis>-<evidence_id>`. | Deterministic IDs make the seeder idempotent (`INSERT OR IGNORE`). |
| `config_id` | TEXT | NOT NULL, FK → `config(id)` | The configuration this observation describes. | Foreign key; referential integrity enforced. |
| `axis` | TEXT | NOT NULL | One of the 8 APT right-sizing axes (see list below). | Axis vocabulary is fixed by the P1 formalism (C7). |
| `value_num` | REAL | | Numeric measurement.  NULL when the axis value is categorical. | Mutually exclusive with `value_cat`; exactly one must be non-NULL. |
| `value_cat` | TEXT | | Categorical measurement.  NULL when the axis value is numeric. | Mutually exclusive with `value_num`; exactly one must be non-NULL. |
| `confidence` | TEXT | NOT NULL, CHECK IN ('H','M','L') | Evidence quality tier assigned at ingestion per the Confidence Policy above. | Never NULL; never back-filled or upgraded after insertion without a new source row. |
| `evidence_id` | TEXT | NOT NULL, FK → `source(evidence_id)` | Provenance anchor.  Referential integrity is the provenance guarantee (C2). | Inserting a source row before the observation row is mandatory. |
| `hardware_tier` | TEXT | | Context: hardware class under which the observation was made.  Examples: `openai-api`, `a100-40gb`, `tpu-v4`. | NULL when not recorded.  Affects comparability of latency, throughput, energy, and memory_hw axes. |
| `dataset` | TEXT | | Context: benchmark or dataset name.  Examples: `mmlu`, `hellaswag`, `humaneval`. | NULL when not recorded.  Affects comparability of quality axis values. |
| `split` | TEXT | | Context: data split used.  Examples: `test`, `validation`, `dev`. | NULL when not recorded. |
| `decoding_cfg` | TEXT | | Context: decoding / sampling configuration identifier.  Examples: `temperature-0.0`, `greedy`, `beam-4`. | NULL when not recorded.  Critical for reproducibility: the same model may score differently under different decoding strategies. |
| `obs_date` | TEXT | | Context: when the observation was recorded, ISO-8601 format (e.g. `2023-11`). | NULL when not recorded.  Useful for detecting model drift across time. |

#### Axis vocabulary (8 axes)

| axis | type | unit / scale | what it measures |
|---|---|---|---|
| `quality` | numeric | 0–1 (accuracy / score fraction) | Task performance; benchmark accuracy, F1, EM, etc. |
| `latency_p95` | numeric | seconds | 95th-percentile end-to-end inference latency. |
| `throughput` | numeric | tokens/second or requests/second | Sustained processing rate under load. |
| `cost` | numeric | USD per 1 000 tokens (or per request) | Monetary inference cost.  Token counts are NOT a proxy — leave ⊥ when only counts are available. |
| `energy` | numeric | Wh per 1 000 tokens | Energy consumption per unit of output. |
| `memory_hw` | numeric | GB (GPU/TPU VRAM) | Peak hardware memory footprint during inference. |
| `governance` | categorical or numeric | deployment-policy tier | Compliance, safety, and policy constraints (e.g. data residency, audit trail). |
| `reviewer_burden` | numeric | hours per 100 outputs | Estimated human review effort required to validate model outputs. |

---

## ⊥ (Evidential Absence)

**⊥ is NOT a stored value.**  There is no `null`, sentinel, or placeholder row
that represents "we don't know."

A cell `(x, a)` is ⊥ **under a confidence policy κ** when:

```
COUNT(observation WHERE config_id = x AND axis = a AND confidence IN κ) = 0
```

This is a **query**, not a column.  Changing κ changes which cells are ⊥ —
this is intentional and is how the solver implements right-sizing under
varying evidence standards.

The Python helper `is_missing(obs, kappa)` in `substrate.py` implements this
check on the solver side.  The `Substrate.cell()` method is κ-free — it
returns all rows and lets the solver decide.

**Never impute ⊥ cells.**  Constraint C7 of the APT formalism prohibits
imputation: a missing axis stays ⊥ rather than receiving an estimated or
interpolated value.

---

## P1 HELM Lite Seed Coverage

The baseline seed (`seed_helm_lite.py`) populates only the `quality` axis from
the HELM Lite leaderboard (arxiv 2211.09110, snapshot 2023-11).

| axis | obs count after seed | status | reason for ⊥ |
|---|---|---|---|
| `quality` | 7 | **populated** | HELM Lite reports accuracy on mmlu for 6 models + 1 paper-reported duplicate for multi-obs demo |
| `latency_p95` | 0 | **⊥** | HELM Lite does not report latency |
| `throughput` | 0 | **⊥** | HELM Lite does not report throughput |
| `cost` | 0 | **⊥** | HELM Lite reports token counts, not dollar cost; proxying would be misleading |
| `energy` | 0 | **⊥** | HELM Lite does not report energy |
| `memory_hw` | 0 | **⊥** | HELM Lite does not report VRAM usage |
| `governance` | 0 | **⊥** | Not covered by HELM Lite |
| `reviewer_burden` | 0 | **⊥** | Not covered by HELM Lite |

Populating the remaining 7 axes requires additional seeders backed by
appropriate sources (measured benchmarks, vendor documentation, or expert
assessments) with correct confidence assignment per the policy above.

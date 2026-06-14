# APT Evidence Engine — Data Dictionary

This document describes every table and column in the APT Evidence Engine schema (`schema.sql`).
The database is SQLite with `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode = WAL`.

---

## Table: `source`

**Purpose:** Tracks the provenance of every piece of evidence — where it came from, when it was
captured, and under what license. Every `evidence_item` row must reference exactly one `source`.

| Column | Type | Nullable | Constraints | Description |
|---|---|---|---|---|
| `source_id` | TEXT | No | PRIMARY KEY | Stable slug identifier for this source, e.g. `src-helm`, `src-mlperf`. Chosen to be human-readable and URL-safe. |
| `source_type` | TEXT | No | CHECK IN (`benchmark`, `paper`, `vendor`, `deployment`) | Classification of the source. `benchmark` = public evaluation suite; `paper` = academic or technical report; `vendor` = provider documentation or marketing; `deployment` = real-world production case study or post-mortem. |
| `name` | TEXT | No | — | Full human-readable name of the source, e.g. `"HELM Lite"` or `"MLPerf Inference v4.0"`. |
| `url` | TEXT | Yes | — | Canonical URL for the source. May be a landing page, paper PDF, or GitHub repository. |
| `snapshot_date` | TEXT | Yes | — | ISO-8601 date (or year-month) when this source was accessed or published, e.g. `"2024-01"`. Used for temporal ordering and reproducibility. |
| `license` | TEXT | Yes | — | SPDX license identifier or short descriptor, e.g. `"MIT"`, `"Apache-2.0"`, `"CC-BY-4.0"`, `"proprietary"`. |

---

## Table: `evidence_item`

**Purpose:** A discrete, citable unit of evidence extracted from a source — a specific table row,
a claim in a paper, or a deployment measurement. This is the atomic unit that `benchmark_run` and
`composition` link to for traceability.

| Column | Type | Nullable | Constraints | Description |
|---|---|---|---|---|
| `evidence_id` | TEXT | No | PRIMARY KEY | Stable slug identifier for this evidence record, e.g. `ev-helm-1`. |
| `source_id` | TEXT | No | FK → `source.source_id` | The source this evidence was extracted from. |
| `evidence_type` | TEXT | No | CHECK IN (`metric`, `claim`, `deployment_record`) | `metric` = a measured numeric result; `claim` = a qualitative statement (e.g. "achieves SOTA"); `deployment_record` = a real-world production observation. |
| `description` | TEXT | Yes | — | Human-readable summary of what this evidence item captures, e.g. `"HELM Lite accuracy scores for LLMs"`. |
| `page_ref` | TEXT | Yes | — | Pointer to the specific location within the source, e.g. `"Table 1"`, `"p. 7"`, `"Appendix B"`, `"Leaderboard"`. |
| `retrieved_date` | TEXT | Yes | — | ISO-8601 date when this specific evidence item was extracted or recorded, e.g. `"2024-01-15"`. |

---

## Table: `component`

**Purpose:** Catalogs individual AI system building blocks — models, retrievers, rerankers, tools,
and agents. A component is the atomic deployable unit; it can appear in multiple compositions.

| Column | Type | Nullable | Constraints | Description |
|---|---|---|---|---|
| `component_id` | TEXT | No | PRIMARY KEY | Stable slug identifier, e.g. `cmp-gpt4o`, `cmp-bm25`. |
| `name` | TEXT | No | — | Human-readable name, e.g. `"GPT-4o"`, `"E5-Large-v2 Reranker"`. |
| `component_type` | TEXT | No | CHECK IN (`llm`, `retriever`, `reranker`, `rag_pipeline`, `tool`, `agent`) | Functional role: `llm` = large language model; `retriever` = document retrieval module; `reranker` = cross-encoder or scoring module; `rag_pipeline` = a pre-packaged RAG system treated as a single component; `tool` = callable function or API; `agent` = autonomous agent with its own reasoning loop. |
| `provider` | TEXT | Yes | — | Organization or individual providing the component, e.g. `"OpenAI"`, `"Meta"`, `"Microsoft"`, `"internal"`. |
| `version` | TEXT | Yes | — | Version string or date stamp, e.g. `"2024-08"`, `"large"`, `"v1.5"`. |
| `params_B` | REAL | Yes | — | Number of parameters in billions for model components. NULL for non-model components (e.g. retrievers, tools). |
| `license` | TEXT | Yes | — | SPDX license identifier or descriptor, e.g. `"Apache-2.0"`, `"Llama-3"`, `"proprietary"`. |
| `open_weights` | INTEGER | No | DEFAULT 0 | Boolean flag (0/1). 1 if model weights are publicly available; 0 for proprietary or access-controlled models. |

---

## Table: `composition`

**Purpose:** Represents an assembled AI system — a named combination of components arranged into
a pattern that solves a class of tasks. Compositions are the units that appear in benchmark runs
and right-sizing profiles.

| Column | Type | Nullable | Constraints | Description |
|---|---|---|---|---|
| `composition_id` | TEXT | No | PRIMARY KEY | Stable slug identifier, e.g. `comp-bare-gpt4o`, `comp-rag-claude`. |
| `name` | TEXT | No | — | Human-readable name for this assembled system, e.g. `"Claude RAG Pipeline"`. |
| `composition_pattern` | TEXT | No | CHECK IN (`bare_llm`, `rag`, `rag_reasoning`, `tool_agent`, `single_agent`, `multi_agent`, `web_nav`) | Architectural pattern: `bare_llm` = direct LLM API call; `rag` = retrieval-augmented generation; `rag_reasoning` = RAG with explicit chain-of-thought or reasoning step; `tool_agent` = LLM with callable tools; `single_agent` = single autonomous agent; `multi_agent` = multiple collaborating agents; `web_nav` = web navigation / browser automation agent. |
| `task_archetype` | TEXT | Yes | — | The class of tasks this composition is designed for, e.g. `"summarization"`, `"question_answering"`, `"code_generation"`. Should align with `benchmark_run.task` values. |
| `evidence_id` | TEXT | Yes | FK → `evidence_item.evidence_id` | Optional link to the primary evidence item that motivated or validates this composition. |
| `notes` | TEXT | Yes | — | Free-text description of the composition, configuration choices, or operational context. |

---

## Table: `composition_component`

**Purpose:** Join table resolving the many-to-many relationship between compositions and components.
Each row specifies one component's role within one composition, and optionally its execution order
in a pipeline.

| Column | Type | Nullable | Constraints | Description |
|---|---|---|---|---|
| `composition_id` | TEXT | No | PK part 1; FK → `composition.composition_id` | The composition this component belongs to. |
| `component_id` | TEXT | No | PK part 2; FK → `component.component_id` | The component being included. |
| `role` | TEXT | No | PK part 3 | Functional label for this component within the composition, e.g. `"retriever"`, `"reranker"`, `"generator"`, `"planner"`. The composite primary key allows the same component to play multiple roles in the same composition. |
| `execution_order` | INTEGER | Yes | — | Numeric ordering of pipeline stages (1-indexed). NULL for components without a strict ordering (e.g. parallel agents). |

---

## Table: `benchmark_run`

**Purpose:** Stores individual measurement records from benchmark evaluations. Each row captures
one observed (quality, latency, cost, energy, memory) tuple for one composition or component on
one task, sourced from one evidence item. Either `composition_id` or `component_id` must be set
(or both), reflecting whether the measurement applies to a full pipeline or a single component.

| Column | Type | Nullable | Constraints | Description |
|---|---|---|---|---|
| `run_id` | TEXT | No | PRIMARY KEY | Stable slug identifier, e.g. `run-helm-1`. |
| `composition_id` | TEXT | Yes | FK → `composition.composition_id` | The assembled system that was measured, if the benchmark evaluated a full composition. NULL if measuring a standalone component. |
| `component_id` | TEXT | Yes | FK → `component.component_id` | The individual component that was measured, if applicable. May be set alongside `composition_id` to indicate which component within a pipeline produced the measurement. |
| `evidence_id` | TEXT | No | FK → `evidence_item.evidence_id` | The evidence item that is the source of this measurement. Must always be set for traceability. |
| `task` | TEXT | No | — | The specific task or benchmark being measured, e.g. `"summarization"`, `"text_generation"`, `"code_generation"`. Should be consistent with `composition.task_archetype`. |
| `hardware_tier` | TEXT | Yes | CHECK IN (`A100`, `H100`, `T4`, `V100`, `CPU`, `TPUv4`, `unknown`) | The hardware on which the measurement was taken. Used to contextualize latency and energy figures. `unknown` when not reported. |
| `quality` | REAL | Yes | — | Normalized quality score in [0, 1]. Normalization policy: use the metric's natural range divided to [0,1]; e.g. accuracy already in [0,1], ROUGE-L divided by 1.0. NULL if quality was not measured. |
| `latency_p95_ms` | REAL | Yes | — | 95th-percentile end-to-end latency in milliseconds. NULL if not reported. |
| `cost_per_1k_tokens` | REAL | Yes | — | Monetary cost in USD per 1,000 tokens (input+output combined, or as reported). NULL for open-weight models running on owned hardware. |
| `energy_J` | REAL | Yes | — | Energy consumed per inference in joules. NULL if not reported. |
| `memory_GB` | REAL | Yes | — | Peak GPU/CPU memory usage in gigabytes during inference. NULL if not reported. |
| `quality_metric` | TEXT | Yes | — | Canonical name for the quality metric used, e.g. `"rouge_l"`, `"f1"`, `"accuracy"`. Enables cross-run comparison. |
| `source_metric` | TEXT | Yes | — | The original metric name as reported in the source, e.g. `"ROUGE-L"`, `"Exact Match F1"`, `"Pass@1"`, `"tokens/sec"`. Preserves traceability to the raw evidence. |
| `notes` | TEXT | Yes | — | Free-text context, caveats, or methodology notes for this measurement. |

---

## Table: `right_sizing_profile`

**Purpose:** Encodes deployment constraints and requirements for a given (pattern, task, context)
combination. Profiles define the minimum quality, maximum latency, and maximum cost thresholds that
a composition must meet to be considered appropriate for deployment in a specific regulatory,
industry, or operational context. This is the core artifact APT uses for right-sizing decisions.

| Column | Type | Nullable | Constraints | Description |
|---|---|---|---|---|
| `profile_id` | TEXT | No | PRIMARY KEY | Stable slug identifier, e.g. `prof-rag-qa-hipaa`. |
| `composition_pattern` | TEXT | No | — | The architectural pattern this profile applies to. Should match values in `VOCAB["composition_pattern"]`. No FK constraint intentionally, to allow profiles for hypothetical patterns. |
| `task_archetype` | TEXT | Yes | — | Optional further narrowing: which task class within the pattern, e.g. `"question_answering"`. NULL means the profile applies to all tasks for this pattern. |
| `quality_min` | REAL | Yes | — | Minimum acceptable quality score (normalized [0,1]). A composition's `benchmark_run.quality` must be >= this value for this profile. NULL means no quality floor. |
| `latency_max_ms` | REAL | Yes | — | Maximum acceptable p95 latency in milliseconds. NULL means no latency ceiling. |
| `cost_max_per_1k` | REAL | Yes | — | Maximum acceptable cost in USD per 1,000 tokens. NULL means no cost ceiling (e.g. for open-weight self-hosted deployments). |
| `regulatory_regime` | TEXT | Yes | — | Applicable regulatory framework, e.g. `"HIPAA"`, `"GDPR"`, `"EU-AI-Act-High-Risk"`, `"SOC2"`, `"none"`. NULL if no specific regime applies. |
| `human_review_required` | INTEGER | No | DEFAULT 0 | Boolean (0/1). 1 if deployments under this profile must include a human-in-the-loop review step before acting on outputs. |
| `pii_involved` | INTEGER | No | DEFAULT 0 | Boolean (0/1). 1 if inputs or outputs under this profile may contain personally identifiable information. Affects data handling and logging requirements. |
| `industry` | TEXT | Yes | — | Industry sector this profile targets, e.g. `"healthcare"`, `"finance"`, `"legal"`, `"general"`. NULL for cross-industry profiles. |
| `value_source_type` | TEXT | Yes | CHECK IN (`benchmark`, `vendor_claim`, `derived`, `default`) | How the threshold values in this profile were determined: `benchmark` = grounded in measured benchmark data; `vendor_claim` = taken from provider SLA or documentation; `derived` = computed from benchmark + business logic; `default` = conservative placeholder pending evidence. |
| `confidence` | TEXT | Yes | CHECK IN (`high`, `medium`, `low`) | Confidence in the threshold values: `high` = multiple corroborating sources; `medium` = single reliable source; `low` = derived or defaulted, should be validated. |
| `notes` | TEXT | Yes | — | Free-text rationale for the profile's thresholds, data sources, or intended use. |

---

## Cross-table relationships

```
source (1) ──< evidence_item (N)
evidence_item (1) ──< benchmark_run (N)
evidence_item (1) ──< composition (N)   [optional]
composition (1) ──< benchmark_run (N)   [optional]
component (1) ──< benchmark_run (N)     [optional]
composition (1) ──< composition_component (N)
component (1) ──< composition_component (N)
```

`right_sizing_profile` is intentionally standalone — it references pattern/archetype vocabulary
rather than FK-linking to `composition`, so profiles can be defined independently of observed
compositions and reused across multiple compositions matching the same pattern.

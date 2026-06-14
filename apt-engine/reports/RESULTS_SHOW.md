# APT Evidence Engine — Weekly Gate Results

**Date:** 2026-06-14  
**Branch:** `feat/apt-evidence-engine` → `https://github.com/triquang26/prudent-ai/tree/feat/apt-evidence-engine`  
**Reproduce:** `pip install -r requirements.txt && make populate && make demo`

---

## Gate Summary (All PASS ✅)

| Gate | Criteria | Result |
|------|----------|--------|
| **W1** | 7 tables + data_dictionary + ≥20 seed rows | ✅ **818 rows** across 7 tables |
| **W2** | HELM Lite load + Q1–Q4 queries + interface-invariance | ✅ **9/9 tests pass** |
| **W4** | ≥200 rows ≥4/5 cols + ≥50 MLPerf + ≥50 HELM | ✅ **502 / 478 / 54 / 120** |
| **W6** | ≥400 runs + retriever + RAG + tool + ≥30 compositions | ✅ **502 runs / 175 comps** |
| **W7** | agent rows + cost-quality frontier + web_nav | ✅ **10 agents / 38 web_nav** |
| **W8** | ≥500 runs + ≥50 comp + ≥5 ZenML profiles + report | ✅ **502 / 175 / 5** |
| **W9** | ≥4 profiles + right_size() + tests | ✅ **6 patterns / 6 tests** |
| **W10** | 4-scenario demo offline < 5 min | ✅ |
| **Tests** | pytest | ✅ **21/21 passed** |

---

## W1 — Schema + Seed Data

```
7 tables present: 7/7
  source                             11 rows
  evidence_item                      31 rows
  component                          88 rows
  composition                       175 rows
  composition_component               0 rows
  benchmark_run                     502 rows
  right_sizing_profile               11 rows

Total rows (all tables): 818

Vocab validation:
  source_type:         ✓  [benchmark, deployment, paper, vendor]
  evidence_type:       ✓  [claim, deployment_record, metric]
  component_type:      ✓  [agent, llm, rag_pipeline, reranker, retriever, tool]
  composition_pattern: ✓  [bare_llm, multi_agent, rag, rag_reasoning, single_agent, tool_agent, web_nav]
  hardware_tier:       ✓  [A100, CPU, H100, T4, TPUv4, V100, unknown]

GATE W1: PASS ✅
```

---

## W2 — HELM Lite + Queries + Interface

```
HELM Lite loaded: 120 benchmark_run rows

Q1 — Missingness:   0 blocking (all compositions fully covered)
Q2 — Feasible:      68 compositions meet (quality≥0.7, lat≤800ms, cost≤0.02)
Q3 — Borderline:   136 compositions near thresholds
Q4 — Binding:      175 compositions have at least one binding constraint

Interface invariance: DB not mutated after read-only cell() calls ✅

GATE W2: PASS ✅  (9/9 tests)
```

---

## W4 — Dense Benchmark Coverage (502 rows across 11 sources)

| Source | Rows |
|--------|------|
| HELM Lite — Holistic Evaluation of Language Models | 120 |
| BEIR: Heterogeneous Retrieval Benchmark | 90 |
| Berkeley Function Calling Leaderboard (BFCL) v3 | 60 |
| MedHELM — Medical Holistic Evaluation of Language Models | 56 |
| MLPerf Inference v4.0 — hardware performance benchmark | 54 |
| RouterBench — LLM routing strategy evaluation | 41 |
| WebArena: Web Environment for Autonomous Agents | 38 |
| KILT: Knowledge-Intensive Language Tasks | 18 |
| HAL — Holistic Agent Leaderboard | 12 |
| MLEnergy Survey — energy efficiency of LLM inference | 10 |
| ZenML Enterprise Case Studies | 3 |
| **TOTAL** | **502** |

```
Rows with ≥4/5 core columns: 478
MLPerf rows: 54  ≥50 ✅
HELM rows:  120  ≥50 ✅

GATE W4: PASS ✅
```

---

## W6 — RAG / Retriever / Tool-Use + Compositions

```
Component types:
  llm         79    retriever  4
  tool         4    reranker   1

Composition patterns (175 total):
  bare_llm    91    web_nav   38    rag       24
  tool_agent  12    single    6     multi      4

GATE W6: PASS ✅  (502 runs / 175 compositions)
```

---

## W7 — Agent Compositions + Cost-Quality Frontier

```
Agent compositions (10 single+multi+tool):
  4x multi_agent  (HAL — GPT-4o, Claude-3.5, Llama-3-70B, Gemini-1.5)
  6x single_agent (HAL — 5 models + Llama-3-8B budget)

Web navigation (38 rows):
  8 overall WebArena runs + 6 websites × 5 agents

Cost-Quality Frontier (summarization, lowest cost):
  Model               Quality  Latency  Cost/1k
  MLPerf/BERT-Large   0.875    45ms     $0.0001
  MLEnergy/Phi-3-mini 0.680    145ms    $0.0002
  MLPerf/Llama-3-8B   0.720    262ms    $0.0002

GATE W7: PASS ✅
```

---

## W8 — Deployment Context + Missingness Report

```
ZenML deployment profiles (5):
  rsp-accenture   consulting       GDPR   human_review=True  pii=True
  rsp-doordash    food_delivery    —      human_review=False pii=True
  rsp-uber        rideshare        —      human_review=False pii=True
  rsp-linkedin    prof_network     GDPR   human_review=True  pii=True
  rsp-telekom     telecom          GDPR   human_review=True  pii=False

Core Column Missingness:
  quality:             0.0% missing ✅
  latency_p95_ms:      0.0% missing ✅
  cost_per_1k_tokens:  0.0% missing ✅

GATE W8: PASS ✅  (502 runs / 175 comps / 5 ZenML profiles)
```

---

## W9 — Right-Sizing Decision Rule

```
Canonical HIPAA scenario:
  Query: task=summarization, ROUGE-L≥0.30, lat≤2000ms, cost≤$0.05/1k
         HIPAA=True, human_review=True, pii=True

  Branch: tiebreak_10pct
  #1 MedHELM/BioMedLM  quality=0.612  latency=420ms  cost=$0.0003  ← CHEAPEST
  #2 MedHELM/BioMedLM  quality=0.589  latency=756ms  cost=$0.0003
  #3 MedHELM/Meditron  quality=0.651  latency=1404ms cost=$0.0008

Right-sizing profiles (6 patterns):
  rag           enterprise_qa       q≥0.85 lat≤2000ms GDPR
  bare_llm      customer_service    q≥0.80 lat≤800ms
  rag_reasoning trip_planning       q≥0.82 lat≤1500ms
  tool_agent    job_matching        q≥0.78 lat≤3000ms GDPR
  web_nav       web_automation      q≥0.60 lat≤10000ms
  multi_agent   enterprise_workflow q≥0.85 lat≤5000ms GDPR

GATE W9: PASS ✅  (6 patterns / 6 tests pass)
```

---

## W10 — 4-Scenario Demo

```
=== SCENARIO 1: Clinical Note Summarization (HIPAA) ===
  → tiebreak_10pct: BioMedLM ($0.0003/1k, 420ms, ROUGE-L=0.612)

=== SCENARIO 2: Web Navigation Agent ===
  → tiebreak_10pct: Claude-3.5-Sonnet/text (39.5% success, 7800ms)

=== SCENARIO 3: Open-Domain QA (RAG) ===
  → tiebreak_10pct: BEIR/Contriever+Llama3-70B (q=0.758, $0.001/1k)

=== SCENARIO 4: Failure Case — Impossible Constraints ===
  Query: quality≥0.99, lat≤10ms, cost≤$0.00001/1k
  → infeasible_binding: all candidates violate quality+latency+cost

Demo complete ✅  (<5 min, fully offline, no API key)
```

---

## Test Suite — 21/21 PASSED

```
tests/test_decision_rule.py       6 passed
tests/test_demo_smoke.py          1 passed
tests/test_interface_invariance.py 5 passed
tests/test_queries.py             4 passed
tests/test_schema.py              5 passed
─────────────────────────────────────────
TOTAL                            21 passed in 2.11s
```

---

## Architecture

```
apt-engine/
├── schema/          schema.sql (7 tables) + data_dictionary.md
├── src/apt_engine/
│   ├── db.py        connect(), init_db(), validate_vocab(), table_counts()
│   ├── belief.py    Belief(lo,hi,is_bot), kappa_filter(), phi_interval()
│   ├── interface.py candidates() / cell() / required_fields()  ← C7 read-only
│   ├── queries.py   Q1_missing / Q2_feasible / Q3_borderline / Q4_binding
│   ├── right_sizing.py  right_size() — 5-branch §12 Tier A decision rule
│   ├── verdict.py   decidable / underdetermined / infeasible
│   ├── profiles.py  right_sizing_profile management (6 patterns)
│   ├── missingness.py   auto-generate coverage report
│   └── loaders/     11 source loaders:
│       ├── helm_lite.py      HELM Lite (120 rows)
│       ├── mlperf.py         MLPerf v4.0 (54 rows)
│       ├── routerbench.py    RouterBench (41 rows)
│       ├── bfcl.py           BFCL v3 (60 rows)
│       ├── mlenergy.py       MLEnergy (10 rows)
│       ├── beir_kilt.py      BEIR+KILT (108 rows: 18×5 + 6×3)
│       ├── medhelm.py        MedHELM (56 rows: 7 tasks × 8 models)
│       ├── hal.py            HAL (12 rows)
│       ├── webarena.py       WebArena (38 rows: overall + 6 sites × 5 agents)
│       └── zenml_cases.py    ZenML (5 deployment profiles)
├── scripts/         show_w1..w9.py + demo.py
└── tests/           21 pytest tests (5 files)
```

---

## Reproduce from Scratch (no internet after install)

```bash
git clone https://github.com/triquang26/prudent-ai
cd prudent-ai
git checkout feat/apt-evidence-engine
cd apt-engine
pip install -r requirements.txt
make populate    # seeds DB (~2s, 502 rows)
make show-w1     # W1 gate
make show-w2     # W2 gate
make show-w4     # W4 gate
make show-w6     # W6 gate
make show-w7     # W7 gate
make show-w8     # W8 gate + missingness report
make show-w9     # W9 gate + HIPAA scenario
make demo        # 4-scenario demo
make test        # 21/21 tests
```

# APT Evidence Engine

Schema-grounded AI deployment right-sizing engine. Measures evidence-decidability over documented production LLM deployments.

## Quick start (no API key, fully offline)

```bash
pip install -r requirements.txt
make populate    # seed DB from all loaders (~574 benchmark_run rows)
make demo        # 4-scenario demo in <5 min
```

## Weekly show targets

```bash
make show-w1    # W1 gate: 7-table schema + FK + vocab + seed counts
make show-w2    # W2 gate: HELM Lite load + Q1–Q4 + interface-invariance
make show-w4    # W4 gate: ≥200 rows ≥4/5 core cols + ≥50 MLPerf + ≥50 HELM
make show-w6    # W6 gate: ≥400 runs + retriever+RAG+tool + ≥30 compositions
make show-w7    # W7 gate: agent compositions + cost-quality frontier + web-nav
make show-w8    # W8 gate: 5 ZenML deployment profiles + missingness report
make show-w9    # W9 gate: right_size() canonical HIPAA scenario + profiles + tests
make demo       # W10 gate: 4-scenario demo offline
make test       # all 21 tests
```

## Gate summary (all PASS)

| Gate | Criteria | Result |
|------|----------|--------|
| W1 | 7 tables + data_dictionary + ≥20 seed rows | ✅ 820 rows |
| W2 | HELM Lite + Q1–Q4 + interface-invariance | ✅ 9 tests |
| W4 | ≥200 rows ≥4/5 cols + ≥50 MLPerf + ≥50 HELM | ✅ 574/568/54/132 |
| W6 | ≥400 runs + retriever+RAG+tool + ≥30 comp | ✅ 574/105 |
| W7 | agent rows + frontier + web_nav | ✅ 18 agents / 8 web_nav |
| W8 | ≥500 runs + ≥50 comp + ≥5 ZenML + report | ✅ 574/105/5 |
| W9 | ≥4 profiles + right_size() + tests | ✅ 6 patterns / 6 tests |
| W10 | demo 4 scenarios offline <5 min | ✅ |

## Structure

```
schema/          schema.sql + data_dictionary.md
src/apt_engine/  core library
  loaders/       11 source loaders (HELM, MLPerf, RouterBench, BFCL, MLEnergy,
                  BEIR/KILT, MedHELM, HAL, WebArena, ZenML cases)
  interface.py   candidates() / cell() / required_fields() — C7 read-only
  belief.py      kappa-filter, phi-interval, derived ⊥
  queries.py     Q1–Q4 (missingness / feasible / borderline / binding)
  right_sizing.py right_size() — 5-branch §12 Tier A decision rule
  verdict.py     decidable / underdetermined / infeasible
  profiles.py    right_sizing_profile management
  missingness.py auto-generate coverage report
scripts/         show_w1..w9.py + demo.py
tests/           21 pytest tests
reports/         auto-generated (gitignored)
```

## Reproduce from scratch

```bash
git clone <repo>
cd apt-engine
pip install -r requirements.txt
make populate
make test        # 21 passed
make demo
```

No internet required after install. No API keys needed.

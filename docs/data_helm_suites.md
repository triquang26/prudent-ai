# Structured data — full HELM-suite batch ingest (→ 20 sources, §13 target met)

> Node: `w7kfzr-ingest-all-helm-suites` (parent `zdnpkh`).
> Code: `src/prudent_ai/substrate/helm_suite/` (auto-version) + `SOURCE_REGISTRY`
> (auto-registers every `helm_suite.SUITES` entry) + `scripts/seed_helm_suites.py`.
> Real GCS data from `crfm-helm-public`.

## What was done

Processed **all auto-ingestible structured data** (skipping anything that needs humans).
Added `version="latest"` auto-resolution to the HELM-suite ingester, then batch-seeded
**every viable text/LLM HELM suite** on the `crfm-helm-public` bucket, sequentially (SQLite
single writer), via the generalized `helm_suite` ingester.

**14 suites ingested** (real data, no stubs): classic, mmlu, reasoning, finance,
long-context, thaiexam, cleva, ewok, mmlu-winogrande-afr, capabilities, safety, air-bench,
arabic-enterprise, torr — joining medhelm + the 5 original sources.

**Excluded (correctly):** multimodal suites (vhelm, heim, audio, image2struct — different
schema), non-LLM (robo-reward-bench), `instruct`/`seahelm` (no [0,1] quality + no latency),
`gzip`/`efficient_helm` (no runs on GCS). **Human-gated** paths skipped per instruction:
HAL (401-gated API), BEIR (needs paper-table extraction), and the paper-row extraction
κ-gate (needs 2 human annotators).

## Result — the substrate now

| metric | before (node zdnpkh) | **after** |
|---|---|---|
| sources | 6 | **20** (master-plan §13 upper target) |
| observations | 4 557 | **5 164** |
| configs | ~520 | **655** |
| archetypes (τ) | 5 | **19** |

Per-suite quality/latency obs are in `scripts/seed_helm_suites.py` output; +181 quality,
+426 latency over the batch. Quality range held at **[0.00, 1.00]** across all 20 sources
(the [0,1] guard skipped every off-scale jury rating; 0 corruption). `torr` (4 900 runs)
contributed latency only (no [0,1] accuracy-family metric).

## Two corpus-level findings (the point of breadth)

**1. The governance blind-spot is now robust over 20 sources.** Across the entire
20-source corpus — quality (HELM Lite/classic/mmlu/capabilities/…), agent+cost (BFCL),
serving (MLPerf), energy (ML.ENERGY), routing (RouterBench), medical (MedHELM), **safety
(safety, air-bench)**, multilingual (cleva, thaiexam, arabic-enterprise,
mmlu-winogrande-afr) — the three hard-to-observe axes report **ZERO** observations:

| axis | configs with evidence (of 655) | miss-rate |
|---|---|---|
| memory_hw | 0 | **1.000** |
| governance | 0 | **1.000** |
| reviewer_burden | 0 | **1.000** |

Notably even the **safety / AIR-Bench** leaderboards report 0 governance: they measure
*model safety behaviour*, not *deployment governance / reviewer burden / hardware
footprint*. So C1's structural blind-spot is **not** an artifact of a narrow source set —
it survives a 20-source, multi-domain corpus that explicitly includes safety and clinical
benchmarks. This materially strengthens C1.

**2. Overall evidence is sparse even on "measurable" axes.** 655 configs × 8 axes = 5 240
cells; **overall cell miss-rate 0.728**. Even measurable axes are fragmented across
sources (throughput 0.936, energy 0.948 miss — they live only in MLPerf/ML.ENERGY), so no
single config spans the axes a multi-constraint query binds. This is the structural,
non-random missingness the C1 thesis predicts, now demonstrated at 20-source scale.

## How adding the rest of the corpus stays one-line

`version="latest"` + the registry auto-registering `helm_suite.SUITES` means a new HELM
suite is a single `_helm_spec("<name>", "<tau>")` line. The batch runner
(`scripts/seed_helm_suites.py`, `--only`/`--skip`) seeds sequentially (never parallel —
SQLite single writer). Re-seeding is idempotent.

## Tests

`tests/test_helm_suite.py` (4) + `tests/test_registry_extraction.py` (registry now ≥18
sources). 73/73 pass; ruff clean. The C7 interface and schema are untouched (the ingest is
pure additive evidence).

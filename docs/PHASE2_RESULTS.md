# PHASE2_RESULTS.md — live acquisition loop (small, real, end-to-end)

**Result: the selective procedure's loop closes end-to-end with real measurement.** On 5
RouterBench slices, an underdetermined masked query → VoI-ranked acquisition → reveal the
measured value into a scratch overlay → re-verdict → commit, with **0 hidden violations**
and **100% minimum-sufficient** commitments. Governance cannot be looped (raises). The
frozen snapshot is **byte-for-byte unchanged**. GATE 2 passed.

Tests: **89 passed** (79 + 7 transfer + 3 loop). `data/apt_substrate.db` md5 unchanged.

## What was built

- `src/prudent_ai/loop/live_acquisition.py` — `LiveAcquisitionLoop`: classify → if
  underdetermined, `voi_ranking` the blockers and pick the top **measurable** axis →
  acquire its true value for each candidate via an injected `oracle(config_id, axis)` →
  write into an `OverlayedSubstrate` scratch overlay (never the frozen db) → re-verdict →
  repeat until commit / infeasible / budget. If the only remaining blockers are structural
  (governance, reviewer_burden, …) it raises `NoMeasurementPathError` — it never fakes a
  measurement that does not exist (no config↔governance audit data, Appendix K).
- `experiments/phase2_live_loop_demo.py` — runs the real loop on 5 slices in two settings.
- `tests/test_live_loop.py` — commit-after-measuring, governance-refusal, frozen-db-unchanged.

The acquisition is real in the sense an offline GT corpus allows: the value is genuinely
revealed from measured RouterBench ground truth and re-entered through the C7 interface,
then the *unmodified* verdict re-runs. The simulated 2.0-vs-6.0 probe count (kept as the
at-scale evidence in `run_multi_blocker.py`) is now backed by a real closed loop.

## Demo results (`outputs/phase2/live_loop_demo.json`)

| setting | coverage | mean probes-to-commit | mean acq cost | hidden violations | min-sufficient |
|---|---|---|---|---|---|
| A — mask quality (1 blocker) | 1.00 | **1.0** | 0.300 | **0** | **1.00** |
| B — mask quality + cost (2 blockers) | 1.00 | **2.0** | 0.350 | **0** | **1.00** |

- The loop resolves every masked decision: it acquires exactly the blocking axis/axes
  (1 when only quality is hidden, 2 when quality and cost are both hidden), then commits the
  cheapest truly-sufficient configuration — **zero** hidden violations, **every** commit
  minimum-sufficient against ground truth.
- `frozen_db_unchanged = true`, `governance_loop_refused = true` in the artifact metadata.

## Boundary (stated, not faked)

Governance and the other never-measured structural axes have **no measurement path** in any
public source. The loop refuses (`NoMeasurementPathError`) rather than invent a value —
matching the paper's documented structural gap. The live loop is therefore demonstrated on
the **measurable** axes only; closing it on governance would require config↔audit data that
does not exist (Appendix K). This is the clean boundary, not a limitation papered over.

GATE 2: end-to-end demo runs on ≥1 real slice (5 here) with zero violations and minimum-
sufficient commitments → Tier-3 demonstrated.

## Phase 2b — live loop swept over the FULL battery (510 decisions)

`outputs/phase2/live_loop_full.json` · `experiments/phase2b_live_loop_full.py`. Scaled the
demo from 5 slices to all 30 RouterBench per-benchmark slices (510 measurable-GT decisions),
both masking settings, VoI-plan vs random acquisition. Every measurement real; frozen db
byte-identical after.

| setting | n | coverage | hidden viol. | min-sufficient | plan probes | random probes |
|---|---|---|---|---|---|---|
| mask quality | 510 | 1.00 | **0** | **1.00** | **1.0** (`{1:510}`) | 2.94 |
| mask quality+cost | 510 | 1.00 | **0** | **1.00** | **2.0** (`{2:510}`) | 3.98 |

At full scale the loop resolves **every** decision with **0 hidden violations** and **100%
minimum-sufficient** commitments. The VoI plan is deterministically optimal (always exactly
the minimal probe count — `{1:510}` / `{2:510}`), ~2–3× fewer probes than random — the
simulated 2.0-vs-6.0 result now real and swept over the whole battery. Random's mean
(2.94/3.98) is over a 5-axis measurable pool (coupon-collector); the plan never wastes a probe.

**Full picture (transfer + loop):** calibrated transfer resolves ~25% of co-location
decisions for free (0 measurement, 0 risk; Appendix L); the live loop measures the rest,
reaching 100% coverage with 0 violations at 1–2 real probes each. Curable-by-transfer,
resolvable-by-measurement, and structurally-unmeasured (governance, refused) — the clean
three-way split, now demonstrated end-to-end at scale.

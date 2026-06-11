# Annotator-free paper-row extraction — Path 1 (L-quarantine) + Path 2 (consensus → M)

> Code: `src/prudent_ai/extraction/` — `axcell.py`, `mole.py`, `agreement.py`,
> registered in `registry.py`. Tests: `tests/test_extraction_paths.py` (6).
> κ-ablation harness already exists: `analysis.decidability_map.sensitivity_kappa`.

## Why this exists

The master plan's §13 long tail is **paper-row extraction**: pulling
`(config, axis, value)` from PDFs. The canonical gate is a **human κ-check** (two
annotators, constraint C5) — because auto-extraction is unreliable (AxCell F1 ~25.8,
MOLE ~67%, paper compute-omission 60–89%). These two paths let us **enrich without
humans** while keeping every hard claim clean.

**Extraction ≠ imputation.** An extracted value is a *real number reported in a real
paper* — legitimate evidence, only noisy. Imputation invents a value for a cell
nobody measured (forbidden, C1). So the issue is *reliability*, handled by the
confidence tier — not fabrication.

## Path 1 — ingest at confidence **L** (quarantine)

`AxCellExtractor` (table rows) and `MOLEExtractor` (schema records) consume the
**cached output** of those tools — exactly as the substrate seeders consume cached
GCS dumps; the heavy model run is an offline preprocessing step. Every value enters
at **`confidence='L'`**, `annotator='axcell'|'mole'`.

The default policy **κ={H,M}** (`beliefs.DEFAULT_KAPPA`) **excludes L**. Therefore:

- Auto-extracted rows can **never touch a hard claim** (57.1%/0%, 527/527 run on H).
- They surface **only** under an explicit κ={H,M,L} sweep
  (`sensitivity_kappa`) — i.e. as a **robustness ablation**, not as headline data.

This is proven by `test_L_rows_do_not_change_a_hard_claim`: an injected L row that
*would* flip a decision if trusted leaves the κ={H,M} `right_size` decision
byte-identical, while κ={H,M,L} does see it.

**Never-invent (C1):** a row is dropped — not guessed — when it lacks a value, its
metric is unmappable, its quality is off-[0,1], or its `config_id` is not already a
modelled config (`loader` skips the last and counts it).

## Path 2 — promote to **M** by cross-extractor consensus

`agreement.cross_agreement(axcell_obs, mole_obs, rel_tol=0.05)` is a **machine
inter-annotator proxy**: a cell extracted by **both** extractors whose values agree
within `rel_tol` is promoted to **confidence M** (`annotator='consensus'`,
`evidence_id='consensus'`, value = mean). Disagreements and single-extractor cells
are **not** promoted — their L rows stand.

**Promoted = M, never H.** Two extractors can share a failure mode (both misread the
same malformed table) where two independent humans would not. So consensus evidence
participates in κ={H,M} but is still excluded from the strongest H-only analyses.
Always surface the `AgreementReport` (`n_shared_cells`, `n_agreed`, `promotion_rate`,
`rel_tol`) so the caveat is auditable.

## What these paths can and cannot do

| | reachable by extraction? |
|---|---|
| quality, latency_p95 (paper-rich) | **yes** — this is what extractors enrich |
| cost, throughput, energy (measurable, fragmented) | **partially** — the marginal decidability win lives here |
| **governance, reviewer_burden, memory_hw** | **no — structurally absent from every paper** |

The 91.1% headline is driven by the **72.4% of real queries blocked by an axis the
whole field never measures**. No extractor can pull a number that was never written
down — so enrichment **strengthens the robustness story** (the blind-spot survives
even the full auto-extracted corpus) rather than lowering the headline. Gaps on the
blind-spot axes still require a real-world measurement (audit / evaluation) — exactly
the "measure this next" plan the procedure already emits.

## How to run

```python
from prudent_ai.extraction import (
    AxCellExtractor, MOLEExtractor, cross_agreement, load,
)
ax, mo = AxCellExtractor(), MOLEExtractor()
a = ax.extract("paper-2403.12031", axcell_cached_rows)   # → confidence L
b = mo.extract("paper-2403.12031", mole_cached_records)  # → confidence L
load(sub, ax.source_record("paper-2403.12031"), a)       # Path 1
load(sub, mo.source_record("paper-2403.12031"), b)
promoted, report = cross_agreement(a, b, rel_tol=0.05)   # Path 2
load(sub, consensus_source, promoted)                    # consensus → M
print(report)   # promotion_rate + caveat, for the write-up
```

Then the κ-ablation (already in the repo):

```python
from prudent_ai.analysis.decidability_map import sensitivity_kappa
sensitivity_kappa(sub)["underdetermined_shift"]   # {'H+M': .., 'H': .., 'H+M+L': ..}
```

## Status

Machinery + tests landed (79/79 pass, ruff clean). **No paper rows are ingested into
the frozen substrate** — doing so honestly requires matching real extracted values to
existing `config_id`s, which is the human-gated work C5 governs; the pipeline is ready
for that data the moment it exists, with no schema or downstream change (C7 intact).

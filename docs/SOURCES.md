# Scaling the substrate — the plug-in guide

> The substrate is built so that **adding evidence later is a localized edit**, not a
> redesign. There are two seams: **structured sources** (leaderboards/benchmark
> dumps) and **paper-row extraction** (PDF → values, deferred content). Both end at
> the same five tables. This file is the map of where to plug in.

## 1. The schema (5 tables, FK-enforced)

DDL: `src/prudent_ai/substrate/schema.sql`; ORM: `src/prudent_ai/substrate/orm.py`.
FK enforcement is per-connection (`PRAGMA foreign_keys=ON`), set by `Substrate`'s
SQLAlchemy `connect` event listener — so the app enforces FKs even though a raw
`sqlite3` connection defaults to off.

| table | PK | FK | role |
|---|---|---|---|
| `component` | `id` | — | a deployable unit (model, adapter, quant). `kind`, `name`. |
| `config` | `id` | — | a deployment configuration; `tau` = deployment-context tag. |
| `config_component` | (`config_id`,`component_id`) | →`config.id`, →`component.id` | many-to-many: which components make a config (lineage). |
| `source` | `evidence_id` | — | provenance: `source_type`, `citation`, `snapshot_version`. |
| `observation` | `obs_id` | →`config.id`, →`source.evidence_id` | one measured value on one axis: `axis`, `value_num`/`value_cat`, `confidence∈{H,M,L}` (CHECK), + context (`hardware_tier,dataset,split,decoding_cfg,obs_date`). |

Key invariants: **`⊥` is never stored** — a missing (config, axis) cell is simply the
absence of `observation` rows, queried under a confidence filter κ. **FK = provenance
guarantee**: an observation cannot exist without a `source`. The substrate↔solver
interface (`candidates`/`cell`/`required_fields`) is **immutable** (C7) — adding data
never touches it.

## 2. Add a STRUCTURED source — 1 package + 1 line

1. Create `src/prudent_ai/substrate/<name>/` with the four-file OOP pattern (copy any
   existing source, e.g. `routerbench/`):
   - `models.py` — frozen dataclasses (rows + a `SeedReport`).
   - `client.py` — transport only (urllib / file load); **freeze a disk snapshot** for
     reproducibility (C3), like `routerbench/client.py` or the ZenML snapshot.
   - `parser.py` — pure transform (raw → domain objects); **never invent values** (C1).
   - `seeder.py` — a `<Name>Seeder` + module-level `seed(db_path, verbose) -> SeedReport`
     that inserts via `sqlite_insert(...).on_conflict_do_nothing()` (idempotent; no raw SQL).
2. Append one `SourceSpec(...)` to `SOURCE_REGISTRY` in
   `src/prudent_ai/substrate/registry.py`.

That's it. `scripts/seed_all.py` ingests it automatically; the coverage report and the
decidability/validation pipeline pick it up with no further edits. Re-seeding is safe
(idempotent). Run: `PYTHONNOUSERSITE=1 uv run python scripts/seed_all.py`
(or `--only <name>`).

**Candidate next sources** (master plan §13, deferred content): HAL (R2 agent+cost,
encrypted traces), MedHELM (governance prior, currently HTTP-401 gated), BEIR/KILT
(retrieval), AI-Agents-That-Matter.

## 3. Add a PAPER-ROW extractor — subclass + register

For the long tail that isn't a clean leaderboard (PDF tables). Scaffolding lives in
`src/prudent_ai/extraction/` (content deferred; the seam is built + tested):

1. Subclass `Extractor` in `extraction/<name>.py` — implement `source_record()` and
   `extract(document_id, raw) -> list[ExtractedObservation]`. Set `confidence` per C4
   (auto → L/M; **H only after a second annotator confirms**, C5); carry the context
   (C6); drop unsourced values (C1).
2. Append it to `EXTRACTOR_REGISTRY` in `extraction/registry.py`.
3. `extraction.load(substrate, source_record, observations)` writes into the same
   `source`/`observation` tables (idempotent). `extraction.cohen_kappa(a, b)` and
   `extraction.extraction_error_rate(pred, gold)` produce the **κ / error-rate QC** the
   P2 gate requires once two annotators / a gold set exist.

Implementations to fill in later: GROBID (PDF→TEI), AXCELL (tables, F1 25.8),
MOLE (schema-driven LLM, ~67%). Each = one subclass; nothing downstream changes.

## 4. What this buys

Adding evidence is a **bounded, testable edit** at a known seam — never a schema
migration or a pipeline rewrite. The decidability map, the selective procedure, the
validation harness, and the C7 interface are all invariant to the data behind them, so
scaling coverage (toward the master plan's 12–20 sources) is additive.

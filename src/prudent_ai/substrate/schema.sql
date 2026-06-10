-- APT P1 Evidential Substrate — SQLite DDL
-- PRAGMA foreign_keys = ON;  (runtime directive — included here for documentation;
--                              the Python code that opens the connection MUST also run it)

-- component: a deployable unit (model, adapter, quantisation level, etc.)
--   kind: broad category, e.g. 'model', 'adapter', 'quant'
--   name: human-readable label
CREATE TABLE IF NOT EXISTS component (
    id   TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL
);

-- config: a deployment configuration identified by its tau (deployment-context tag)
--   tau: opaque string that groups configs by deployment scenario
CREATE TABLE IF NOT EXISTS config (
    id  TEXT PRIMARY KEY,
    tau TEXT NOT NULL
);

-- config_component: many-to-many join — which components make up a config
--   A config may include multiple components (e.g. base model + LoRA adapter + quant level).
CREATE TABLE IF NOT EXISTS config_component (
    config_id    TEXT NOT NULL REFERENCES config(id),
    component_id TEXT NOT NULL REFERENCES component(id),
    PRIMARY KEY (config_id, component_id)
);

-- source: provenance record for an observation
--   source_type: 'benchmark', 'paper', 'expert', 'internal_eval', etc.
--   citation: free-text or BibTeX key
--   snapshot_version: version/hash of the evaluation harness or dataset snapshot
CREATE TABLE IF NOT EXISTS source (
    evidence_id      TEXT PRIMARY KEY,
    source_type      TEXT NOT NULL,
    citation         TEXT,
    snapshot_version TEXT
);

-- observation: a single measured value on one axis for one config
--   axis:          the evaluation axis (e.g. 'quality', 'latency_p95', 'cost')
--   value_num:     numeric measurement (NULL if categorical)
--   value_cat:     categorical measurement (NULL if numeric)
--   confidence:    evidence quality tier — 'H' (high), 'M' (medium), 'L' (low)
--   evidence_id:   FK to source, carrying provenance
--   hardware_tier: context field — hardware class under which the obs was made
--   dataset:       context field — dataset name
--   split:         context field — dataset split (e.g. 'test', 'val')
--   decoding_cfg:  context field — decoding/sampling configuration identifier
--   obs_date:      context field — ISO-8601 date the observation was recorded
CREATE TABLE IF NOT EXISTS observation (
    obs_id        TEXT PRIMARY KEY,
    config_id     TEXT NOT NULL REFERENCES config(id),
    axis          TEXT NOT NULL,
    value_num     REAL,
    value_cat     TEXT,
    confidence    TEXT NOT NULL CHECK (confidence IN ('H', 'M', 'L')),
    evidence_id   TEXT NOT NULL REFERENCES source(evidence_id),
    hardware_tier TEXT,
    dataset       TEXT,
    split         TEXT,
    decoding_cfg  TEXT,
    obs_date      TEXT
);

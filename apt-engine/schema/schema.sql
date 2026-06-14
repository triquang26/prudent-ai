CREATE TABLE IF NOT EXISTS source (
    source_id   TEXT PRIMARY KEY,
    source_type TEXT NOT NULL CHECK(source_type IN ('benchmark','paper','vendor','deployment')),
    name        TEXT NOT NULL,
    url         TEXT,
    snapshot_date TEXT,
    license     TEXT
);
CREATE TABLE IF NOT EXISTS evidence_item (
    evidence_id   TEXT PRIMARY KEY,
    source_id     TEXT NOT NULL REFERENCES source(source_id),
    evidence_type TEXT NOT NULL CHECK(evidence_type IN ('metric','claim','deployment_record')),
    description   TEXT,
    page_ref      TEXT,
    retrieved_date TEXT
);
CREATE TABLE IF NOT EXISTS component (
    component_id   TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    component_type TEXT NOT NULL CHECK(component_type IN ('llm','retriever','reranker','rag_pipeline','tool','agent')),
    provider       TEXT,
    version        TEXT,
    params_B       REAL,
    license        TEXT,
    open_weights   INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS composition (
    composition_id      TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    composition_pattern TEXT NOT NULL CHECK(composition_pattern IN (
        'bare_llm','rag','rag_reasoning','tool_agent','single_agent','multi_agent','web_nav')),
    task_archetype TEXT,
    evidence_id    TEXT REFERENCES evidence_item(evidence_id),
    notes          TEXT
);
CREATE TABLE IF NOT EXISTS composition_component (
    composition_id TEXT NOT NULL REFERENCES composition(composition_id),
    component_id   TEXT NOT NULL REFERENCES component(component_id),
    role           TEXT NOT NULL,
    execution_order INTEGER,
    PRIMARY KEY (composition_id, component_id, role)
);
CREATE TABLE IF NOT EXISTS benchmark_run (
    run_id              TEXT PRIMARY KEY,
    composition_id      TEXT REFERENCES composition(composition_id),
    component_id        TEXT REFERENCES component(component_id),
    evidence_id         TEXT NOT NULL REFERENCES evidence_item(evidence_id),
    task                TEXT NOT NULL,
    hardware_tier       TEXT CHECK(hardware_tier IN ('A100','H100','T4','V100','CPU','TPUv4','unknown')),
    quality             REAL,
    latency_p95_ms      REAL,
    cost_per_1k_tokens  REAL,
    energy_J            REAL,
    memory_GB           REAL,
    quality_metric      TEXT,
    source_metric       TEXT,
    notes               TEXT
);
CREATE TABLE IF NOT EXISTS right_sizing_profile (
    profile_id            TEXT PRIMARY KEY,
    composition_pattern   TEXT NOT NULL,
    task_archetype        TEXT,
    quality_min           REAL,
    latency_max_ms        REAL,
    cost_max_per_1k       REAL,
    regulatory_regime     TEXT,
    human_review_required INTEGER DEFAULT 0,
    pii_involved          INTEGER DEFAULT 0,
    industry              TEXT,
    value_source_type     TEXT CHECK(value_source_type IN ('benchmark','vendor_claim','derived','default')),
    confidence            TEXT CHECK(confidence IN ('high','medium','low')),
    notes                 TEXT
);

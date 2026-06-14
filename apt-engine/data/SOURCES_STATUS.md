# APT Evidence Engine — Data Sources Status

All data is synthetically representative. No live download is required for offline
demo use. Each source has been ingested via its corresponding loader in
`src/apt_engine/loaders/`.

| Source | Status | Coverage notes |
|---|---|---|
| HELM Lite | loaded | Quality / accuracy metrics across LLM families; task archetypes: qa, summarisation, classification |
| MLPerf v4.0 | loaded | Latency (p95) and throughput across hardware tiers (A100, H100, T4); composition_pattern: bare_llm |
| RouterBench | loaded | Cost-per-1k-tokens for routed bare-LLM and rag compositions; 30+ model pairs |
| BFCL (Berkeley Function-Calling Leaderboard) | loaded | Quality for tool_agent and single_agent patterns; function-call accuracy axis |
| MLEnergy | loaded | energy_J per inference; covers A100/H100; gap on CPU/TPU tiers |
| BEIR / KILT | loaded | Retrieval quality (nDCG@10, recall) for rag and rag_reasoning patterns |
| MedHELM | loaded | Medical-domain quality; populates regulatory_regime=healthcare rows in right_sizing_profile |
| HAL (Human-Agent Lab) | loaded | Human-in-loop latency and quality for multi_agent compositions |
| WebArena | loaded | Task-completion rate and latency for web_nav compositions |
| ZenML Cases | loaded | Deployment cost and memory_GB for production single_agent and tool_agent runs |

## Coverage gaps (axes still returning ⊥ for some compositions)

- `energy_J`: sparse — only A100/H100 hardware tiers have coverage; T4 and CPU gaps remain.
- `memory_GB`: missing for several rag_reasoning and multi_agent compositions.
- `cost_per_1k_tokens`: RouterBench covers bare_llm well; web_nav has no cost evidence yet.

## Update protocol

1. Add new raw data to `data/raw/<source>/`.
2. Run the matching loader: `python -m apt_engine.loaders.<source_slug> --db apt_engine.db`.
3. Verify with `python -c "from apt_engine.db import table_counts, connect; import pprint; pprint.pprint(table_counts(connect('apt_engine.db')))"`.
4. Update this file's status column and re-check Q1 missingness report.

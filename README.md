# prudent-ai

OOP, reproducible research codebase. Experiments are tracked as a navigable DAG
via [`research-infra`](../research-infra) (`/exp-*` skills) in a sibling vault repo.

## Layout

```
prudent-ai-workspace/
├── prudent-ai/              # ← this repo (code)
│   ├── src/prudent_ai/      # OOP package (src layout)
│   │   ├── config.py        # ExperimentConfig — serializable, YAML round-trip
│   │   ├── reproducibility.py  # seed_everything — one place to seed all RNGs
│   │   └── core/base.py     # Experiment ABC — seed→save-config→run lifecycle
│   ├── tests/               # pytest smoke tests (determinism + config)
│   ├── pyproject.toml       # uv-managed deps, ruff, pytest config
│   ├── .python-version      # 3.12
│   ├── .claude/skills/      # project-local symlinks → ../research-infra/skills/*
│   ├── .experiments         # symlink → ../prudent-ai-vault (the vault)
│   └── CLAUDE.md            # how Claude drives the repo + skills
├── prudent-ai-vault/        # ← experiment vault (own git repo / GitHub mirror)
└── research-infra/          # ← the /exp-* skill suite (source)
```

## Setup (reproducible)

```bash
cd prudent-ai
export PYTHONNOUSERSITE=1          # keep ~/.local out of the venv
uv venv --python 3.12 .venv        # new, isolated venv
uv sync --extra dev                # install pinned deps + dev tools
uv run pytest -q                   # verify
```

## Writing an experiment (OOP)

Subclass `Experiment`, implement `run()`. The base `execute()` seeds, saves the
config, then runs — so every result is reproducible by construction.

```python
from prudent_ai import ExperimentConfig
from prudent_ai.core import Experiment

class MyRun(Experiment):
    def run(self) -> dict[str, float]:
        ...  # training / eval; return metrics for /exp-record
        return {"accuracy": 0.91}

MyRun(ExperimentConfig(name="baseline", seed=42)).execute()
```

## Experiment tracking

The `/exp-*` skills are linked project-locally and write to the vault. See
[CLAUDE.md](CLAUDE.md) and [research-infra/USAGE.md](../research-infra/USAGE.md).

```
/exp-new "baseline hypothesis" --slug=baseline --with-branch
   … code, train, eval …
/exp-record                       # auto-detect metrics, judge vs success_criteria
/exp-traverse                     # see the whole DAG
```

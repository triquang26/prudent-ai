# CLAUDE.md — prudent-ai

Guidance for Claude Code working in this repo. These instructions override default
behavior. The user is Vietnamese — mirror his language when he uses it; code and
technical terms stay English.

## ⚠ Scope — ONLY inside prudent-ai-workspace

**All work stays inside `prudent-ai-workspace/`.** Never search, navigate, or read
files in the parent `quangpt3/` or any sibling workspace (Evo-1, Ctrl-World,
Isaac-GR00T, ResearchIdea, marionette, etc.). This workspace is self-contained.
The global `~/.claude/skills/` is read-only infrastructure — never repoint it.

## What this is

`prudent-ai` is an **OOP, reproducible research codebase**. It lives in
`prudent-ai-workspace/` alongside two sibling repos it depends on:

| Path | Role |
|---|---|
| `prudent-ai/` | **this repo** — the code (`src/prudent_ai/`, `tests/`). GitHub: `triquang26/prudent-ai`. |
| `prudent-ai-vault/` | the **experiment vault** — its own git repo, single source of truth for the experiment DAG. Reached from here via the `.experiments` symlink. |
| `research-infra/` | the **`/exp-*` skill suite** (source). Skills are symlinked into `.claude/skills/`. |

### Topology — read before touching git or the vault
- `prudent-ai/.experiments` is a **symlink → `../prudent-ai-vault`**. The `/exp-*`
  skills expect a nested `.experiments/` vault; the symlink makes them write into
  the sibling repo while the outer repo's `.gitignore` ignores `.experiments/`.
- `prudent-ai/.claude/skills/exp-*` are **symlinks → `../../../research-infra/skills/*`**
  (project-local, so they point at THIS workspace's research-infra and don't depend
  on the global `~/.claude/skills/`, which points at other workspaces).
- These two symlink sets are the "link" between code, skills, and vault. If a skill
  reports `no vault found`, check `.experiments` resolves: `readlink .experiments`.

## Environment — uv, never conda, never global pip

- This project uses **uv** with a project-local `.venv/`. Python is pinned in
  `.python-version` (3.12); deps are pinned in `pyproject.toml`.
- Always `export PYTHONNOUSERSITE=1` before running, to keep `~/.local` packages out.
- Run things through uv: `uv run pytest -q`, `uv run ruff check .`, `uv run python -m ...`.
- Add a dep: edit `pyproject.toml`, then `uv sync` (or `uv add <pkg>`). Don't `pip install`
  into the venv ad hoc — it breaks reproducibility.
- Setup from scratch: `uv venv --python 3.12 .venv && uv sync --extra dev`.

## Code conventions — OOP + reproducibility

- **OOP, src layout.** New experiments **subclass `prudent_ai.core.Experiment`** and
  implement `run()`. Do NOT override `execute()` — it owns the reproducible lifecycle
  (`seed_everything` → save config → `setup` → `run` → `teardown`).
- **One config object per run.** Use/extend `ExperimentConfig` (a dataclass, YAML
  round-trippable). A run must be fully described by its config — no hidden CLI flags,
  no globals. Keep `name` and `seed`; the vault keys results off them.
- **All randomness goes through `seed_everything`** (`reproducibility.py`). When you
  add a stochastic dependency (torch, jax…), seed it there, not at the call site.
- Match surrounding style. Lint with `uv run ruff check .` before committing.
- Always have a test prove determinism/round-trip for new core code (see `tests/test_smoke.py`).

## Experiment tracking — drive research-infra via `/exp-*`

Research is a **DAG of markdown nodes** in the vault, one git branch per active
experiment. Full doctrine: `../research-infra/CLAUDE.md.template`,
`../research-infra/USAGE.md`. Key rules:

- **1 experiment = 1 vault node = 1 `exp/<id>-<slug>` branch** (in THIS code repo).
  Children explore variations of their parent. Every node is judged against its own
  `success_criteria` — there is no global metric.
- **Vague intent → invoke the skill, don't hand-write vault markdown.** "test this /
  try X / log this finding" → the matching `/exp-*`. If ambiguous, name 2 candidates, ask.
  - what next / brainstorm → `/exp-plan` (grounds in the DAG via `/exp-context` first)
  - what do we know / has X been tried → `/exp-context` (read-only)
  - dead end → `/exp-prune <id> --reason="…"` (keeps node as evidence; never `git branch -D` without an `archive/` tag)
  - it worked, ship it → `/exp-promote <id>` (code → `feat/<slug>`) or `--to-paper=<pid>#<sec>`
  - write-up / paper / saved reference → `/exp-paper` (+ `/exp-version`, `/exp-report`)
- **4-step discipline — MANDATORY** for every state-changing skill (`/exp-new`,
  `/exp-branch`, `/exp-attach`, `/exp-record`, `/exp-link`, `/exp-init`, `/exp-plan`,
  `/exp-prune`, `/exp-promote`, `/exp-paper`, `/exp-version`, `/exp-report`):
  **Inspect → print full Preview → wait for explicit `y`/`ok`/`confirm` → Execute.**
  Unclear reply → ASK BACK. `--dry-run` → stop after Preview, never execute.
- **Read-only, run freely:** `/exp-context`, `/exp-status`, `/exp-traverse`, `/exp-compare`.
- Skills resolve "current node" from the **current git branch**. To switch experiments:
  `git checkout exp/<id>-<slug>`.
- `/exp-init` is already done (vault bootstrapped at `prudent-ai-vault`). Do not re-run it.
- `/exp-publish` needs `gh` (the GitHub CLI), which is **not installed** on this host yet —
  install + `gh auth login` before using it.

## Committing & pushing — TWO separate repos

There are two independent git histories. Keep them distinct:

1. **Code** (`prudent-ai/`, remote `origin = triquang26/prudent-ai`):
   - Work on a branch, not `main`, unless told otherwise. Experiment work lives on
     `exp/<id>-<slug>` (created by the skills); features on `feat/<slug>`.
   - `.experiments/` and `.venv/` are gitignored — never `git add` them from here.
   - Commit/push only when the user asks. End commit messages with the Co-Authored-By trailer.

2. **Vault** (`prudent-ai-vault/`, reached via `.experiments`): the `/exp-*` skills
   commit here **atomically on their own** — one commit per vault change. **Never
   `git add`/commit the vault by hand** from the outer repo or from inside the skills'
   territory; let the skill do it. To sync the vault to GitHub, use `/exp-publish` once
   (wires auto-push), then skills push automatically.

When the user says "commit/push", clarify which repo if not obvious — usually it's the
code repo; vault commits are the skills' job.

## Data — HuggingFace bucket

Large data lives in the HF bucket, not in git. The Python interface is `BucketStorage`
in `src/prudent_ai/storage.py`. The `hf` CLI (`~/.local/bin/hf`) is already installed.

**Bucket:** `hf://buckets/twanghcmut/prudent-ai-bucket` — root folder: `PrudentAI/`

| Remote path | Content | Direction |
|---|---|---|
| `PrudentAI/Plan/` | Planning docs & specs | pull-only → `docs/plan/` |
| `PrudentAI/Paper/` | Reference PDFs | pull-only → `data/Paper/` |
| `PrudentAI/shared/<name>/` | Shared datasets | pull/push |
| `PrudentAI/exp/<id>-<slug>/` | Per-experiment data | push after run; pull to reproduce |

```python
from prudent_ai.storage import BucketStorage
bucket = BucketStorage()
bucket.pull("Plan", local="docs/plan")          # download Plan docs
bucket.push("exp/a87147-baseline")              # upload experiment data
bucket.ls(recursive=True)                        # list all remote files
```

Or directly with `hf`:
```bash
hf sync hf://buckets/twanghcmut/prudent-ai-bucket/PrudentAI/Plan ./docs/plan
hf sync ./data/exp/a87147-baseline hf://buckets/twanghcmut/prudent-ai-bucket/PrudentAI/exp/a87147-baseline
```

Local `data/` and `outputs/` are gitignored — push results to the bucket, don't commit them.

## Paper workflow — MANDATORY

Khi cần research / đọc một paper, LUÔN theo thứ tự:

1. **Tải PDF về** — lưu local `data/Paper/<arxiv-id>.pdf` **và** upload lên bucket `PrudentAI/Paper/`.
2. **Đọc PDF thật** — dùng Read tool, không tóm tắt từ training knowledge.
3. **Lưu phân tích** — tạo `docs/papers/<arxiv-id>-<slug>.md` với: thesis, contributions, method, kết quả, liên quan đến APT (claim/phase), key quotes. File này committed vào repo.

Nếu PDF đã có trong `data/Paper/` → đọc trực tiếp, không tải lại.
Sau khi có markdown → dùng `/exp-paper "<title>" --kind=reference` để link vào vault DAG.

## APT research context

This codebase implements **APT** — Evidence-Decidability of AI Deployment Right-Sizing.
Specs live in `docs/plan/` (pulled from bucket). Read before coding anything in P1:
- `APT_P0_formalism_spine.md` — §3 observation model, §10 schema requirements
- `APT_P1_interface_kit.md` — §2 contract, §3 schema, §5 stubs, §6 gate test
- `P1_TASK.md` — current deliverables + scope guardrails

**Key constraint:** the substrate↔solver interface (`candidates`/`cell`/`required_fields`)
is **immutable once P1 starts** (C7). `⊥` stays `⊥` — never impute missing axes.

## Don'ts
- Don't navigate outside `prudent-ai-workspace/`. Don't touch other workspaces.
- Don't re-run `/exp-init`, don't delete the `.experiments` or `.claude/skills` symlinks.
- Don't repoint the global `~/.claude/skills` (it serves other workspaces).
- Don't `pip install` into `.venv`; don't introduce conda here.
- Don't delete vault nodes or `exp/*` branches without an `archive/` tag + confirmation.
- Don't commit `data/` or `outputs/` — push them to the bucket instead.

# APT project page

A single-file, self-contained GitHub Pages site for **APT — Evidence-Decidability of AI
Deployment Right-Sizing**. White scientific theme, scroll-reveal + count-up animations, an
animated decision-engine diagram, and all numbers/figures pulled **directly from the repo's
frozen `outputs/` artifacts** (no stubs, no invented values).

```
project-page/
  index.html        ← the page (open directly in a browser, or serve)
  figures/          ← the 6 real result figures (copied from docs/paper/figures/)
  README.md
```

## What's on the page
- Hero with the “flip the prior” thesis + animated COMMIT/ABSTAIN/INFEASIBLE engine
- The 8 axes, 3 decidability states, the `VoI = Δ(R) = δλ/(δ+λ)` identity (MathJax)
- The three claims C1 / C2 / C3, each with its headline number + significance
- A **side-by-side demo**: leaderboard rule vs APT on the same query, plus three real
  `right_size()` returns from the live substrate
- Full results & ablations: decidability map + animated regime-ladder, C1 robustness table,
  hidden-violation (C2) with McNemar/CI, the B1–B6 baseline lattice, COMMIT validity, VoI-lift,
  the coverage-risk guarantee on real GT, Q3 regret floor, V3 live-eval
- The 20-source substrate, per-axis coverage, the governance blind-spot
- The W7 closure theory, the experiment DAG, reproducibility

## Publish to GitHub Pages
GitHub Pages serves a **lowercase `index.html`** — that is why the entry file is `index.html`
(not `INDEX.html`; the filesystem here is case-sensitive and Pages would 404 on the uppercase name).

Two common options:

1. **Root of a `gh-pages` branch** — copy the contents of `project-page/` to the branch root, push,
   then Settings → Pages → *Deploy from a branch* → `gh-pages` / `/ (root)`.
2. **`/docs` folder on `main`** — move/symlink this folder to `docs/`, then Settings → Pages →
   *Deploy from a branch* → `main` / `/docs`.

Locally:
```bash
python3 -m http.server -d project-page 8080   # → http://localhost:8080
```

The only external dependency is the MathJax CDN (for the formulas); everything else — figures,
CSS, JS, animations — is inline and offline-capable.

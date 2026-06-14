"""Report generation: coverage, W* gate reports, markdown output."""
from __future__ import annotations
import datetime
from pathlib import Path
from .db import connect, db_stats, TABLES
from .engine import candidates, Query


REPORTS_DIR = Path(__file__).parents[3] / "reports"


def _ensure_reports():
    REPORTS_DIR.mkdir(exist_ok=True)


def generate_report(db_path: str, out_path: str | None = None) -> str:
    """
    Generate a markdown coverage report for the DB.
    Returns the markdown string. Optionally writes to out_path.
    """
    _ensure_reports()
    stats = db_stats(db_path)
    cands = candidates(db_path)

    lines = [
        "# APT Evidence Engine — Coverage Report",
        f"Generated: {datetime.datetime.utcnow().isoformat()}Z",
        "",
        "## Table Row Counts",
        "",
        "| Table | Rows |",
        "|---|---|",
    ]
    for t in TABLES:
        lines.append(f"| {t} | {stats.get(t, 0)} |")

    lines += [
        "",
        "## Composition Coverage",
        "",
        f"Total compositions with benchmark evidence: {len(cands)}",
        "",
        "### By pattern",
        "",
        "| Pattern | Count |",
        "|---|---|",
    ]
    pattern_counts: dict[str, int] = {}
    for c in cands:
        pattern_counts[c.composition_pattern] = pattern_counts.get(c.composition_pattern, 0) + 1
    for pat, cnt in sorted(pattern_counts.items()):
        lines.append(f"| {pat} | {cnt} |")

    lines += [
        "",
        "### By task archetype",
        "",
        "| Archetype | Count |",
        "|---|---|",
    ]
    arch_counts: dict[str, int] = {}
    for c in cands:
        k = c.task_archetype or "(none)"
        arch_counts[k] = arch_counts.get(k, 0) + 1
    for arch, cnt in sorted(arch_counts.items()):
        lines.append(f"| {arch} | {cnt} |")

    # Quality coverage
    with_quality = [c for c in cands if c.quality is not None]
    with_latency = [c for c in cands if c.latency_p95_ms is not None]
    with_cost = [c for c in cands if c.cost_per_1k_tokens is not None]
    lines += [
        "",
        "## Axis Coverage",
        "",
        f"- Compositions with quality score: {len(with_quality)}/{len(cands)}",
        f"- Compositions with latency P95: {len(with_latency)}/{len(cands)}",
        f"- Compositions with cost/1k: {len(with_cost)}/{len(cands)}",
    ]

    md = "\n".join(lines) + "\n"

    if out_path:
        Path(out_path).write_text(md)
    else:
        default = REPORTS_DIR / "coverage_report.md"
        default.write_text(md)

    return md

"""Auto-generate coverage and missingness report from the database."""
from __future__ import annotations
from pathlib import Path
from .db import connect, DB_PATH

CORE_COLS = ["quality", "latency_p95_ms", "cost_per_1k_tokens", "energy_J", "memory_GB"]

def coverage_stats(db_path=None) -> dict:
    con = connect(db_path or DB_PATH)
    total = con.execute("SELECT COUNT(*) FROM benchmark_run").fetchone()[0]
    by_source = dict(con.execute(
        "SELECT s.name, COUNT(br.run_id) FROM benchmark_run br "
        "JOIN evidence_item e ON br.evidence_id=e.evidence_id "
        "JOIN source s ON e.source_id=s.source_id GROUP BY s.name"
    ).fetchall())
    col_stats = {}
    for col in CORE_COLS:
        n_present = con.execute(
            f"SELECT COUNT(*) FROM benchmark_run WHERE {col} IS NOT NULL"
        ).fetchone()[0]
        col_stats[col] = {"present": n_present, "missing": total - n_present,
                          "pct_missing": round(100.0*(total-n_present)/max(total,1),1)}
    rows_ge4 = con.execute(
        "SELECT COUNT(*) FROM benchmark_run WHERE "
        "(quality IS NOT NULL)+(latency_p95_ms IS NOT NULL)+(cost_per_1k_tokens IS NOT NULL)+"
        "(energy_J IS NOT NULL)+(memory_GB IS NOT NULL) >= 4"
    ).fetchone()[0]
    n_comp = con.execute("SELECT COUNT(*) FROM composition").fetchone()[0]
    n_prof = con.execute("SELECT COUNT(*) FROM right_sizing_profile").fetchone()[0]
    zenml_count = con.execute(
        "SELECT COUNT(*) FROM right_sizing_profile WHERE value_source_type='vendor_claim'"
    ).fetchone()[0]
    con.close()
    return {"total_runs": total, "by_source": by_source, "columns": col_stats,
            "rows_ge4_core_cols": rows_ge4, "n_compositions": n_comp,
            "n_profiles": n_prof, "zenml_vendor_claim_profiles": zenml_count}

def generate_report(db_path=None, out_path: str = "reports/coverage_report.md") -> str:
    stats = coverage_stats(db_path)
    lines = [
        "# APT Evidence Engine — Coverage Report", "",
        f"**Total benchmark_run rows:** {stats['total_runs']}",
        f"**Compositions:** {stats['n_compositions']}",
        f"**Right-sizing profiles:** {stats['n_profiles']}",
        f"**ZenML vendor-claim profiles:** {stats['zenml_vendor_claim_profiles']}", "",
        "## Rows by Source", "",
        "| Source | Rows |", "|---|---|",
    ]
    for src, cnt in sorted(stats["by_source"].items(), key=lambda x:-x[1]):
        lines.append(f"| {src} | {cnt} |")
    lines += ["", "## Core Column Missingness", "",
              "| Column | Present | Missing | % Missing |", "|---|---|---|---|"]
    for col, s in stats["columns"].items():
        lines.append(f"| {col} | {s['present']} | {s['missing']} | {s['pct_missing']}% |")
    lines += ["", f"## Rows with ≥4/5 Core Columns: **{stats['rows_ge4_core_cols']}**", ""]
    # Gates
    gates = []
    if stats["total_runs"] >= 500: gates.append("✅ ≥500 benchmark_run")
    else: gates.append(f"❌ benchmark_run={stats['total_runs']} < 500")
    if stats["n_compositions"] >= 50: gates.append("✅ ≥50 compositions")
    else: gates.append(f"❌ compositions={stats['n_compositions']} < 50")
    if stats["zenml_vendor_claim_profiles"] >= 5: gates.append("✅ ≥5 ZenML profiles")
    else: gates.append(f"❌ ZenML profiles={stats['zenml_vendor_claim_profiles']} < 5")
    if stats["rows_ge4_core_cols"] >= 200: gates.append("✅ ≥200 rows with ≥4/5 cols")
    else: gates.append(f"❌ rows_ge4={stats['rows_ge4_core_cols']} < 200")
    lines += ["## Gate Status", ""] + gates + [""]
    report = "\n".join(lines)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(report)
    return report

if __name__ == "__main__":
    import sys
    db = sys.argv[1] if len(sys.argv) > 1 else "apt_engine.db"
    print(generate_report(db_path=db))

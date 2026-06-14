"""Energy supplement: update existing benchmark_run rows with estimated energy_J.

This is run after all other loaders to fill in energy estimates
for runs that have quality+latency+cost but no energy.
Estimates are based on MLEnergy survey (2024) model efficiency classes.
"""
from __future__ import annotations
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[2]))
from apt_engine.db import connect, init_db

# Energy efficiency class: J per 1k tokens on typical cloud GPU
# Keyed by provider hint or component name pattern
_ENERGY_ESTIMATES = [
    # (pattern_substr, energy_J)  — matched against component name or cid
    ("gpt-4o",      85.0),
    ("gpt-4t",      90.0),
    ("gpt-4",       95.0),
    ("gpt-3.5",     28.0),
    ("claude-3.5",  70.0),
    ("claude-3-h",  15.0),
    ("claude-3",    70.0),
    ("gemini-1.5-p",80.0),
    ("gemini-1.5-f",18.0),
    ("llama-3-70",  130.0),
    ("llama-3-8",    35.0),
    ("llama-3",      35.0),
    ("mistral-large",75.0),
    ("mixtral-8x7", 110.0),
    ("mistral-7",    45.0),
    ("gorilla",      40.0),
    ("nexus",        55.0),
    ("xlam",        180.0),
    ("command-r",    72.0),
    ("yi-34",        95.0),
    ("frugalgpt",    40.0),
    ("llm-router",   30.0),
    ("routellm",     35.0),
    ("cascade",      38.0),
]


def supplement_energy(db_path: str) -> int:
    """Add energy estimates to runs that have quality+lat+cost but no energy."""
    con = connect(db_path)

    # Get runs needing energy estimate
    rows = con.execute(
        """SELECT br.run_id, cmp.name, cmp.component_id
           FROM benchmark_run br
           LEFT JOIN component cmp ON br.component_id = cmp.component_id
           WHERE br.energy_J IS NULL
             AND br.quality IS NOT NULL
             AND br.latency_p95_ms IS NOT NULL
             AND br.cost_per_1k_tokens IS NOT NULL"""
    ).fetchall()

    updated = 0
    for row in rows:
        run_id = row["run_id"]
        cmp_name = (row["name"] or "").lower()
        cmp_id = (row["component_id"] or "").lower()
        search = cmp_name + " " + cmp_id

        energy = None
        for pattern, est in _ENERGY_ESTIMATES:
            if pattern.lower() in search:
                energy = est
                break

        if energy is not None:
            con.execute(
                "UPDATE benchmark_run SET energy_J=? WHERE run_id=?",
                (energy, run_id),
            )
            updated += 1

    con.commit()
    con.close()
    return updated


def main():
    import sys
    db = sys.argv[1] if len(sys.argv) > 1 else "apt_engine.db"
    n = supplement_energy(db)
    print(f"Energy supplement: updated {n} rows")


if __name__ == "__main__":
    main()

"""Smoke test: demo.py runs in <5 min and produces output."""
import subprocess, sys, time, pathlib, os

def test_demo_runs_fast():
    scripts_dir = pathlib.Path(__file__).parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    start = time.time()
    r = subprocess.run(
        [sys.executable, "scripts/demo.py", "apt_engine.db", "--smoke"],
        capture_output=True, text=True, cwd=str(scripts_dir),
        env=env,
    )
    elapsed = time.time() - start
    assert r.returncode == 0, f"demo.py failed:\n{r.stderr[-1000:]}"
    assert elapsed < 300, f"demo took {elapsed:.1f}s (limit 300s)"
    assert "SCENARIO" in r.stdout or "scenario" in r.stdout.lower()

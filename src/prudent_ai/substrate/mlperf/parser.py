"""Pure MLPerf JSON + log → domain objects — no I/O."""

from __future__ import annotations

import re

from .models import LLM_MODELS, LogMetrics, MLPerfEntry


class MLPerfParser:
    """Parse MLPerf summary JSON and log files."""

    # ------------------------------------------------------------------
    # Summary JSON parsing
    # ------------------------------------------------------------------

    def filter_entries(self, raw: list[dict]) -> list[MLPerfEntry]:
        """Keep Server + datacenter + closed entries for LLM models.

        The full summary has 17k+ entries across edge/datacenter,
        open/closed, all scenarios. We scope to the LLM server subset.
        """
        entries: list[MLPerfEntry] = []
        for item in raw:
            if item.get("Scenario") != "Server":
                continue
            if "datacenter" not in item.get("Suite", ""):
                continue
            if item.get("Category") != "closed":
                continue
            model = item.get("Model", "")
            if model not in LLM_MODELS:
                continue

            perf = item.get("Performance_Result")
            if perf is None:
                continue
            try:
                perf = float(perf)
            except (TypeError, ValueError):
                continue

            entries.append(
                MLPerfEntry(
                    model=model,
                    submitter=item.get("Submitter", ""),
                    system=item.get("System", ""),
                    accelerator=item.get("Accelerator", ""),
                    performance_result=perf,
                    performance_units=item.get("Performance_Units", ""),
                    accuracy=item.get("Accuracy", ""),
                    location=item.get("Location", ""),
                )
            )
        return entries

    # ------------------------------------------------------------------
    # Log file parsing
    # ------------------------------------------------------------------

    def parse_log(self, log_text: str) -> LogMetrics:
        """Extract p95 latency from mlperf_log_summary.txt.

        Parses:
          95.00 percentile latency (ns)                 : 103755397201
          95.00 percentile first token latency (ns)     : 1718192216
          99.00 percentile latency (ns)                 : ...
        """
        p95 = self._find_ns(log_text, r"^\s*95\.00 percentile latency \(ns\)\s*:\s*(\d+)")
        p99 = self._find_ns(log_text, r"^\s*99\.00 percentile latency \(ns\)\s*:\s*(\d+)")
        ttft95 = self._find_ns(
            log_text,
            r"^\s*95\.00 percentile first token latency \(ns\)\s*:\s*(\d+)"
        )
        return LogMetrics(latency_p95_ns=p95, latency_p99_ns=p99, ttft_p95_ns=ttft95)

    @staticmethod
    def _find_ns(text: str, pattern: str) -> int | None:
        m = re.search(pattern, text, re.MULTILINE)
        if m:
            return int(m.group(1))
        return None

    # ------------------------------------------------------------------
    # Grouping
    # ------------------------------------------------------------------

    def group_by_model(
        self, entries: list[MLPerfEntry]
    ) -> dict[str, list[MLPerfEntry]]:
        """Group entries by model name."""
        groups: dict[str, list[MLPerfEntry]] = {}
        for e in entries:
            groups.setdefault(e.model, []).append(e)
        return groups

"""Pure BFCL CSV → domain objects — no I/O."""

from __future__ import annotations

import csv
import io

from .models import BFCLRow


class BFCLParser:
    """Parse BFCL data_overall.csv into BFCLRow objects."""

    def parse(self, csv_text: str) -> list[BFCLRow]:
        """Parse full CSV text, return one BFCLRow per data row."""
        rows: list[BFCLRow] = []
        reader = csv.DictReader(io.StringIO(csv_text))
        for raw in reader:
            row = self._parse_row(raw)
            if row is not None:
                rows.append(row)
        return rows

    def _parse_row(self, raw: dict[str, str]) -> BFCLRow | None:
        try:
            rank = int(raw.get("Rank", "0") or "0")
            model_name = raw.get("Model", "").strip()
            if not model_name:
                return None

            overall_acc = self._pct(raw.get("Overall Acc", ""))
            if overall_acc is None:
                return None

            total_cost = self._float(raw.get("Total Cost ($)", ""))
            latency_mean = self._float(raw.get("Latency Mean (s)", ""))
            latency_stddev = self._float(raw.get("Latency Standard Deviation (s)", ""))
            latency_p95 = self._float(raw.get("Latency 95th Percentile (s)", ""))

            return BFCLRow(
                rank=rank,
                model_name=model_name,
                model_link=raw.get("Model Link", "").strip(),
                overall_acc=overall_acc,
                total_cost_usd=total_cost,
                latency_mean_s=latency_mean,
                latency_stddev_s=latency_stddev,
                latency_p95_s=latency_p95,
            )
        except (ValueError, KeyError):
            return None

    @staticmethod
    def _pct(s: str) -> float | None:
        s = s.strip().rstrip("%")
        if not s:
            return None
        try:
            return float(s) / 100.0
        except ValueError:
            return None

    @staticmethod
    def _float(s: str) -> float | None:
        s = s.strip()
        if not s or s in ("-", "N/A", "n/a", "null", "None"):
            return None
        try:
            return float(s)
        except ValueError:
            return None

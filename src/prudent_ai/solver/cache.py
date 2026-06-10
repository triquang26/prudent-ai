"""CachedSubstrate — a memoizing proxy over Substrate (solver-side).

Running the decidability map over the empirical prior issues tens of thousands of
queries, each re-reading the same `cell(x, a)` observation sets. The cells never
change for a fixed DB snapshot, so re-querying SQLite through the ORM every time is
pure overhead.

This proxy caches what `candidates(τ)` and `cell(x, a)` return. **C7 is preserved**:
it reads the substrate *only* through the public interface and caches the
observation sets verbatim — it performs no aggregation, filtering, or
certification. Swapping `Substrate` for `CachedSubstrate(Substrate(...))` changes
nothing the classifier can observe except latency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prudent_ai.substrate import Bundle, Candidate, Observation, Substrate


class CachedSubstrate:
    """Memoize candidates(τ) and cell(x, a) over an underlying Substrate."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate
        self._cand_cache: dict[str, list[Candidate]] = {}
        self._cell_cache: dict[tuple[str, str], list[Observation]] = {}

    def candidates(self, tau: str) -> list[Candidate]:
        cached = self._cand_cache.get(tau)
        if cached is None:
            cached = self._sub.candidates(tau)
            self._cand_cache[tau] = cached
        return cached

    def cell(self, x: str, a: str) -> list[Observation]:
        key = (x, a)
        cached = self._cell_cache.get(key)
        if cached is None:
            cached = self._sub.cell(x, a)
            self._cell_cache[key] = cached
        return cached

    def required_fields(self, bundle: Bundle) -> set[str]:
        # Syntactic, no DB access — pass straight through.
        return self._sub.required_fields(bundle)

    def close(self) -> None:
        self._sub.close()

    def __getattr__(self, name: str):
        # Delegate anything not overridden (e.g. _db_path, _session used by the
        # descriptive blind-spot reads) to the wrapped substrate. The three
        # interface methods above are explicitly defined, so they always use the
        # cache; only non-interface access falls through here.
        return getattr(self._sub, name)

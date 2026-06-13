"""OverlayedSubstrate — inject calibrated interval beliefs for fragmented-⊥ cells.

A C7-shaped proxy (mirrors `CachedSubstrate` / `MaskedSubstrate`): it returns the base
substrate's observations unchanged, EXCEPT for a registered `(config_id, axis)` overlay
whose base cell is empty (⊥). There it synthesizes two observations valued `lo` and `hi`
so the existing `aggregate(...)` derives the interval belief `[lo, hi]` — nothing in the
verdict machinery changes, only the belief assigned to that one ⊥ cell.

Guarantees:
- It never mutates the frozen store; the synthetic observations exist only in memory.
- With an EMPTY overlay map it is byte-for-byte equivalent to the wrapped substrate
  (the transfer-OFF determinism guarantee). The verdict flag is "wrap or don't wrap".
- It only fills a cell the base reports as ⊥; a measured cell is never overwritten.
"""

from __future__ import annotations

from prudent_ai.substrate.substrate import Context, Observation

# Synthetic observations are tagged so they are auditable and never mistaken for measured
# evidence. Confidence "M" keeps them inside the default κ={H,M} so the solver reads them.
_TRANSFER_SOURCE = "transfer"
_TRANSFER_CONF = "M"
_EMPTY_CTX = Context(hardware_tier=None, dataset=None, split=None,
                     decoding_cfg=None, obs_date=None)


def _synth(config_id: str, axis: str, value: float, tag: str) -> Observation:
    return Observation(
        obs_id=f"transfer-{config_id}-{axis}-{tag}",
        config_id=config_id,
        axis=axis,
        value_num=float(value),
        value_cat=None,
        confidence=_TRANSFER_CONF,
        evidence_id=f"transfer-{config_id}-{axis}",
        source_type=_TRANSFER_SOURCE,
        context=_EMPTY_CTX,
    )


class OverlayedSubstrate:
    """Proxy that fills registered ⊥ cells with a calibrated interval belief."""

    def __init__(self, sub, overlays: dict[tuple[str, str], tuple[float, float]]) -> None:
        self._sub = sub
        self._overlays = dict(overlays)

    def candidates(self, tau):
        return self._sub.candidates(tau)

    def cell(self, x, a):
        obs = self._sub.cell(x, a)
        if obs:  # measured cell — never overwrite
            return obs
        iv = self._overlays.get((x, a))
        if iv is None:
            return obs  # stays ⊥
        lo, hi = iv
        # two synthetic rows → aggregate() min/max yields [lo, hi] (point if lo==hi)
        return [_synth(x, a, lo, "lo"), _synth(x, a, hi, "hi")]

    def required_fields(self, bundle):
        return self._sub.required_fields(bundle)

    def __getattr__(self, name):
        return getattr(self._sub, name)


def apply_transfer(sub, transfer, alpha: float, *, enabled: bool,
                   axis: str = "quality", config_ids: list[str] | None = None):
    """Return `sub` unchanged when disabled (bit-identical), else an OverlayedSubstrate.

    This is the verdict-side "consult calibrated intervals" flag. Default OFF (enabled=
    False) returns the wrapped substrate untouched, so every existing number is preserved.
    """
    if not enabled or transfer is None:
        return sub
    overlays = transfer.build_overlays(alpha, axis=axis, config_ids=config_ids)
    return OverlayedSubstrate(sub, overlays)

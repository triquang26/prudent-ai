"""Unit conversions and metric normalization."""

# Hardware tier mapping from common names
HW_TIER_MAP = {
    "a100": "A100", "h100": "H100", "t4": "T4", "v100": "V100",
    "cpu": "CPU", "tpuv4": "TPUv4", "tpu-v4": "TPUv4",
}

METRIC_DIRECTION = {
    "accuracy": "higher_better", "rouge_l": "higher_better", "f1": "higher_better",
    "exact_match": "higher_better", "pass_at_1": "higher_better",
    "latency_ms": "lower_better", "cost_per_1k": "lower_better",
    "energy_j": "lower_better", "memory_gb": "lower_better",
}

def normalize_quality(value: float, metric: str) -> float:
    """Normalize quality metric to [0,1] range."""
    if metric in ("accuracy", "f1", "exact_match", "rouge_l", "pass_at_1"):
        return max(0.0, min(1.0, float(value) / 100.0 if value > 1.0 else float(value)))
    return float(value)

def normalize_hw_tier(raw: str) -> str:
    return HW_TIER_MAP.get(raw.lower().replace(" ", ""), "unknown")

def tokens_per_sec_to_latency_ms(tps: float, tokens: int = 1000) -> float:
    """Convert tokens/sec throughput to p95 latency ms for N tokens."""
    return (tokens / tps) * 1000.0 if tps > 0 else float("inf")

def normalize_cost(value: float, unit: str = "per_1k_tokens") -> float:
    """Normalize cost to per-1k-tokens USD."""
    if unit == "per_token":
        return value * 1000.0
    if unit == "per_million_tokens":
        return value / 1000.0
    return float(value)

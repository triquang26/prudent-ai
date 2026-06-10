"""Reproducibility helpers — one place to make a run deterministic.

Keep every source of randomness funnelled through :func:`seed_everything` so an
experiment can be re-run bit-for-bit (or as close as the libraries allow). When a
new stochastic dependency is added (torch, jax, ...), seed it here, not at the
call site.
"""

from __future__ import annotations

import os
import random


def seed_everything(seed: int, *, deterministic: bool = True) -> int:
    """Seed all known RNGs and return the seed (for logging into the vault node).

    Args:
        seed: The integer seed to apply across stdlib, NumPy, and (if installed)
            PyTorch.
        deterministic: When True, also flips library flags that trade speed for
            reproducibility (e.g. cuDNN determinism).

    Returns:
        The seed, so callers can record it alongside metrics.
    """
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)

    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:  # NumPy is a core dep, but stay defensive.
        pass

    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        if deterministic:
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    except ImportError:
        pass

    return seed

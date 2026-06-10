"""HELM Lite downloader + parser for the APT evidential substrate.

Entry point:
    from prudent_ai.substrate.helm_lite import seed
    report = seed()                      # full download, all models
    report = seed(limit=20)              # first 20 runs (for testing)
    report = seed(db_path="custom.db")   # custom DB path

OOP classes for custom pipelines:
    from prudent_ai.substrate.helm_lite import (
        HelmLiteClient,   # HTTP client
        HelmLiteParser,   # raw JSON → domain objects
        HelmLiteSeeder,   # orchestration → DB
    )
    from prudent_ai.substrate.helm_lite.models import (
        RunDirectory, StatEntry, ParsedRun, ModelRuns, SeedReport
    )
"""

from .client import HelmLiteClient
from .parser import HelmLiteParser
from .seeder import HelmLiteSeeder, seed

__all__ = [
    "HelmLiteClient",
    "HelmLiteParser",
    "HelmLiteSeeder",
    "seed",
]

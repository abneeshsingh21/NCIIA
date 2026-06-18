"""
OSINT Sources Package
"""

from nciia.ingestion.sources.base import (
    BaseSource,
    SourceConfig,
    SourceResult,
    SourceStatus,
)
from nciia.ingestion.sources.web_search import WebSearchSource
from nciia.ingestion.sources.paste_sites import PasteSiteSource
from nciia.ingestion.sources.domain import DomainSource

__all__ = [
    "BaseSource",
    "SourceConfig",
    "SourceResult",
    "SourceStatus",
    "WebSearchSource",
    "PasteSiteSource",
    "DomainSource",
]

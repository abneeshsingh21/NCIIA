"""
Base OSINT Source Adapter

Abstract base class for all OSINT data sources.
Each source adapter handles connection, rate limiting, and data extraction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Optional
from uuid import UUID, uuid4

import httpx
import structlog

from nciia.models import Signal, SignalType

logger = structlog.get_logger(__name__)


class SourceStatus(str, Enum):
    """Status of an OSINT source."""
    IDLE = "idle"
    RUNNING = "running"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class SourceConfig:
    """Configuration for an OSINT source."""
    
    name: str
    source_type: str
    enabled: bool = True
    check_interval_seconds: int = 300
    rate_limit_per_minute: int = 10
    request_timeout: int = 30
    max_retries: int = 3
    respect_robots_txt: bool = True
    user_agent: str = "N-CIIA OSINT Collector/0.1.0 (Research)"
    custom_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class SourceResult:
    """Result from an OSINT source query."""
    
    id: UUID = field(default_factory=uuid4)
    source_name: str = ""
    content: str = ""
    url: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    content_hash: Optional[str] = None
    is_new: bool = True  # False if duplicate detected


class BaseSource(ABC):
    """
    Abstract base class for OSINT sources.
    
    All OSINT sources must implement this interface.
    """
    
    def __init__(self, config: SourceConfig):
        self.config = config
        self.status = SourceStatus.IDLE
        self.last_check: Optional[datetime] = None
        self.error_count: int = 0
        self.last_error: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def is_enabled(self) -> bool:
        return self.config.enabled and self.status != SourceStatus.DISABLED
    
    async def initialize(self) -> None:
        """Initialize the source (create HTTP client, etc.)."""
        self._client = httpx.AsyncClient(
            timeout=self.config.request_timeout,
            headers={
                "User-Agent": self.config.user_agent,
                **self.config.custom_headers,
            },
            follow_redirects=True,
        )
        logger.info("source_initialized", source=self.name)
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("source_cleanup", source=self.name)
    
    @abstractmethod
    async def search(self, query: str) -> AsyncIterator[SourceResult]:
        """
        Search the source for matching content.
        
        Args:
            query: Search query (username, email, keyword, etc.)
            
        Yields:
            SourceResult objects for each match found
        """
        pass
    
    @abstractmethod
    async def check_updates(self) -> AsyncIterator[SourceResult]:
        """
        Check for new content since last check (for monitoring).
        
        Yields:
            SourceResult objects for new content
        """
        pass
    
    async def fetch_url(self, url: str) -> Optional[str]:
        """Fetch content from a URL with error handling."""
        if not self._client:
            await self.initialize()
        
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            self.error_count = 0
            return response.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                self.status = SourceStatus.RATE_LIMITED
                logger.warning("rate_limited", source=self.name, url=url)
            else:
                self._record_error(f"HTTP {e.response.status_code}: {str(e)}")
            return None
        except httpx.RequestError as e:
            self._record_error(str(e))
            return None
    
    def _record_error(self, error: str) -> None:
        """Record an error occurrence."""
        self.error_count += 1
        self.last_error = error
        self.status = SourceStatus.ERROR
        logger.error("source_error", source=self.name, error=error, count=self.error_count)
    
    def to_signal(self, result: SourceResult) -> Signal:
        """Convert a SourceResult to a Signal."""
        return Signal(
            type=self._get_signal_type(),
            source_url=result.url,
            source_name=self.name,
            raw_content=result.content,
            metadata=result.metadata,
            content_timestamp=result.timestamp,
        )
    
    @abstractmethod
    def _get_signal_type(self) -> SignalType:
        """Return the SignalType for this source."""
        pass

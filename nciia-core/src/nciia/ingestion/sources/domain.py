"""
Domain WHOIS OSINT Source

Monitors WHOIS records for domain changes.
"""

from __future__ import annotations

from datetime import datetime
from typing import AsyncIterator, Optional

import structlog

from nciia.ingestion.sources.base import BaseSource, SourceConfig, SourceResult
from nciia.models import SignalType

logger = structlog.get_logger(__name__)


class DomainSource(BaseSource):
    """
    Domain WHOIS monitoring source.
    
    Tracks WHOIS record changes for specified domains.
    """
    
    def __init__(self, config: Optional[SourceConfig] = None):
        if config is None:
            config = SourceConfig(
                name="DomainWHOIS",
                source_type="domain_records",
                check_interval_seconds=3600,  # Hourly
                rate_limit_per_minute=2,
            )
        super().__init__(config)
        
        self._monitored_domains: dict[str, dict] = {}  # domain -> last_record
    
    def add_domain(self, domain: str) -> None:
        """Add a domain to monitor."""
        domain = domain.lower().strip()
        if domain not in self._monitored_domains:
            self._monitored_domains[domain] = {}
            logger.info("domain_added", source=self.name, domain=domain)
    
    async def search(self, query: str) -> AsyncIterator[SourceResult]:
        """Search for domain information."""
        domain = query.lower().strip()
        
        # Use public WHOIS API
        whois_url = f"https://whois.arin.net/rest/net/n/{domain}"
        
        # For now, use a simpler approach - just record the query
        yield SourceResult(
            source_name=self.name,
            content=f"Domain lookup requested: {domain}",
            url=f"https://who.is/whois/{domain}",
            metadata={"domain": domain, "type": "whois_lookup"},
        )
    
    async def check_updates(self) -> AsyncIterator[SourceResult]:
        """Check monitored domains for changes."""
        for domain in list(self._monitored_domains.keys()):
            async for result in self.search(domain):
                yield result
        
        self.last_check = datetime.utcnow()
    
    def _get_signal_type(self) -> SignalType:
        return SignalType.DOMAIN_RECORD

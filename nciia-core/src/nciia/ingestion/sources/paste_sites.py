"""
Paste Site OSINT Source

Monitors public paste sites for relevant content.
Focuses on detecting leaked data, credentials, and threat intel.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import AsyncIterator, Optional

import structlog

from nciia.ingestion.sources.base import BaseSource, SourceConfig, SourceResult
from nciia.models import SignalType

logger = structlog.get_logger(__name__)


class PasteSiteSource(BaseSource):
    """
    Paste site monitoring source.
    
    Monitors public paste sites for content matching
    specified patterns (emails, usernames, domains, etc.)
    """
    
    # Public paste site archive APIs
    PASTE_SOURCES = [
        {
            "name": "Pastebin",
            "archive_url": "https://pastebin.com/archive",
            "raw_url_template": "https://pastebin.com/raw/{paste_id}",
            "id_pattern": r'href="/([a-zA-Z0-9]{8})"',
        },
    ]
    
    def __init__(self, config: Optional[SourceConfig] = None):
        if config is None:
            config = SourceConfig(
                name="PasteSites",
                source_type="paste_sites",
                check_interval_seconds=300,
                rate_limit_per_minute=5,
            )
        super().__init__(config)
        
        self._seen_paste_ids: set[str] = set()
        self._search_patterns: list[re.Pattern] = []
        self._keywords: list[str] = []
    
    def add_keyword(self, keyword: str) -> None:
        """Add a keyword to search for in pastes."""
        if keyword.lower() not in [k.lower() for k in self._keywords]:
            self._keywords.append(keyword)
            logger.info("keyword_added", source=self.name, keyword=keyword)
    
    def add_pattern(self, pattern: str) -> None:
        """Add a regex pattern to match in pastes."""
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            self._search_patterns.append(compiled)
            logger.info("pattern_added", source=self.name, pattern=pattern)
        except re.error as e:
            logger.error("invalid_pattern", pattern=pattern, error=str(e))
    
    async def search(self, query: str) -> AsyncIterator[SourceResult]:
        """
        Search paste sites for matching content.
        
        Due to rate limits, this fetches recent pastes and
        filters locally rather than using search APIs.
        """
        # Add query as keyword for this search
        temp_keywords = self._keywords + [query]
        
        for source in self.PASTE_SOURCES:
            async for result in self._check_source(source, temp_keywords):
                yield result
    
    async def check_updates(self) -> AsyncIterator[SourceResult]:
        """Check for new pastes matching our patterns."""
        for source in self.PASTE_SOURCES:
            async for result in self._check_source(source, self._keywords):
                yield result
    
    async def _check_source(
        self,
        source: dict,
        keywords: list[str]
    ) -> AsyncIterator[SourceResult]:
        """Check a specific paste source for matching content."""
        archive_html = await self.fetch_url(source["archive_url"])
        if not archive_html:
            return
        
        # Extract paste IDs from archive
        paste_ids = re.findall(source["id_pattern"], archive_html)
        new_ids = [pid for pid in paste_ids if pid not in self._seen_paste_ids]
        
        logger.info("checking_pastes", source=source["name"], new_count=len(new_ids))
        
        for paste_id in new_ids[:20]:  # Limit to prevent overwhelming
            self._seen_paste_ids.add(paste_id)
            
            # Fetch paste content
            raw_url = source["raw_url_template"].format(paste_id=paste_id)
            content = await self.fetch_url(raw_url)
            
            if not content:
                continue
            
            # Check for keyword matches
            matches = self._find_matches(content, keywords)
            
            if matches:
                yield SourceResult(
                    source_name=f"{self.name}:{source['name']}",
                    content=content[:5000],  # Limit content size
                    url=f"https://pastebin.com/{paste_id}",
                    metadata={
                        "paste_id": paste_id,
                        "matches": matches,
                        "content_length": len(content),
                    },
                    is_new=True,
                )
        
        self.last_check = datetime.utcnow()
    
    def _find_matches(self, content: str, keywords: list[str]) -> list[dict]:
        """Find keyword and pattern matches in content."""
        matches = []
        content_lower = content.lower()
        
        # Check keywords
        for keyword in keywords:
            if keyword.lower() in content_lower:
                # Find context around match
                idx = content_lower.find(keyword.lower())
                context_start = max(0, idx - 50)
                context_end = min(len(content), idx + len(keyword) + 50)
                context = content[context_start:context_end]
                
                matches.append({
                    "type": "keyword",
                    "value": keyword,
                    "context": context,
                })
        
        # Check regex patterns
        for pattern in self._search_patterns:
            for match in pattern.finditer(content):
                matches.append({
                    "type": "pattern",
                    "value": match.group(),
                    "pattern": pattern.pattern,
                })
        
        return matches
    
    def _get_signal_type(self) -> SignalType:
        return SignalType.PASTE_SITE

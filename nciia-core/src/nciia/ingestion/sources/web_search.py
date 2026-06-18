"""
Web Search OSINT Source

Monitors search engine results for specified queries.
Uses public search APIs and respects rate limits.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, AsyncIterator, Optional
from urllib.parse import quote_plus, urljoin

import structlog

from nciia.ingestion.sources.base import BaseSource, SourceConfig, SourceResult
from nciia.models import SignalType

logger = structlog.get_logger(__name__)


class WebSearchSource(BaseSource):
    """
    Web search monitoring source.
    
    Monitors search results for specified queries and detects
    new pages mentioning the target.
    """
    
    def __init__(self, config: Optional[SourceConfig] = None):
        if config is None:
            config = SourceConfig(
                name="WebSearch",
                source_type="web_search",
                check_interval_seconds=600,
                rate_limit_per_minute=5,
            )
        super().__init__(config)
        
        # Track seen URLs to detect new results
        self._seen_urls: set[str] = set()
        self._active_queries: list[str] = []
    
    def add_query(self, query: str) -> None:
        """Add a query to monitor."""
        if query not in self._active_queries:
            self._active_queries.append(query)
            logger.info("query_added", source=self.name, query=query)
    
    def remove_query(self, query: str) -> None:
        """Remove a query from monitoring."""
        if query in self._active_queries:
            self._active_queries.remove(query)
    
    async def search(self, query: str) -> AsyncIterator[SourceResult]:
        """
        Search for a query and yield results.
        
        Note: This uses DuckDuckGo HTML search as it doesn't require API keys.
        For production, consider using official APIs.
        """
        encoded_query = quote_plus(query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        
        html = await self.fetch_url(search_url)
        if not html:
            return
        
        # Parse results from DuckDuckGo HTML
        results = self._parse_ddg_results(html, query)
        
        for result in results:
            is_new = result.url not in self._seen_urls
            if result.url:
                self._seen_urls.add(result.url)
            result.is_new = is_new
            yield result
        
        self.last_check = datetime.utcnow()
    
    async def check_updates(self) -> AsyncIterator[SourceResult]:
        """Check all active queries for new results."""
        for query in self._active_queries:
            async for result in self.search(query):
                if result.is_new:
                    yield result
    
    def _parse_ddg_results(self, html: str, query: str) -> list[SourceResult]:
        """Parse DuckDuckGo HTML results."""
        results = []
        
        # Simple regex parsing for result links
        # Pattern matches DuckDuckGo result format
        link_pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
        snippet_pattern = r'<a[^>]*class="result__snippet"[^>]*>([^<]+)</a>'
        
        links = re.findall(link_pattern, html, re.IGNORECASE)
        snippets = re.findall(snippet_pattern, html, re.IGNORECASE)
        
        for i, (url, title) in enumerate(links[:10]):  # Limit to 10 results
            snippet = snippets[i] if i < len(snippets) else ""
            
            # Clean up HTML entities
            title = self._clean_html(title)
            snippet = self._clean_html(snippet)
            
            results.append(SourceResult(
                source_name=self.name,
                content=f"{title}\n\n{snippet}",
                url=url,
                metadata={
                    "query": query,
                    "title": title,
                    "position": i + 1,
                },
            ))
        
        logger.info("search_complete", source=self.name, query=query, results=len(results))
        return results
    
    @staticmethod
    def _clean_html(text: str) -> str:
        """Clean HTML entities from text."""
        replacements = {
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"',
            "&#39;": "'",
            "&nbsp;": " ",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text.strip()
    
    def _get_signal_type(self) -> SignalType:
        return SignalType.WEB_CONTENT

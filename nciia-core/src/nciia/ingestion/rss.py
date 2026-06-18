
import asyncio
import feedparser
from datetime import datetime
from typing import List, Dict
from nciia.utils import get_logger

logger = get_logger(__name__)

RSS_FEEDS = {
    "TheHackerNews": "https://feeds.feedburner.com/TheHackersNews",
    "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
    "CISA Alerts": "https://www.cisa.gov/cybersecurity-advisories/all.xml"
}

class RSSCollector:
    """
    Real-time RSS Ingestor for Cyber News.
    fetches external intelligence to power the dashboard ticker.
    """
    
    def __init__(self):
        self._cache: List[Dict] = []
        self._last_fetch = None
        
    async def fetch_headlines(self) -> List[Dict]:
        """Fetch and parse headlines from configured feeds."""
        # Simple caching strategy: fetch at most once every 5 minutes
        if self._last_fetch and (datetime.now() - self._last_fetch).seconds < 300:
            return self._cache
            
        headlines = []
        logger.info("rss_fetch_started", sources=list(RSS_FEEDS.keys()))
        
        for source, url in RSS_FEEDS.items():
            try:
                # feedparser is synchronous, run in executor
                feed = await asyncio.to_thread(feedparser.parse, url)
                
                for entry in feed.entries[:5]: # Top 5 from each
                    headlines.append({
                        "source": source,
                        "title": entry.title,
                        "link": entry.link,
                        "published": entry.get("published", datetime.now().isoformat()),
                        "summary": entry.get("summary", "")[:200]
                    })
            except Exception as e:
                logger.error("rss_fetch_error", source=source, error=str(e))
                
        # Sort by latest (heuristic)
        self._cache = headlines
        self._last_fetch = datetime.now()
        logger.info("rss_fetch_complete", count=len(headlines))
        return headlines

_rss = RSSCollector()

def get_rss_collector():
    return _rss

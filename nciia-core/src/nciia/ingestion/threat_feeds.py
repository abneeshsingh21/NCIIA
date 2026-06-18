"""
Real-Time Threat Intelligence Feeds

Integrates with free threat intelligence APIs:
- Abuse.ch URLhaus (Malicious URLs)
- Abuse.ch ThreatFox (IOCs)
- AbuseIPDB (Malicious IPs)
"""

import asyncio
import httpx
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from nciia.utils import get_logger

logger = get_logger(__name__)


class ThreatType(Enum):
    MALICIOUS_URL = "malicious_url"
    MALWARE_HASH = "malware_hash"
    C2_SERVER = "c2_server"
    PHISHING = "phishing"
    BOTNET = "botnet"
    MALICIOUS_IP = "malicious_ip"


class ThreatSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ThreatIndicator:
    """Represents a single threat indicator from external feeds."""
    id: str
    type: ThreatType
    value: str  # The IOC value (URL, IP, hash, etc.)
    source: str
    severity: ThreatSeverity
    description: str
    first_seen: datetime
    last_seen: datetime
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_blocked: bool = False
    

class ThreatFeedCollector:
    """
    Collects real-time threat intelligence from multiple free sources.
    """
    
    URLHAUS_API = "https://urlhaus-api.abuse.ch/v1"
    THREATFOX_API = "https://threatfox-api.abuse.ch/api/v1"
    
    def __init__(self):
        self._cache: Dict[str, List[ThreatIndicator]] = {}
        self._last_fetch: Dict[str, datetime] = {}
        self._blocked_iocs: set = set()  # User-blocked IOCs
        self._client = httpx.AsyncClient(timeout=30.0)
        self._cache_ttl = 300  # 5 minutes
        
    async def get_recent_threats(self, limit: int = 50) -> List[ThreatIndicator]:
        """Get recent threats from all sources."""
        threats = []
        
        # Fetch from each source
        urlhaus = await self._fetch_urlhaus_recent(limit // 2)
        threatfox = await self._fetch_threatfox_recent(limit // 2)
        
        threats.extend(urlhaus)
        threats.extend(threatfox)
        
        # Sort by last_seen (most recent first)
        threats.sort(key=lambda t: t.last_seen, reverse=True)
        
        return threats[:limit]
    
    async def _fetch_urlhaus_recent(self, limit: int = 25) -> List[ThreatIndicator]:
        """Fetch recent malicious URLs from URLhaus."""
        cache_key = "urlhaus_recent"
        
        # Check cache
        if self._is_cache_valid(cache_key):
            return self._cache.get(cache_key, [])[:limit]
        
        try:
            logger.info("threat_feed_fetch", source="URLhaus")
            
            response = await self._client.post(
                f"{self.URLHAUS_API}/urls/recent/",
                data={"limit": limit}
            )
            
            if response.status_code == 200:
                data = response.json()
                threats = []
                
                for url_entry in data.get("urls", [])[:limit]:
                    threat = ThreatIndicator(
                        id=f"urlhaus_{url_entry.get('id', '')}",
                        type=ThreatType.MALICIOUS_URL,
                        value=url_entry.get("url", ""),
                        source="URLhaus",
                        severity=self._map_urlhaus_threat(url_entry.get("threat", "")),
                        description=f"{url_entry.get('threat', 'Unknown')} - {url_entry.get('url_status', 'unknown')}",
                        first_seen=self._parse_date(url_entry.get("date_added", "")),
                        last_seen=self._parse_date(url_entry.get("date_added", "")),
                        tags=url_entry.get("tags", []) if url_entry.get("tags") else [],
                        metadata={
                            "host": url_entry.get("host", ""),
                            "reporter": url_entry.get("reporter", ""),
                            "url_status": url_entry.get("url_status", ""),
                            "blacklists": url_entry.get("blacklists", {})
                        },
                        is_blocked=url_entry.get("url", "") in self._blocked_iocs
                    )
                    threats.append(threat)
                
                self._cache[cache_key] = threats
                self._last_fetch[cache_key] = datetime.now()
                logger.info("threat_feed_success", source="URLhaus", count=len(threats))
                return threats
                
        except Exception as e:
            logger.error("threat_feed_error", source="URLhaus", error=str(e))
        
        return self._cache.get(cache_key, [])[:limit]
    
    async def _fetch_threatfox_recent(self, limit: int = 25) -> List[ThreatIndicator]:
        """Fetch recent IOCs from ThreatFox."""
        cache_key = "threatfox_recent"
        
        # Check cache
        if self._is_cache_valid(cache_key):
            return self._cache.get(cache_key, [])[:limit]
        
        try:
            logger.info("threat_feed_fetch", source="ThreatFox")
            
            response = await self._client.post(
                self.THREATFOX_API,
                json={"query": "get_iocs", "days": 1}
            )
            
            if response.status_code == 200:
                data = response.json()
                threats = []
                
                if data.get("query_status") == "ok":
                    for ioc in data.get("data", [])[:limit]:
                        threat_type = self._map_threatfox_type(ioc.get("ioc_type", ""))
                        
                        threat = ThreatIndicator(
                            id=f"threatfox_{ioc.get('id', '')}",
                            type=threat_type,
                            value=ioc.get("ioc", ""),
                            source="ThreatFox",
                            severity=self._map_confidence_to_severity(ioc.get("confidence_level", 50)),
                            description=f"{ioc.get('malware', 'Unknown')} - {ioc.get('threat_type', '')}",
                            first_seen=self._parse_date(ioc.get("first_seen", "")),
                            last_seen=self._parse_date(ioc.get("last_seen", ioc.get("first_seen", ""))),
                            tags=ioc.get("tags", []) if ioc.get("tags") else [],
                            metadata={
                                "malware": ioc.get("malware", ""),
                                "malware_printable": ioc.get("malware_printable", ""),
                                "threat_type": ioc.get("threat_type", ""),
                                "confidence": ioc.get("confidence_level", 0),
                                "reporter": ioc.get("reporter", "")
                            },
                            is_blocked=ioc.get("ioc", "") in self._blocked_iocs
                        )
                        threats.append(threat)
                
                self._cache[cache_key] = threats
                self._last_fetch[cache_key] = datetime.now()
                logger.info("threat_feed_success", source="ThreatFox", count=len(threats))
                return threats
                
        except Exception as e:
            logger.error("threat_feed_error", source="ThreatFox", error=str(e))
        
        return self._cache.get(cache_key, [])[:limit]
    
    async def search_ioc(self, ioc: str) -> Optional[ThreatIndicator]:
        """Search for a specific IOC across all feeds."""
        try:
            # Try URLhaus first
            response = await self._client.post(
                f"{self.URLHAUS_API}/url/",
                data={"url": ioc}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("query_status") == "ok":
                    return ThreatIndicator(
                        id=f"urlhaus_search_{data.get('id', '')}",
                        type=ThreatType.MALICIOUS_URL,
                        value=ioc,
                        source="URLhaus",
                        severity=self._map_urlhaus_threat(data.get("threat", "")),
                        description=data.get("threat", "Malicious URL"),
                        first_seen=self._parse_date(data.get("date_added", "")),
                        last_seen=datetime.now(),
                        tags=data.get("tags", []),
                        metadata=data
                    )
                    
        except Exception as e:
            logger.error("ioc_search_error", ioc=ioc, error=str(e))
        
        return None
    
    def block_ioc(self, ioc: str) -> bool:
        """Block an IOC locally."""
        self._blocked_iocs.add(ioc)
        logger.info("ioc_blocked", ioc=ioc)
        return True
    
    def unblock_ioc(self, ioc: str) -> bool:
        """Unblock an IOC."""
        self._blocked_iocs.discard(ioc)
        logger.info("ioc_unblocked", ioc=ioc)
        return True
    
    def get_blocked_iocs(self) -> List[str]:
        """Get list of blocked IOCs."""
        return list(self._blocked_iocs)
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache is still valid."""
        if cache_key not in self._last_fetch:
            return False
        return (datetime.now() - self._last_fetch[cache_key]).seconds < self._cache_ttl
    
    def _map_urlhaus_threat(self, threat: str) -> ThreatSeverity:
        """Map URLhaus threat type to severity."""
        threat_lower = threat.lower()
        if "ransomware" in threat_lower or "c2" in threat_lower:
            return ThreatSeverity.CRITICAL
        elif "malware" in threat_lower or "trojan" in threat_lower:
            return ThreatSeverity.HIGH
        elif "phishing" in threat_lower:
            return ThreatSeverity.MEDIUM
        return ThreatSeverity.LOW
    
    def _map_threatfox_type(self, ioc_type: str) -> ThreatType:
        """Map ThreatFox IOC type to our ThreatType."""
        type_lower = ioc_type.lower()
        if "url" in type_lower:
            return ThreatType.MALICIOUS_URL
        elif "ip" in type_lower:
            return ThreatType.C2_SERVER
        elif "hash" in type_lower or "md5" in type_lower or "sha" in type_lower:
            return ThreatType.MALWARE_HASH
        return ThreatType.MALICIOUS_URL
    
    def _map_confidence_to_severity(self, confidence: int) -> ThreatSeverity:
        """Map confidence level to severity."""
        if confidence >= 90:
            return ThreatSeverity.CRITICAL
        elif confidence >= 70:
            return ThreatSeverity.HIGH
        elif confidence >= 50:
            return ThreatSeverity.MEDIUM
        return ThreatSeverity.LOW
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime."""
        if not date_str:
            return datetime.now()
        try:
            # Try common formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    return datetime.strptime(date_str.split(".")[0], fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return datetime.now()
    
    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()


# Global instance
_threat_collector: Optional[ThreatFeedCollector] = None


async def get_threat_collector() -> ThreatFeedCollector:
    """Get or create the global threat collector."""
    global _threat_collector
    if _threat_collector is None:
        _threat_collector = ThreatFeedCollector()
    return _threat_collector

"""
Delta Detection Engine

Detects changes in OSINT data to avoid reprocessing
and identify genuinely new intelligence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from collections import OrderedDict

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class DeltaRecord:
    """Record of previously seen content."""
    
    content_hash: str
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


class DeltaDetector:
    """
    Delta detection for identifying new vs. previously seen content.
    
    Uses content hashing and LRU cache to efficiently detect duplicates
    while maintaining reasonable memory usage.
    """
    
    def __init__(
        self,
        max_cache_size: int = 100000,
        expiry_hours: int = 168,  # 1 week
    ):
        self.max_cache_size = max_cache_size
        self.expiry_hours = expiry_hours
        
        # LRU cache for hash -> DeltaRecord
        self._cache: OrderedDict[str, DeltaRecord] = OrderedDict()
        
        # Statistics
        self.total_checked: int = 0
        self.duplicates_found: int = 0
        self.new_items: int = 0
    
    def compute_hash(self, content: str, normalize: bool = True) -> str:
        """
        Compute content hash for deduplication.
        
        Args:
            content: Raw content string
            normalize: Whether to normalize whitespace before hashing
            
        Returns:
            SHA-256 hash (first 32 chars)
        """
        if normalize:
            # Normalize whitespace for fuzzy matching
            content = " ".join(content.split())
            content = content.lower()
        
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]
    
    def is_new(self, content: str, source: str = "") -> tuple[bool, str]:
        """
        Check if content is new (not seen before).
        
        Args:
            content: Content to check
            source: Source identifier for logging
            
        Returns:
            Tuple of (is_new, content_hash)
        """
        self.total_checked += 1
        content_hash = self.compute_hash(content)
        
        # Check cache
        if content_hash in self._cache:
            record = self._cache[content_hash]
            record.last_seen = datetime.utcnow()
            record.occurrence_count += 1
            
            # Move to end (LRU update)
            self._cache.move_to_end(content_hash)
            
            self.duplicates_found += 1
            logger.debug("duplicate_detected", hash=content_hash, count=record.occurrence_count)
            return False, content_hash
        
        # New content
        self._add_to_cache(content_hash)
        self.new_items += 1
        logger.debug("new_content", hash=content_hash, source=source)
        return True, content_hash
    
    def is_new_by_hash(self, content_hash: str) -> bool:
        """Check if a hash has been seen before."""
        return content_hash not in self._cache
    
    def _add_to_cache(self, content_hash: str) -> None:
        """Add a new hash to the cache."""
        now = datetime.utcnow()
        
        # Evict old entries if cache is full
        while len(self._cache) >= self.max_cache_size:
            self._cache.popitem(last=False)  # Remove oldest
        
        self._cache[content_hash] = DeltaRecord(
            content_hash=content_hash,
            first_seen=now,
            last_seen=now,
        )
    
    def cleanup_expired(self) -> int:
        """Remove expired entries from cache."""
        cutoff = datetime.utcnow() - timedelta(hours=self.expiry_hours)
        expired = []
        
        for hash_key, record in self._cache.items():
            if record.last_seen < cutoff:
                expired.append(hash_key)
        
        for hash_key in expired:
            del self._cache[hash_key]
        
        if expired:
            logger.info("cache_cleanup", expired_count=len(expired))
        
        return len(expired)
    
    def get_stats(self) -> dict[str, Any]:
        """Get detection statistics."""
        return {
            "total_checked": self.total_checked,
            "duplicates_found": self.duplicates_found,
            "new_items": self.new_items,
            "cache_size": len(self._cache),
            "max_cache_size": self.max_cache_size,
            "duplicate_rate": (
                self.duplicates_found / self.total_checked
                if self.total_checked > 0 else 0
            ),
        }
    
    def save_state(self) -> dict[str, Any]:
        """Export cache state for persistence."""
        return {
            "cache": {
                k: {
                    "content_hash": v.content_hash,
                    "first_seen": v.first_seen.isoformat(),
                    "last_seen": v.last_seen.isoformat(),
                    "occurrence_count": v.occurrence_count,
                }
                for k, v in self._cache.items()
            },
            "stats": self.get_stats(),
        }
    
    def load_state(self, state: dict[str, Any]) -> None:
        """Load cache state from persistence."""
        self._cache.clear()
        
        for hash_key, record_data in state.get("cache", {}).items():
            self._cache[hash_key] = DeltaRecord(
                content_hash=record_data["content_hash"],
                first_seen=datetime.fromisoformat(record_data["first_seen"]),
                last_seen=datetime.fromisoformat(record_data["last_seen"]),
                occurrence_count=record_data.get("occurrence_count", 1),
            )
        
        logger.info("state_loaded", records=len(self._cache))


class SimilarityDetector:
    """
    Detects similar (not identical) content using locality-sensitive hashing.
    
    Useful for detecting paraphrased or slightly modified content.
    """
    
    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        self._fingerprints: dict[str, list[int]] = {}
    
    def compute_shingles(self, text: str, k: int = 3) -> set[str]:
        """Compute k-shingles (character n-grams) of text."""
        text = " ".join(text.lower().split())
        if len(text) < k:
            return {text}
        return {text[i:i+k] for i in range(len(text) - k + 1)}
    
    def compute_minhash(self, shingles: set[str], num_hashes: int = 100) -> list[int]:
        """Compute MinHash signature for a set of shingles."""
        if not shingles:
            return [0] * num_hashes
        
        signature = []
        for seed in range(num_hashes):
            min_hash = float('inf')
            for shingle in shingles:
                h = hash((shingle, seed)) & 0xFFFFFFFF
                min_hash = min(min_hash, h)
            signature.append(min_hash)
        
        return signature
    
    def estimate_similarity(self, sig1: list[int], sig2: list[int]) -> float:
        """Estimate Jaccard similarity from MinHash signatures."""
        if len(sig1) != len(sig2):
            return 0.0
        
        matches = sum(1 for a, b in zip(sig1, sig2) if a == b)
        return matches / len(sig1)
    
    def find_similar(self, content: str, content_id: str) -> list[tuple[str, float]]:
        """Find content similar to the given text."""
        shingles = self.compute_shingles(content)
        signature = self.compute_minhash(shingles)
        
        similar = []
        for other_id, other_sig in self._fingerprints.items():
            if other_id != content_id:
                sim = self.estimate_similarity(signature, other_sig)
                if sim >= self.threshold:
                    similar.append((other_id, sim))
        
        # Store this content's fingerprint
        self._fingerprints[content_id] = signature
        
        return sorted(similar, key=lambda x: x[1], reverse=True)

"""
Alias Inference Engine

Infers potential aliases and alternative identities
from observed signals and patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import structlog

from nciia.models import Entity, EntityType, Alias, Confidence

logger = structlog.get_logger(__name__)


@dataclass
class AliasMatch:
    """A potential alias relationship."""
    
    entity1: Entity
    entity2: Entity
    match_type: str  # email_username, similar_handle, shared_content, etc.
    confidence: float
    evidence: list[str] = field(default_factory=list)


class AliasInferenceEngine:
    """
    Infers alias relationships between entities.
    
    Uses multiple strategies:
    - Email-username correlation
    - Handle similarity
    - Shared content/phrases
    - Temporal correlation
    """
    
    def __init__(self, min_confidence: float = 0.6):
        self.min_confidence = min_confidence
        self._known_aliases: dict[str, list[AliasMatch]] = {}
    
    def infer_aliases(
        self,
        primary: Entity,
        candidates: list[Entity],
    ) -> list[AliasMatch]:
        """
        Find potential aliases for an entity among candidates.
        
        Args:
            primary: The primary entity to find aliases for
            candidates: List of candidate entities to check
            
        Returns:
            List of potential alias matches
        """
        matches = []
        
        for candidate in candidates:
            if candidate.id == primary.id:
                continue
            
            match = self._check_alias(primary, candidate)
            if match and match.confidence >= self.min_confidence:
                matches.append(match)
        
        # Sort by confidence
        matches.sort(key=lambda m: m.confidence, reverse=True)
        
        logger.info(
            "aliases_inferred",
            primary=primary.value,
            matches_found=len(matches),
        )
        
        return matches
    
    def _check_alias(self, e1: Entity, e2: Entity) -> Optional[AliasMatch]:
        """Check if two entities might be aliases."""
        confidence = 0.0
        evidence = []
        match_type = "unknown"
        
        # Same type - check similarity
        if e1.type == e2.type:
            sim = self._string_similarity(e1.value, e2.value)
            if sim >= 0.7:
                confidence = sim * 0.8
                match_type = "similar_value"
                evidence.append(f"String similarity: {sim:.2f}")
        
        # Email -> Username inference
        if e1.type == EntityType.EMAIL and e2.type == EntityType.USERNAME:
            email_username = e1.value.split("@")[0].lower()
            if e2.value.lower() in email_username or email_username in e2.value.lower():
                confidence = 0.85
                match_type = "email_username"
                evidence.append(f"Username '{e2.value}' found in email")
        
        # Username -> Email inference
        if e1.type == EntityType.USERNAME and e2.type == EntityType.EMAIL:
            email_username = e2.value.split("@")[0].lower()
            if e1.value.lower() in email_username or email_username in e1.value.lower():
                confidence = 0.85
                match_type = "username_email"
                evidence.append(f"Username found in email local part")
        
        # Check for numeric suffix patterns (user123 -> user)
        if e1.type == EntityType.USERNAME and e2.type == EntityType.USERNAME:
            base1 = re.sub(r'\d+$', '', e1.value.lower())
            base2 = re.sub(r'\d+$', '', e2.value.lower())
            if base1 and base2 and base1 == base2:
                confidence = 0.75
                match_type = "username_variant"
                evidence.append("Same base username with numeric suffix")
        
        # Check underscore/dot variations
        if e1.type == EntityType.USERNAME and e2.type == EntityType.USERNAME:
            clean1 = re.sub(r'[._-]', '', e1.value.lower())
            clean2 = re.sub(r'[._-]', '', e2.value.lower())
            if clean1 == clean2 and e1.value != e2.value:
                confidence = 0.9
                match_type = "separator_variant"
                evidence.append("Same username with different separators")
        
        if confidence >= self.min_confidence:
            return AliasMatch(
                entity1=e1,
                entity2=e2,
                match_type=match_type,
                confidence=confidence,
                evidence=evidence,
            )
        
        return None
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate normalized string similarity (Levenshtein-based)."""
        s1, s2 = s1.lower(), s2.lower()
        
        if s1 == s2:
            return 1.0
        
        if not s1 or not s2:
            return 0.0
        
        # Simple Levenshtein distance
        len1, len2 = len(s1), len(s2)
        
        if len1 < len2:
            s1, s2 = s2, s1
            len1, len2 = len2, len1
        
        previous = list(range(len2 + 1))
        
        for i, c1 in enumerate(s1):
            current = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous[j + 1] + 1
                deletions = current[j] + 1
                substitutions = previous[j] + (c1 != c2)
                current.append(min(insertions, deletions, substitutions))
            previous = current
        
        distance = previous[-1]
        max_len = max(len1, len2)
        
        return 1.0 - (distance / max_len)
    
    def to_alias_model(self, match: AliasMatch) -> Alias:
        """Convert an AliasMatch to an Alias model."""
        return Alias(
            primary_entity_id=match.entity1.id,
            alias_entity_id=match.entity2.id,
            confidence=Confidence(
                score=match.confidence,
                reasoning=match.evidence,
            ),
            evidence_type=match.match_type,
        )

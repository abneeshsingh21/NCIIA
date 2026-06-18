"""
Persona Reconstructor

Main engine for digital persona reconstruction from seed identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

import structlog

from nciia.models import Persona, Entity, EntityType, Confidence, Signal
from nciia.persona.seed import SeedHandler, SeedInfo
from nciia.persona.inference import AliasInferenceEngine
from nciia.persona.correlation import PlatformCorrelator, PlatformProfile
from nciia.persona.timeline import TimelineReconstructor
from nciia.ingestion import get_collector
from nciia.db import get_database

logger = structlog.get_logger(__name__)


@dataclass
class ReconstructionResult:
    """Result of persona reconstruction."""
    
    persona: Persona
    entities_found: int = 0
    aliases_found: int = 0
    platforms_detected: list[str] = field(default_factory=list)
    signals_processed: int = 0
    confidence: float = 0.0
    duration_seconds: float = 0.0


class PersonaReconstructor:
    """
    Main persona reconstruction engine.
    
    Takes a seed identifier and reconstructs a digital persona by:
    1. Processing and normalizing the seed
    2. Searching OSINT sources for related content
    3. Extracting entities and inferring aliases
    4. Correlating platform presence
    5. Building activity timeline
    6. Scoring confidence
    """
    
    def __init__(self):
        self.seed_handler = SeedHandler()
        self.alias_engine = AliasInferenceEngine()
        self.correlator = PlatformCorrelator()
    
    async def reconstruct(
        self,
        seed_value: str,
        seed_type: Optional[EntityType] = None,
        case_id: Optional[UUID] = None,
        deep_search: bool = False,
    ) -> ReconstructionResult:
        """
        Reconstruct a digital persona from a seed.
        
        Args:
            seed_value: The seed identifier
            seed_type: Optional type hint
            case_id: Optional case to associate
            deep_search: Whether to do deep OSINT search
            
        Returns:
            ReconstructionResult with the persona
        """
        start_time = datetime.utcnow()
        
        logger.info(
            "reconstruction_started",
            seed_value=seed_value,
            seed_type=seed_type,
        )
        
        # Process seed
        seed_info = self.seed_handler.process(seed_value, seed_type)
        
        # Create initial persona
        persona = Persona(
            case_id=case_id,
            primary_identifier=seed_info.normalized_value,
            identifier_type=seed_info.seed_type,
            first_activity=datetime.utcnow(),
            last_activity=datetime.utcnow(),
        )
        
        # Create primary entity
        primary_entity = Entity(
            type=seed_info.seed_type,
            value=seed_info.normalized_value,
            original_value=seed_info.original_value,
            confidence=Confidence(score=1.0, reasoning=["Primary seed input"]),
        )
        persona.add_entity(primary_entity)
        
        # Search OSINT sources
        signals = await self._search_osint(seed_info)
        
        # Build timeline
        timeline = TimelineReconstructor()
        for signal in signals:
            timeline.add_signal(signal)
            persona.add_signal(signal.id)
        
        # Extract entities from signals
        extracted_entities = self._extract_entities(signals)
        for entity in extracted_entities:
            persona.add_entity(entity)
        
        # Infer aliases
        all_entities = persona.entities
        aliases = self.alias_engine.infer_aliases(primary_entity, all_entities)
        for alias_match in aliases:
            persona.aliases.append(
                self.alias_engine.to_alias_model(alias_match)
            )
        
        # Detect platform presence
        platforms = self._detect_platforms(signals, seed_info)
        persona.platforms_detected = list(set(p.platform for p in platforms))
        
        # Calculate confidence
        confidence = self._calculate_confidence(persona, signals)
        persona.overall_confidence = Confidence(
            score=confidence,
            reasoning=self._build_confidence_reasoning(persona, signals),
        )
        
        # Save to database
        db = await get_database()
        await db.insert_persona(persona.model_dump())
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(
            "reconstruction_complete",
            persona_id=str(persona.id),
            entities=persona.entity_count,
            aliases=persona.alias_count,
            platforms=len(persona.platforms_detected),
            duration=duration,
        )
        
        return ReconstructionResult(
            persona=persona,
            entities_found=persona.entity_count,
            aliases_found=persona.alias_count,
            platforms_detected=persona.platforms_detected,
            signals_processed=len(signals),
            confidence=confidence,
            duration_seconds=duration,
        )
    
    async def _search_osint(self, seed_info: SeedInfo) -> list[Signal]:
        """Search OSINT sources for the seed."""
        signals = []
        
        try:
            collector = await get_collector()
            
            # Search for primary value
            found = await collector.search(seed_info.normalized_value)
            signals.extend(found)
            
            # Search variations
            for variation in seed_info.username_variations[:5]:
                if variation != seed_info.normalized_value:
                    found = await collector.search(variation)
                    signals.extend(found)
            
        except Exception as e:
            logger.error("osint_search_error", error=str(e))
        
        return signals
    
    def _extract_entities(self, signals: list[Signal]) -> list[Entity]:
        """Extract entities from signal content."""
        entities = []
        
        for signal in signals:
            content = signal.raw_content
            
            # Extract emails
            import re
            emails = re.findall(
                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                content
            )
            for email in emails[:5]:
                entities.append(Entity(
                    type=EntityType.EMAIL,
                    value=email.lower(),
                    original_value=email,
                    confidence=Confidence(score=0.7, reasoning=["Extracted from signal"]),
                    source_signals=[signal.id],
                ))
            
            # Extract usernames (@ mentions)
            mentions = re.findall(r'@([a-zA-Z0-9_]+)', content)
            for mention in mentions[:5]:
                entities.append(Entity(
                    type=EntityType.USERNAME,
                    value=mention.lower(),
                    original_value=mention,
                    confidence=Confidence(score=0.6, reasoning=["Mention in signal"]),
                    source_signals=[signal.id],
                ))
        
        return entities
    
    def _detect_platforms(
        self,
        signals: list[Signal],
        seed_info: SeedInfo,
    ) -> list[PlatformProfile]:
        """Detect platform presence from signals."""
        profiles = []
        
        for signal in signals:
            # Extract from URLs in content
            found = self.correlator.extract_platforms_from_text(signal.raw_content)
            profiles.extend(found)
            
            # Extract from signal URL
            if signal.source_url:
                found = self.correlator.extract_platforms_from_url(signal.source_url)
                profiles.extend(found)
        
        # Generate potential profiles from username
        if seed_info.seed_type == EntityType.USERNAME:
            potential = self.correlator.generate_platform_urls(seed_info.normalized_value)
            profiles.extend(potential)
        
        return profiles
    
    def _calculate_confidence(
        self,
        persona: Persona,
        signals: list[Signal],
    ) -> float:
        """Calculate overall persona confidence."""
        score = 0.3  # Base score
        
        # Entity count contribution
        if persona.entity_count >= 3:
            score += 0.15
        if persona.entity_count >= 5:
            score += 0.1
        
        # Alias confirmation
        if persona.alias_count >= 1:
            score += 0.15
        
        # Platform diversity
        if len(persona.platforms_detected) >= 2:
            score += 0.1
        if len(persona.platforms_detected) >= 4:
            score += 0.1
        
        # Signal volume
        if len(signals) >= 5:
            score += 0.1
        
        return min(0.95, score)
    
    def _build_confidence_reasoning(
        self,
        persona: Persona,
        signals: list[Signal],
    ) -> list[str]:
        """Build reasoning for confidence score."""
        reasons = []
        
        if persona.entity_count > 1:
            reasons.append(f"{persona.entity_count} entities found")
        
        if persona.alias_count > 0:
            reasons.append(f"{persona.alias_count} alias relationships detected")
        
        if len(persona.platforms_detected) > 0:
            reasons.append(f"Present on {len(persona.platforms_detected)} platforms")
        
        if len(signals) > 0:
            reasons.append(f"{len(signals)} signals collected")
        
        return reasons


# Global reconstructor instance
_reconstructor: Optional[PersonaReconstructor] = None


def get_reconstructor() -> PersonaReconstructor:
    """Get or create persona reconstructor."""
    global _reconstructor
    if _reconstructor is None:
        _reconstructor = PersonaReconstructor()
    return _reconstructor

"""
Escalation Detection

Detects threat escalation patterns and velocity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import structlog

from nciia.models import ThreatScore

logger = structlog.get_logger(__name__)


@dataclass
class EscalationEvent:
    """A detected escalation event."""
    
    timestamp: datetime
    previous_score: float
    new_score: float
    delta: float
    trigger: str
    severity: str  # minor, moderate, major, critical


@dataclass
class EscalationPattern:
    """Detected escalation pattern."""
    
    pattern_type: str
    description: str
    velocity: float  # Score change per day
    confidence: float
    events: list[EscalationEvent] = field(default_factory=list)


class EscalationDetector:
    """
    Detects threat escalation patterns.
    
    Monitors score changes over time to detect:
    - Rapid escalation
    - Steady increase
    - Burst patterns
    """
    
    def __init__(
        self,
        major_threshold: float = 20.0,
        critical_threshold: float = 35.0,
    ):
        self.major_threshold = major_threshold
        self.critical_threshold = critical_threshold
        
        # Score history by persona
        self._history: dict[str, list[tuple[datetime, float]]] = {}
    
    def record_score(self, persona_id: UUID, score: float) -> Optional[EscalationEvent]:
        """
        Record a new score and check for escalation.
        
        Returns EscalationEvent if escalation detected.
        """
        key = str(persona_id)
        now = datetime.utcnow()
        
        if key not in self._history:
            self._history[key] = []
        
        history = self._history[key]
        
        # Check for escalation against last score
        event = None
        if history:
            last_time, last_score = history[-1]
            delta = score - last_score
            
            if delta >= self.critical_threshold:
                event = EscalationEvent(
                    timestamp=now,
                    previous_score=last_score,
                    new_score=score,
                    delta=delta,
                    trigger="critical_jump",
                    severity="critical",
                )
                logger.warning(
                    "critical_escalation",
                    persona_id=key,
                    delta=delta,
                )
            elif delta >= self.major_threshold:
                event = EscalationEvent(
                    timestamp=now,
                    previous_score=last_score,
                    new_score=score,
                    delta=delta,
                    trigger="major_increase",
                    severity="major",
                )
                logger.info(
                    "major_escalation",
                    persona_id=key,
                    delta=delta,
                )
            elif delta >= 10:
                event = EscalationEvent(
                    timestamp=now,
                    previous_score=last_score,
                    new_score=score,
                    delta=delta,
                    trigger="moderate_increase",
                    severity="moderate",
                )
        
        # Record new score
        history.append((now, score))
        
        # Trim old history (keep last 30 days)
        cutoff = now - timedelta(days=30)
        self._history[key] = [(t, s) for t, s in history if t >= cutoff]
        
        return event
    
    def analyze_pattern(self, persona_id: UUID) -> Optional[EscalationPattern]:
        """Analyze escalation pattern for a persona."""
        key = str(persona_id)
        
        if key not in self._history or len(self._history[key]) < 2:
            return None
        
        history = self._history[key]
        
        # Calculate velocity (score change per day)
        first_time, first_score = history[0]
        last_time, last_score = history[-1]
        
        days_elapsed = (last_time - first_time).total_seconds() / 86400
        if days_elapsed < 0.01:
            days_elapsed = 0.01
        
        velocity = (last_score - first_score) / days_elapsed
        
        # Determine pattern type
        if velocity >= 10:
            pattern_type = "rapid_escalation"
            description = "Threat score increasing rapidly"
        elif velocity >= 3:
            pattern_type = "steady_increase"
            description = "Consistent upward trend"
        elif velocity <= -5:
            pattern_type = "de_escalation"
            description = "Threat score decreasing"
        else:
            pattern_type = "stable"
            description = "No significant trend"
        
        return EscalationPattern(
            pattern_type=pattern_type,
            description=description,
            velocity=velocity,
            confidence=min(0.9, 0.3 + len(history) * 0.1),
        )
    
    def get_velocity(self, persona_id: UUID) -> float:
        """Get current escalation velocity."""
        pattern = self.analyze_pattern(persona_id)
        return pattern.velocity if pattern else 0.0
    
    def is_escalating(self, persona_id: UUID) -> bool:
        """Check if persona is currently escalating."""
        velocity = self.get_velocity(persona_id)
        return velocity >= 3.0


# Global detector instance
_detector: Optional[EscalationDetector] = None


def get_escalation_detector() -> EscalationDetector:
    """Get or create escalation detector."""
    global _detector
    if _detector is None:
        _detector = EscalationDetector()
    return _detector

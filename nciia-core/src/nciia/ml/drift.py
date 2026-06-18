"""
Behavioral Drift Detection

Detects changes in behavioral patterns that may indicate
account compromise or identity shifts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import structlog

from nciia.behavioral import StyleFeatures

logger = structlog.get_logger(__name__)


@dataclass
class DriftEvent:
    """A detected behavioral drift event."""
    
    timestamp: datetime
    drift_type: str  # style, temporal, vocabulary
    severity: str  # minor, moderate, major
    description: str
    confidence: float
    before_sample: Optional[str] = None
    after_sample: Optional[str] = None


@dataclass
class DriftAnalysis:
    """Complete drift analysis result."""
    
    persona_id: UUID
    baseline_established: bool
    drift_detected: bool
    overall_drift_score: float  # 0-1, higher = more drift
    events: list[DriftEvent] = field(default_factory=list)
    recommendation: str = ""


class DriftDetector:
    """
    Detects behavioral drift in personas.
    
    Monitors style, vocabulary, and temporal patterns
    for significant deviations from baseline.
    """
    
    def __init__(self, drift_threshold: float = 0.3):
        self.drift_threshold = drift_threshold
        
        # Baseline fingerprints by persona
        self._baselines: dict[str, dict[str, Any]] = {}
        
        # Recent samples for comparison
        self._recent: dict[str, list[dict]] = {}
    
    def establish_baseline(
        self,
        persona_id: UUID,
        features: StyleFeatures,
        sample_count: int = 1,
    ) -> None:
        """Establish or update baseline fingerprint."""
        key = str(persona_id)
        
        if key not in self._baselines:
            self._baselines[key] = {
                "avg_word_length": features.avg_word_length,
                "avg_sentence_length": features.avg_sentence_length,
                "vocabulary_richness": features.vocabulary_richness,
                "sample_count": sample_count,
                "established_at": datetime.utcnow(),
            }
        else:
            # Weighted update
            existing = self._baselines[key]
            n = existing["sample_count"]
            
            existing["avg_word_length"] = (
                existing["avg_word_length"] * n + features.avg_word_length
            ) / (n + 1)
            existing["avg_sentence_length"] = (
                existing["avg_sentence_length"] * n + features.avg_sentence_length
            ) / (n + 1)
            existing["vocabulary_richness"] = (
                existing["vocabulary_richness"] * n + features.vocabulary_richness
            ) / (n + 1)
            existing["sample_count"] = n + 1
    
    def analyze(
        self,
        persona_id: UUID,
        current_features: StyleFeatures,
    ) -> DriftAnalysis:
        """
        Analyze current features for drift from baseline.
        
        Returns comprehensive drift analysis.
        """
        key = str(persona_id)
        
        if key not in self._baselines:
            return DriftAnalysis(
                persona_id=persona_id,
                baseline_established=False,
                drift_detected=False,
                overall_drift_score=0.0,
                recommendation="Insufficient baseline data. Continue monitoring.",
            )
        
        baseline = self._baselines[key]
        events = []
        drift_scores = []
        
        # Check word length drift
        word_len_drift = abs(
            current_features.avg_word_length - baseline["avg_word_length"]
        ) / max(baseline["avg_word_length"], 1)
        if word_len_drift > 0.2:
            severity = "major" if word_len_drift > 0.4 else "moderate"
            events.append(DriftEvent(
                timestamp=datetime.utcnow(),
                drift_type="style",
                severity=severity,
                description=f"Average word length changed by {word_len_drift*100:.0f}%",
                confidence=0.7,
            ))
        drift_scores.append(min(1.0, word_len_drift))
        
        # Check sentence length drift
        sent_len_drift = abs(
            current_features.avg_sentence_length - baseline["avg_sentence_length"]
        ) / max(baseline["avg_sentence_length"], 1)
        if sent_len_drift > 0.25:
            severity = "major" if sent_len_drift > 0.5 else "moderate"
            events.append(DriftEvent(
                timestamp=datetime.utcnow(),
                drift_type="style",
                severity=severity,
                description=f"Sentence length changed by {sent_len_drift*100:.0f}%",
                confidence=0.65,
            ))
        drift_scores.append(min(1.0, sent_len_drift))
        
        # Check vocabulary drift
        vocab_drift = abs(
            current_features.vocabulary_richness - baseline["vocabulary_richness"]
        )
        if vocab_drift > 0.15:
            severity = "major" if vocab_drift > 0.3 else "moderate"
            events.append(DriftEvent(
                timestamp=datetime.utcnow(),
                drift_type="vocabulary",
                severity=severity,
                description=f"Vocabulary richness shifted by {vocab_drift*100:.0f}%",
                confidence=0.75,
            ))
        drift_scores.append(min(1.0, vocab_drift * 3))
        
        # Overall drift score
        overall = sum(drift_scores) / len(drift_scores) if drift_scores else 0.0
        drift_detected = overall > self.drift_threshold
        
        # Build recommendation
        if drift_detected:
            if any(e.severity == "major" for e in events):
                recommendation = (
                    "ALERT: Significant behavioral drift detected. "
                    "Consider investigating for potential account compromise or identity shift."
                )
            else:
                recommendation = (
                    "Moderate behavioral changes detected. "
                    "Monitor for continued drift patterns."
                )
        else:
            recommendation = "Behavioral patterns consistent with baseline."
        
        return DriftAnalysis(
            persona_id=persona_id,
            baseline_established=True,
            drift_detected=drift_detected,
            overall_drift_score=overall,
            events=events,
            recommendation=recommendation,
        )
    
    def get_baseline(self, persona_id: UUID) -> Optional[dict[str, Any]]:
        """Get baseline data for a persona."""
        return self._baselines.get(str(persona_id))


# Global detector
_drift_detector: Optional[DriftDetector] = None


def get_drift_detector() -> DriftDetector:
    """Get or create drift detector."""
    global _drift_detector
    if _drift_detector is None:
        _drift_detector = DriftDetector()
    return _drift_detector

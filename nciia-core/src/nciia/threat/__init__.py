"""
N-CIIA Threat Package

Threat scoring and escalation detection.
"""

from nciia.threat.scorer import ThreatScorer, ScoringRule, get_scorer
from nciia.threat.escalation import (
    EscalationDetector,
    EscalationEvent,
    EscalationPattern,
    get_escalation_detector,
)

__all__ = [
    # Scoring
    "ThreatScorer",
    "ScoringRule",
    "get_scorer",
    # Escalation
    "EscalationDetector",
    "EscalationEvent",
    "EscalationPattern",
    "get_escalation_detector",
]

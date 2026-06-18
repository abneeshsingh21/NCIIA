"""
Threat Scorer

Rule-based transparent threat scoring with full explainability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import structlog

from nciia.models import (
    ThreatScore,
    ThreatIndicator,
    RiskLevel,
    Confidence,
    Persona,
    Signal,
)

logger = structlog.get_logger(__name__)


@dataclass
class ScoringRule:
    """A single scoring rule."""
    
    name: str
    description: str
    weight: float  # 0.0 - 1.0
    category: str
    check: callable  # Function that returns (triggered: bool, evidence: list[str])


class ThreatScorer:
    """
    Rule-based threat scoring engine.
    
    Provides transparent, explainable threat assessments
    with no black-box scoring.
    """
    
    def __init__(self):
        self.rules: list[ScoringRule] = []
        self._setup_default_rules()
    
    def _setup_default_rules(self) -> None:
        """Setup default scoring rules."""
        
        # Content-based rules
        self.rules.append(ScoringRule(
            name="credential_keywords",
            description="Contains credential-related keywords",
            weight=0.3,
            category="content",
            check=self._check_credential_keywords,
        ))
        
        self.rules.append(ScoringRule(
            name="threat_language",
            description="Contains threatening or malicious language",
            weight=0.4,
            category="content",
            check=self._check_threat_language,
        ))
        
        self.rules.append(ScoringRule(
            name="financial_indicators",
            description="References to financial fraud or scams",
            weight=0.35,
            category="content",
            check=self._check_financial_indicators,
        ))
        
        # Behavioral rules
        self.rules.append(ScoringRule(
            name="high_volume_activity",
            description="Unusually high activity volume",
            weight=0.2,
            category="behavioral",
            check=self._check_high_volume,
        ))
        
        self.rules.append(ScoringRule(
            name="multi_platform",
            description="Activity across multiple platforms",
            weight=0.15,
            category="behavioral",
            check=self._check_multi_platform,
        ))
        
        # Technical rules
        self.rules.append(ScoringRule(
            name="paste_site_presence",
            description="Content found on paste sites",
            weight=0.25,
            category="technical",
            check=self._check_paste_presence,
        ))
    
    def score(
        self,
        persona: Persona,
        signals: list[Signal],
        context: Optional[dict[str, Any]] = None,
    ) -> ThreatScore:
        """
        Calculate threat score for a persona.
        
        Returns fully explainable ThreatScore.
        """
        context = context or {}
        context["persona"] = persona
        context["signals"] = signals
        
        indicators = []
        total_weight = 0.0
        triggered_weight = 0.0
        contributing_factors = {}
        
        for rule in self.rules:
            triggered, evidence = rule.check(context)
            
            indicator = ThreatIndicator(
                name=rule.name,
                description=rule.description,
                weight=rule.weight,
                detected=triggered,
                evidence=evidence,
            )
            indicators.append(indicator)
            
            total_weight += rule.weight
            if triggered:
                triggered_weight += rule.weight
                contributing_factors[rule.name] = rule.weight
        
        # Calculate score (0-100)
        if total_weight > 0:
            raw_score = (triggered_weight / total_weight) * 100
        else:
            raw_score = 0.0
        
        # Determine risk level
        risk_level = ThreatScore.calculate_risk_level(raw_score)
        
        # Build reasoning
        reasoning = []
        for indicator in indicators:
            if indicator.detected:
                reasoning.append(f"{indicator.description}: {', '.join(indicator.evidence[:3])}")
        
        # Calculate confidence based on signal volume
        signal_count = len(signals)
        if signal_count >= 10:
            conf_score = 0.85
        elif signal_count >= 5:
            conf_score = 0.7
        elif signal_count >= 2:
            conf_score = 0.5
        else:
            conf_score = 0.3
        
        return ThreatScore(
            persona_id=persona.id,
            overall_score=raw_score,
            risk_level=risk_level,
            indicators=indicators,
            reasoning=reasoning,
            contributing_factors=contributing_factors,
            confidence=Confidence(
                score=conf_score,
                reasoning=[f"Based on {signal_count} signals"],
            ),
        )
    
    # Rule check functions
    def _check_credential_keywords(self, ctx: dict) -> tuple[bool, list[str]]:
        """Check for credential-related keywords."""
        keywords = ["password", "login", "credential", "account", "hack", "leak", "dump"]
        signals = ctx.get("signals", [])
        evidence = []
        
        for signal in signals:
            content = signal.raw_content.lower()
            for kw in keywords:
                if kw in content:
                    evidence.append(f"'{kw}' found in signal")
        
        return len(evidence) > 0, evidence[:5]
    
    def _check_threat_language(self, ctx: dict) -> tuple[bool, list[str]]:
        """Check for threatening language."""
        threat_terms = ["attack", "exploit", "malware", "ransomware", "ddos", "breach"]
        signals = ctx.get("signals", [])
        evidence = []
        
        for signal in signals:
            content = signal.raw_content.lower()
            for term in threat_terms:
                if term in content:
                    evidence.append(f"Threat term '{term}' detected")
        
        return len(evidence) > 0, evidence[:5]
    
    def _check_financial_indicators(self, ctx: dict) -> tuple[bool, list[str]]:
        """Check for financial fraud indicators."""
        terms = ["wire transfer", "bitcoin", "crypto payment", "money mule", "cash out"]
        signals = ctx.get("signals", [])
        evidence = []
        
        for signal in signals:
            content = signal.raw_content.lower()
            for term in terms:
                if term in content:
                    evidence.append(f"Financial term '{term}' found")
        
        return len(evidence) > 0, evidence[:5]
    
    def _check_high_volume(self, ctx: dict) -> tuple[bool, list[str]]:
        """Check for high activity volume."""
        persona = ctx.get("persona")
        if not persona:
            return False, []
        
        if persona.activity_count >= 20:
            return True, [f"{persona.activity_count} activities recorded"]
        
        return False, []
    
    def _check_multi_platform(self, ctx: dict) -> tuple[bool, list[str]]:
        """Check for multi-platform presence."""
        persona = ctx.get("persona")
        if not persona:
            return False, []
        
        platforms = persona.platforms_detected
        if len(platforms) >= 3:
            return True, [f"Active on {len(platforms)} platforms: {', '.join(platforms[:5])}"]
        
        return False, []
    
    def _check_paste_presence(self, ctx: dict) -> tuple[bool, list[str]]:
        """Check for paste site presence."""
        signals = ctx.get("signals", [])
        paste_signals = [s for s in signals if "paste" in s.source_name.lower()]
        
        if paste_signals:
            return True, [f"{len(paste_signals)} paste site occurrences"]
        
        return False, []


# Global scorer instance
_scorer: Optional[ThreatScorer] = None


def get_scorer() -> ThreatScorer:
    """Get or create threat scorer."""
    global _scorer
    if _scorer is None:
        _scorer = ThreatScorer()
    return _scorer

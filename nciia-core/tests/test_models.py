"""
Test Data Models
"""

import pytest
from datetime import datetime
from uuid import UUID

from nciia.models import (
    Signal, SignalType, Persona, Entity, EntityType,
    ThreatScore, RiskLevel, Confidence, Evidence, Case
)


class TestConfidence:
    """Test Confidence model."""
    
    def test_create_confidence(self):
        conf = Confidence(score=0.8, reasoning=["test reason"])
        assert conf.score == 0.8
        assert conf.current_score <= 0.8  # May decay slightly
        assert conf.level in ["high", "very_high"]
    
    def test_confidence_boost(self):
        conf = Confidence(score=0.5)
        boosted = conf.boost(0.2, "new evidence")
        assert boosted.score == 0.7
        assert "new evidence" in boosted.reasoning
        assert boosted.source_count == 2


class TestSignal:
    """Test Signal model."""
    
    def test_create_signal(self):
        signal = Signal(
            type=SignalType.PASTE_SITE,
            source_name="Test Source",
            raw_content="Test content for analysis",
        )
        assert signal.id is not None
        assert signal.type == SignalType.PASTE_SITE
        assert signal.content_hash is not None
        assert len(signal.content_hash) == 32
    
    def test_signal_hash_consistency(self):
        content = "Same content"
        s1 = Signal(type=SignalType.WEB_CONTENT, source_name="A", raw_content=content)
        s2 = Signal(type=SignalType.WEB_CONTENT, source_name="B", raw_content=content)
        assert s1.content_hash == s2.content_hash
    
    def test_signal_requires_content(self):
        with pytest.raises(ValueError):
            Signal(type=SignalType.WEB_CONTENT, source_name="Test", raw_content="")


class TestEntity:
    """Test Entity model."""
    
    def test_create_entity(self):
        entity = Entity(
            type=EntityType.USERNAME,
            value="TestUser",
            original_value="TestUser",
        )
        assert entity.value == "testuser"  # normalized to lowercase
    
    def test_entity_types(self):
        for etype in EntityType:
            entity = Entity(type=etype, value="test", original_value="test")
            assert entity.type == etype


class TestPersona:
    """Test Persona model."""
    
    def test_create_persona(self):
        persona = Persona(
            primary_identifier="test@example.com",
            identifier_type=EntityType.EMAIL,
        )
        assert persona.id is not None
        assert persona.entity_count == 0
        assert persona.activity_count == 0
    
    def test_add_entity(self):
        persona = Persona(
            primary_identifier="testuser",
            identifier_type=EntityType.USERNAME,
        )
        entity = Entity(type=EntityType.EMAIL, value="test@test.com", original_value="test@test.com")
        persona.add_entity(entity)
        assert persona.entity_count == 1
    
    def test_add_signal(self):
        persona = Persona(
            primary_identifier="testuser",
            identifier_type=EntityType.USERNAME,
        )
        signal = Signal(type=SignalType.FORUM_POST, source_name="Test", raw_content="Test")
        persona.add_signal(signal.id)
        assert persona.activity_count == 1
        assert signal.id in persona.signal_ids


class TestThreatScore:
    """Test ThreatScore model."""
    
    def test_create_threat_score(self):
        score = ThreatScore(overall_score=75.0)
        assert score.overall_score == 75.0
        assert score.risk_level == RiskLevel.UNKNOWN
    
    def test_calculate_risk_level(self):
        assert ThreatScore.calculate_risk_level(85) == RiskLevel.CRITICAL
        assert ThreatScore.calculate_risk_level(65) == RiskLevel.HIGH
        assert ThreatScore.calculate_risk_level(45) == RiskLevel.MEDIUM
        assert ThreatScore.calculate_risk_level(25) == RiskLevel.LOW
        assert ThreatScore.calculate_risk_level(10) == RiskLevel.UNKNOWN
    
    def test_is_actionable(self):
        high_conf = ThreatScore(
            overall_score=80,
            risk_level=RiskLevel.CRITICAL,
            confidence=Confidence(score=0.9),
        )
        assert high_conf.is_actionable
        
        low_conf = ThreatScore(
            overall_score=80,
            risk_level=RiskLevel.CRITICAL,
            confidence=Confidence(score=0.5),
        )
        assert not low_conf.is_actionable


class TestCase:
    """Test Case model."""
    
    def test_create_case(self):
        case = Case(name="Test Investigation", description="Test case")
        assert case.id is not None
        assert case.status == "open"
        assert case.priority == "medium"
    
    def test_log_action(self):
        case = Case(name="Test", description="Test")
        case.log_action("update", "analyst1", {"field": "status"})
        assert len(case.action_log) == 1
        assert case.action_log[0]["action"] == "update"

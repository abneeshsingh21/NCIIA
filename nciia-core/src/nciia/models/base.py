"""
Core Data Models for N-CIIA

This module defines the fundamental data structures used throughout the system.
All models are immutable where possible and include comprehensive validation.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum, auto
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field, field_validator


class SignalType(str, Enum):
    """Types of intelligence signals that N-CIIA can process."""
    
    # Primary OSINT sources
    WEB_CONTENT = "web_content"
    FORUM_POST = "forum_post"
    PASTE_SITE = "paste_site"
    SOCIAL_MEDIA = "social_media"
    DOMAIN_RECORD = "domain_record"
    EMAIL_HEADER = "email_header"
    
    # Derived signals
    ALIAS_MATCH = "alias_match"
    BEHAVIORAL_MATCH = "behavioral_match"
    PATTERN_MATCH = "pattern_match"
    
    # Meta signals
    ANALYST_INPUT = "analyst_input"
    SYSTEM_GENERATED = "system_generated"


class RiskLevel(str, Enum):
    """Risk classification levels."""
    
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Confidence(BaseModel):
    """
    Represents confidence in a conclusion or inference.
    
    Includes the score, reasoning, and decay over time.
    """
    
    score: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    reasoning: list[str] = Field(default_factory=list, description="Factors supporting confidence")
    source_count: int = Field(default=1, description="Number of corroborating sources")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    decay_rate: float = Field(default=0.01, description="Daily confidence decay rate")
    
    @computed_field
    @property
    def current_score(self) -> float:
        """Calculate current confidence with time decay."""
        days_elapsed = (datetime.utcnow() - self.last_updated).days
        decayed = self.score * (1 - self.decay_rate) ** days_elapsed
        return max(0.0, min(1.0, decayed))
    
    @computed_field
    @property
    def level(self) -> str:
        """Human-readable confidence level."""
        if self.current_score >= 0.9:
            return "very_high"
        elif self.current_score >= 0.75:
            return "high"
        elif self.current_score >= 0.5:
            return "medium"
        elif self.current_score >= 0.25:
            return "low"
        return "very_low"
    
    def boost(self, amount: float = 0.1, reason: str = "") -> Confidence:
        """Return a new Confidence with boosted score."""
        new_score = min(1.0, self.score + amount)
        new_reasons = self.reasoning.copy()
        if reason:
            new_reasons.append(reason)
        return Confidence(
            score=new_score,
            reasoning=new_reasons,
            source_count=self.source_count + 1,
            last_updated=datetime.utcnow(),
            decay_rate=self.decay_rate,
        )


class Signal(BaseModel):
    """
    Represents a raw intelligence signal from any OSINT source.
    
    This is the fundamental input unit of the system.
    """
    
    id: UUID = Field(default_factory=uuid4)
    type: SignalType
    source_url: Optional[str] = None
    source_name: str = Field(description="Name of the OSINT source")
    
    # Content
    raw_content: str = Field(description="Original unprocessed content")
    extracted_text: Optional[str] = Field(default=None, description="Cleaned text content")
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    # Timing
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    content_timestamp: Optional[datetime] = Field(
        default=None, description="When the content was originally created"
    )
    
    # Hashing for deduplication and integrity
    content_hash: Optional[str] = None
    
    # Processing state
    is_processed: bool = False
    processing_notes: list[str] = Field(default_factory=list)
    
    @field_validator("raw_content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("raw_content cannot be empty")
        return v
    
    def model_post_init(self, __context: Any) -> None:
        """Compute content hash after initialization."""
        if self.content_hash is None:
            self.content_hash = hashlib.sha256(
                self.raw_content.encode("utf-8")
            ).hexdigest()[:32]
    
    @computed_field
    @property
    def age_hours(self) -> float:
        """Hours since signal was discovered."""
        delta = datetime.utcnow() - self.discovered_at
        return delta.total_seconds() / 3600


class EntityType(str, Enum):
    """Types of entities that can be extracted or tracked."""
    
    USERNAME = "username"
    EMAIL = "email"
    PHONE = "phone"
    DOMAIN = "domain"
    IP_ADDRESS = "ip_address"
    CRYPTO_ADDRESS = "crypto_address"
    KEYWORD = "keyword"
    HASH = "hash"
    URL = "url"


class Entity(BaseModel):
    """
    A discrete entity extracted from signals or provided as input.
    """
    
    id: UUID = Field(default_factory=uuid4)
    type: EntityType
    value: str = Field(description="The entity value (normalized)")
    original_value: str = Field(description="Original form before normalization")
    confidence: Confidence = Field(default_factory=lambda: Confidence(score=1.0))
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    occurrence_count: int = 1
    source_signals: list[UUID] = Field(default_factory=list)
    
    @field_validator("value")
    @classmethod
    def normalize_value(cls, v: str) -> str:
        return v.strip().lower()


class Alias(BaseModel):
    """
    Represents a potential alias relationship between two entities.
    """
    
    id: UUID = Field(default_factory=uuid4)
    primary_entity_id: UUID
    alias_entity_id: UUID
    confidence: Confidence
    evidence_type: str = Field(description="How the alias was inferred")
    discovered_at: datetime = Field(default_factory=datetime.utcnow)


class Persona(BaseModel):
    """
    A reconstructed digital persona aggregating multiple entities and signals.
    
    This is the core output of the persona reconstruction engine.
    """
    
    id: UUID = Field(default_factory=uuid4)
    case_id: Optional[UUID] = Field(default=None, description="Associated investigation case")
    
    # Core identity
    primary_identifier: str = Field(description="Main identifier for this persona")
    identifier_type: EntityType
    
    # Known entities
    entities: list[Entity] = Field(default_factory=list)
    aliases: list[Alias] = Field(default_factory=list)
    
    # Activity
    signal_ids: list[UUID] = Field(default_factory=list)
    platforms_detected: list[str] = Field(default_factory=list)
    
    # Timeline
    first_activity: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    activity_count: int = 0
    
    # Analysis
    behavioral_fingerprint_id: Optional[UUID] = None
    threat_score: Optional[ThreatScore] = None
    overall_confidence: Confidence = Field(
        default_factory=lambda: Confidence(score=0.5, reasoning=["Initial reconstruction"])
    )
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active_watch: bool = False
    analyst_notes: list[str] = Field(default_factory=list)
    
    @computed_field
    @property
    def entity_count(self) -> int:
        return len(self.entities)
    
    @computed_field
    @property
    def alias_count(self) -> int:
        return len(self.aliases)
    
    def add_entity(self, entity: Entity) -> None:
        """Add a new entity to this persona."""
        self.entities.append(entity)
        self.updated_at = datetime.utcnow()
    
    def add_signal(self, signal_id: UUID) -> None:
        """Record a new signal associated with this persona."""
        if signal_id not in self.signal_ids:
            self.signal_ids.append(signal_id)
            self.activity_count += 1
            self.last_activity = datetime.utcnow()
            self.updated_at = datetime.utcnow()


class ThreatIndicator(BaseModel):
    """
    A specific indicator contributing to threat assessment.
    """
    
    name: str
    description: str
    weight: float = Field(ge=0.0, le=1.0)
    detected: bool = False
    evidence: list[str] = Field(default_factory=list)
    signal_ids: list[UUID] = Field(default_factory=list)


class ThreatScore(BaseModel):
    """
    Comprehensive threat assessment with full explainability.
    """
    
    id: UUID = Field(default_factory=uuid4)
    persona_id: Optional[UUID] = None
    
    # Scores
    overall_score: float = Field(ge=0.0, le=100.0)
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    
    # Breakdown
    indicators: list[ThreatIndicator] = Field(default_factory=list)
    
    # Explainability
    reasoning: list[str] = Field(default_factory=list)
    contributing_factors: dict[str, float] = Field(default_factory=dict)
    
    # Confidence
    confidence: Confidence = Field(default_factory=lambda: Confidence(score=0.5))
    
    # Escalation
    is_escalating: bool = False
    escalation_velocity: float = 0.0  # Rate of score increase
    
    # Coordination signals
    coordination_detected: bool = False
    coordination_evidence: list[str] = Field(default_factory=list)
    
    # Timestamps
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None
    
    @computed_field
    @property
    def is_actionable(self) -> bool:
        """Whether this threat requires immediate attention."""
        return (
            self.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
            and self.confidence.current_score >= 0.7
        )
    
    @classmethod
    def calculate_risk_level(cls, score: float) -> RiskLevel:
        """Determine risk level from numerical score."""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        elif score >= 20:
            return RiskLevel.LOW
        return RiskLevel.UNKNOWN


class EvidenceItem(BaseModel):
    """
    A piece of evidence in an investigation package.
    """
    
    id: UUID = Field(default_factory=uuid4)
    
    # Content
    title: str
    description: str
    content_type: str  # text, screenshot, url, etc.
    content: str
    content_hash: str
    
    # Source
    source_url: Optional[str] = None
    source_name: str
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Provenance
    signal_id: Optional[UUID] = None
    collection_method: str = "automated"
    
    # Confidence
    confidence: Confidence = Field(default_factory=lambda: Confidence(score=0.8))
    
    def model_post_init(self, __context: Any) -> None:
        """Compute content hash."""
        if not self.content_hash:
            self.content_hash = hashlib.sha256(
                self.content.encode("utf-8")
            ).hexdigest()


class Evidence(BaseModel):
    """
    Complete evidence package for an investigation.
    
    Designed to be court-defensible with full traceability.
    """
    
    id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    persona_id: Optional[UUID] = None
    
    # Evidence items
    items: list[EvidenceItem] = Field(default_factory=list)
    
    # Timeline
    events: list[dict[str, Any]] = Field(default_factory=list)
    
    # IOCs
    indicators_of_compromise: list[Entity] = Field(default_factory=list)
    
    # Assessment
    threat_score: Optional[ThreatScore] = None
    overall_confidence: Confidence = Field(default_factory=lambda: Confidence(score=0.5))
    
    # Analyst work
    analyst_id: Optional[str] = None
    analyst_conclusions: list[str] = Field(default_factory=list)
    analyst_annotations: dict[str, str] = Field(default_factory=dict)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finalized_at: Optional[datetime] = None
    is_finalized: bool = False
    
    # Export
    export_formats_available: list[str] = Field(
        default_factory=lambda: ["json", "pdf", "html"]
    )
    
    @computed_field
    @property
    def item_count(self) -> int:
        return len(self.items)
    
    @computed_field
    @property
    def package_hash(self) -> str:
        """Compute hash of entire evidence package for integrity."""
        content = "|".join(item.content_hash for item in self.items)
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def add_item(self, item: EvidenceItem) -> None:
        """Add an evidence item."""
        if self.is_finalized:
            raise ValueError("Cannot modify finalized evidence package")
        self.items.append(item)
    
    def finalize(self, analyst_id: str) -> None:
        """Lock the evidence package."""
        self.analyst_id = analyst_id
        self.finalized_at = datetime.utcnow()
        self.is_finalized = True


class Case(BaseModel):
    """
    An investigation case grouping related personas and evidence.
    """
    
    id: UUID = Field(default_factory=uuid4)
    
    # Identification
    name: str
    description: str
    
    # Related entities
    persona_ids: list[UUID] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)
    
    # Status
    status: str = "open"  # open, active, closed, archived
    priority: str = "medium"  # low, medium, high, critical
    
    # Assignment
    analyst_id: Optional[str] = None
    team_ids: list[str] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    
    # Audit
    action_log: list[dict[str, Any]] = Field(default_factory=list)
    
    def log_action(self, action: str, analyst_id: str, details: dict[str, Any] | None = None) -> None:
        """Record an action in the audit log."""
        self.action_log.append({
            "action": action,
            "analyst_id": analyst_id,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {},
        })
        self.updated_at = datetime.utcnow()


class BehavioralFingerprint(BaseModel):
    """
    Behavioral signature for authorship attribution.
    """
    
    id: UUID = Field(default_factory=uuid4)
    persona_id: Optional[UUID] = None
    
    # Stylometry features
    vocabulary_fingerprint: list[float] = Field(default_factory=list)
    punctuation_pattern: dict[str, float] = Field(default_factory=dict)
    sentence_length_distribution: dict[str, float] = Field(default_factory=dict)
    
    # Temporal patterns
    active_hours: list[int] = Field(default_factory=list)  # 0-23
    active_days: list[int] = Field(default_factory=list)   # 0-6
    posting_frequency: float = 0.0  # Posts per day
    
    # Content patterns
    common_phrases: list[str] = Field(default_factory=list)
    topic_interests: list[str] = Field(default_factory=list)
    
    # Confidence
    sample_count: int = 0
    confidence: Confidence = Field(default_factory=lambda: Confidence(score=0.3))
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def compute_similarity(self, other: BehavioralFingerprint) -> float:
        """Compute similarity score with another fingerprint."""
        # Simplified similarity - actual implementation would be more sophisticated
        if not self.vocabulary_fingerprint or not other.vocabulary_fingerprint:
            return 0.0
        
        # Cosine similarity of vocabulary fingerprints
        min_len = min(len(self.vocabulary_fingerprint), len(other.vocabulary_fingerprint))
        if min_len == 0:
            return 0.0
        
        dot_product = sum(
            a * b for a, b in zip(
                self.vocabulary_fingerprint[:min_len],
                other.vocabulary_fingerprint[:min_len]
            )
        )
        mag_a = sum(x ** 2 for x in self.vocabulary_fingerprint[:min_len]) ** 0.5
        mag_b = sum(x ** 2 for x in other.vocabulary_fingerprint[:min_len]) ** 0.5
        
        if mag_a == 0 or mag_b == 0:
            return 0.0
        
        return dot_product / (mag_a * mag_b)

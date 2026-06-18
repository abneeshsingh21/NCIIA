"""
Timeline Reconstruction

Reconstructs activity timeline from signals for a persona.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import structlog

from nciia.models import Signal

logger = structlog.get_logger(__name__)


@dataclass
class TimelineEvent:
    """A single event in the activity timeline."""
    
    timestamp: datetime
    event_type: str
    title: str
    description: str
    signal_id: Optional[UUID] = None
    source: Optional[str] = None
    url: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    importance: int = 1  # 1-5 scale


@dataclass
class ActivityPattern:
    """Detected activity pattern."""
    
    pattern_type: str  # daily_rhythm, burst, dormant, etc.
    description: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    confidence: float = 0.5


class TimelineReconstructor:
    """
    Reconstructs and analyzes activity timelines.
    
    Features:
    - Chronological event ordering
    - Gap detection
    - Activity burst detection
    - Temporal pattern analysis
    """
    
    def __init__(self):
        self._events: list[TimelineEvent] = []
    
    def add_signal(self, signal: Signal) -> TimelineEvent:
        """Convert a signal to a timeline event and add it."""
        timestamp = signal.content_timestamp or signal.discovered_at
        
        event = TimelineEvent(
            timestamp=timestamp,
            event_type=signal.type.value,
            title=f"{signal.type.value} from {signal.source_name}",
            description=signal.raw_content[:200] + "..." 
                       if len(signal.raw_content) > 200 
                       else signal.raw_content,
            signal_id=signal.id,
            source=signal.source_name,
            url=signal.source_url,
        )
        
        self._events.append(event)
        return event
    
    def add_event(self, event: TimelineEvent) -> None:
        """Add a timeline event directly."""
        self._events.append(event)
    
    def get_timeline(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> list[TimelineEvent]:
        """
        Get chronologically sorted timeline.
        
        Args:
            start: Filter events after this time
            end: Filter events before this time
            limit: Maximum events to return
            
        Returns:
            Sorted list of events
        """
        events = self._events.copy()
        
        if start:
            events = [e for e in events if e.timestamp >= start]
        
        if end:
            events = [e for e in events if e.timestamp <= end]
        
        # Sort chronologically
        events.sort(key=lambda e: e.timestamp)
        
        if limit:
            events = events[:limit]
        
        return events
    
    def detect_gaps(self, threshold_hours: int = 168) -> list[dict[str, Any]]:
        """
        Detect significant gaps in activity.
        
        Args:
            threshold_hours: Minimum gap hours to report
            
        Returns:
            List of gap periods
        """
        if len(self._events) < 2:
            return []
        
        sorted_events = sorted(self._events, key=lambda e: e.timestamp)
        gaps = []
        
        for i in range(1, len(sorted_events)):
            prev = sorted_events[i - 1]
            curr = sorted_events[i]
            
            gap_hours = (curr.timestamp - prev.timestamp).total_seconds() / 3600
            
            if gap_hours >= threshold_hours:
                gaps.append({
                    "start": prev.timestamp.isoformat(),
                    "end": curr.timestamp.isoformat(),
                    "duration_hours": gap_hours,
                    "duration_days": gap_hours / 24,
                })
        
        return gaps
    
    def detect_bursts(
        self,
        window_hours: int = 24,
        min_events: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Detect activity bursts (high-frequency periods).
        
        Args:
            window_hours: Time window to analyze
            min_events: Minimum events in window to be a burst
            
        Returns:
            List of burst periods
        """
        if len(self._events) < min_events:
            return []
        
        sorted_events = sorted(self._events, key=lambda e: e.timestamp)
        bursts = []
        window = timedelta(hours=window_hours)
        
        i = 0
        while i < len(sorted_events):
            window_start = sorted_events[i].timestamp
            window_end = window_start + window
            
            # Count events in window
            window_events = [
                e for e in sorted_events[i:]
                if e.timestamp <= window_end
            ]
            
            if len(window_events) >= min_events:
                bursts.append({
                    "start": window_start.isoformat(),
                    "end": window_events[-1].timestamp.isoformat(),
                    "event_count": len(window_events),
                    "intensity": len(window_events) / window_hours,
                })
                # Skip past this burst
                i += len(window_events)
            else:
                i += 1
        
        return bursts
    
    def analyze_patterns(self) -> list[ActivityPattern]:
        """Analyze activity patterns."""
        patterns = []
        
        if len(self._events) < 2:
            return patterns
        
        sorted_events = sorted(self._events, key=lambda e: e.timestamp)
        
        # Analyze hourly distribution
        hour_counts = [0] * 24
        for event in sorted_events:
            hour_counts[event.timestamp.hour] += 1
        
        # Find peak hours
        max_hour = hour_counts.index(max(hour_counts))
        peak_range_start = (max_hour - 2) % 24
        peak_range_end = (max_hour + 2) % 24
        
        patterns.append(ActivityPattern(
            pattern_type="daily_rhythm",
            description=f"Most active around {max_hour}:00 UTC",
            confidence=0.7 if max(hour_counts) > len(self._events) * 0.1 else 0.4,
        ))
        
        # Detect recent activity level
        now = datetime.utcnow()
        recent = [e for e in sorted_events if (now - e.timestamp).days <= 7]
        
        if len(recent) == 0:
            patterns.append(ActivityPattern(
                pattern_type="dormant",
                description="No activity in the last 7 days",
                confidence=0.9,
            ))
        elif len(recent) >= 10:
            patterns.append(ActivityPattern(
                pattern_type="highly_active",
                description=f"{len(recent)} events in the last 7 days",
                confidence=0.85,
            ))
        
        return patterns
    
    def get_summary(self) -> dict[str, Any]:
        """Get timeline summary statistics."""
        if not self._events:
            return {"total_events": 0}
        
        sorted_events = sorted(self._events, key=lambda e: e.timestamp)
        
        return {
            "total_events": len(self._events),
            "first_activity": sorted_events[0].timestamp.isoformat(),
            "last_activity": sorted_events[-1].timestamp.isoformat(),
            "span_days": (sorted_events[-1].timestamp - sorted_events[0].timestamp).days,
            "sources": list(set(e.source for e in self._events if e.source)),
            "event_types": list(set(e.event_type for e in self._events)),
        }

"""
Threat Evolution Predictor

Predicts future threat states using time-series analysis
and behavioral patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Prediction:
    """A threat prediction."""
    
    persona_id: UUID
    current_score: float
    predicted_score: float
    prediction_horizon_days: int
    confidence: float
    factors: list[str]
    trend: str  # increasing, decreasing, stable
    velocity: float  # change per day
    explanation: str


@dataclass
class TrendData:
    """Historical trend data point."""
    
    timestamp: datetime
    score: float


class ThreatPredictor:
    """
    Predicts threat evolution using time-series analysis.
    
    Uses linear regression and exponential smoothing for forecasting.
    All predictions are fully explainable.
    """
    
    def __init__(self):
        self._history: dict[str, list[TrendData]] = {}
    
    def record_score(self, persona_id: UUID, score: float) -> None:
        """Record a threat score for trend analysis."""
        key = str(persona_id)
        if key not in self._history:
            self._history[key] = []
        
        self._history[key].append(TrendData(
            timestamp=datetime.utcnow(),
            score=score,
        ))
        
        # Keep last 90 days
        cutoff = datetime.utcnow() - timedelta(days=90)
        self._history[key] = [
            d for d in self._history[key] if d.timestamp >= cutoff
        ]
    
    def predict(
        self,
        persona_id: UUID,
        horizon_days: int = 7,
    ) -> Optional[Prediction]:
        """
        Predict threat score for future timeframe.
        
        Args:
            persona_id: Target persona
            horizon_days: Days ahead to predict
            
        Returns:
            Prediction with explanation
        """
        key = str(persona_id)
        history = self._history.get(key, [])
        
        if len(history) < 2:
            return None
        
        # Calculate trend using linear regression
        slope, intercept = self._linear_regression(history)
        
        # Current score (most recent)
        current_score = history[-1].score
        
        # Predicted score
        predicted_score = current_score + (slope * horizon_days)
        predicted_score = max(0, min(100, predicted_score))  # Clamp 0-100
        
        # Determine trend
        if slope > 2:
            trend = "rapidly_increasing"
        elif slope > 0.5:
            trend = "increasing"
        elif slope < -2:
            trend = "rapidly_decreasing"
        elif slope < -0.5:
            trend = "decreasing"
        else:
            trend = "stable"
        
        # Calculate confidence based on data consistency
        confidence = self._calculate_confidence(history, slope)
        
        # Build factors
        factors = self._identify_factors(history, slope)
        
        # Build explanation
        explanation = self._build_explanation(
            current_score, predicted_score, slope, horizon_days, trend
        )
        
        return Prediction(
            persona_id=persona_id,
            current_score=current_score,
            predicted_score=predicted_score,
            prediction_horizon_days=horizon_days,
            confidence=confidence,
            factors=factors,
            trend=trend,
            velocity=slope,
            explanation=explanation,
        )
    
    def _linear_regression(self, history: list[TrendData]) -> tuple[float, float]:
        """Simple linear regression for slope calculation."""
        if len(history) < 2:
            return 0.0, 0.0
        
        # Convert to days from first observation
        base_time = history[0].timestamp
        x = [(d.timestamp - base_time).total_seconds() / 86400 for d in history]
        y = [d.score for d in history]
        
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)
        
        denominator = n * sum_x2 - sum_x ** 2
        if abs(denominator) < 0.001:
            return 0.0, sum_y / n
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n
        
        return slope, intercept
    
    def _calculate_confidence(
        self,
        history: list[TrendData],
        slope: float,
    ) -> float:
        """Calculate prediction confidence."""
        # Base confidence from data points
        data_confidence = min(0.8, 0.3 + len(history) * 0.05)
        
        # Reduce confidence for volatile data
        if len(history) >= 3:
            scores = [d.score for d in history]
            variance = sum((s - sum(scores)/len(scores))**2 for s in scores) / len(scores)
            volatility_penalty = min(0.3, variance / 1000)
            data_confidence -= volatility_penalty
        
        return max(0.2, data_confidence)
    
    def _identify_factors(
        self,
        history: list[TrendData],
        slope: float,
    ) -> list[str]:
        """Identify contributing factors to trend."""
        factors = []
        
        if slope > 0:
            factors.append("Threat score increasing over time")
        elif slope < 0:
            factors.append("Threat score decreasing over time")
        
        # Check for recent acceleration
        if len(history) >= 5:
            recent = history[-3:]
            earlier = history[-6:-3]
            if earlier:
                recent_avg = sum(d.score for d in recent) / len(recent)
                earlier_avg = sum(d.score for d in earlier) / len(earlier)
                if recent_avg > earlier_avg + 10:
                    factors.append("Recent acceleration in threat level")
        
        # Check for high activity
        if len(history) >= 10:
            factors.append(f"Based on {len(history)} data points")
        
        return factors
    
    def _build_explanation(
        self,
        current: float,
        predicted: float,
        slope: float,
        horizon: int,
        trend: str,
    ) -> str:
        """Build human-readable explanation."""
        change = predicted - current
        direction = "increase" if change > 0 else "decrease"
        
        if abs(change) < 5:
            return f"Threat level expected to remain stable around {predicted:.0f} over the next {horizon} days."
        
        return (
            f"Based on historical trend analysis, threat score is expected to "
            f"{direction} from {current:.0f} to {predicted:.0f} over the next "
            f"{horizon} days. This represents a {trend.replace('_', ' ')} pattern "
            f"with a velocity of {abs(slope):.1f} points per day."
        )


# Global predictor
_predictor: Optional[ThreatPredictor] = None


def get_predictor() -> ThreatPredictor:
    """Get or create threat predictor."""
    global _predictor
    if _predictor is None:
        _predictor = ThreatPredictor()
    return _predictor

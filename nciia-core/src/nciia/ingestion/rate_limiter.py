"""
Rate Limiter for OSINT Collection

Token bucket rate limiting with per-source tracking
to ensure compliance with source ToS and prevent blocking.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class RateLimitState:
    """State for a single rate limiter."""
    
    tokens: float
    max_tokens: float
    refill_rate: float  # tokens per second
    last_refill: datetime = field(default_factory=datetime.utcnow)
    total_requests: int = 0
    denied_requests: int = 0


class RateLimiter:
    """
    Token bucket rate limiter for OSINT sources.
    
    Supports per-source rate limits and global rate limiting.
    """
    
    def __init__(
        self,
        default_rate: float = 10.0,  # requests per minute
        global_rate: float = 30.0,    # global requests per minute
    ):
        self.default_rate = default_rate
        self.global_rate = global_rate
        
        # Per-source limiters
        self._limiters: dict[str, RateLimitState] = {}
        
        # Global limiter
        self._global = RateLimitState(
            tokens=global_rate,
            max_tokens=global_rate,
            refill_rate=global_rate / 60.0,
        )
    
    def configure_source(
        self,
        source_name: str,
        requests_per_minute: float,
    ) -> None:
        """Configure rate limit for a specific source."""
        self._limiters[source_name] = RateLimitState(
            tokens=requests_per_minute,
            max_tokens=requests_per_minute,
            refill_rate=requests_per_minute / 60.0,
        )
        logger.info(
            "rate_limit_configured",
            source=source_name,
            rpm=requests_per_minute,
        )
    
    def _refill(self, state: RateLimitState) -> None:
        """Refill tokens based on elapsed time."""
        now = datetime.utcnow()
        elapsed = (now - state.last_refill).total_seconds()
        
        # Add tokens based on elapsed time
        state.tokens = min(
            state.max_tokens,
            state.tokens + (elapsed * state.refill_rate)
        )
        state.last_refill = now
    
    def can_proceed(self, source_name: str) -> bool:
        """
        Check if a request can proceed without blocking.
        
        Returns:
            True if request can proceed, False if rate limited
        """
        # Check global limit
        self._refill(self._global)
        if self._global.tokens < 1:
            return False
        
        # Check source-specific limit
        if source_name not in self._limiters:
            self.configure_source(source_name, self.default_rate)
        
        state = self._limiters[source_name]
        self._refill(state)
        
        return state.tokens >= 1
    
    async def acquire(self, source_name: str, timeout: float = 30.0) -> bool:
        """
        Acquire permission to make a request, waiting if necessary.
        
        Args:
            source_name: Name of the source
            timeout: Maximum seconds to wait
            
        Returns:
            True if acquired, False if timeout
        """
        start = datetime.utcnow()
        
        while True:
            if self._try_acquire(source_name):
                return True
            
            # Check timeout
            elapsed = (datetime.utcnow() - start).total_seconds()
            if elapsed >= timeout:
                logger.warning("rate_limit_timeout", source=source_name)
                return False
            
            # Wait and retry
            await asyncio.sleep(0.5)
    
    def _try_acquire(self, source_name: str) -> bool:
        """Try to acquire a token."""
        # Check global limit
        self._refill(self._global)
        if self._global.tokens < 1:
            self._global.denied_requests += 1
            return False
        
        # Check source limit
        if source_name not in self._limiters:
            self.configure_source(source_name, self.default_rate)
        
        state = self._limiters[source_name]
        self._refill(state)
        
        if state.tokens < 1:
            state.denied_requests += 1
            return False
        
        # Consume tokens
        self._global.tokens -= 1
        self._global.total_requests += 1
        state.tokens -= 1
        state.total_requests += 1
        
        return True
    
    def release(self, source_name: str) -> None:
        """Release a token (for retry scenarios)."""
        if source_name in self._limiters:
            state = self._limiters[source_name]
            state.tokens = min(state.max_tokens, state.tokens + 1)
    
    def get_stats(self) -> dict:
        """Get rate limiting statistics."""
        return {
            "global": {
                "tokens": self._global.tokens,
                "max_tokens": self._global.max_tokens,
                "total_requests": self._global.total_requests,
                "denied_requests": self._global.denied_requests,
            },
            "sources": {
                name: {
                    "tokens": state.tokens,
                    "max_tokens": state.max_tokens,
                    "total_requests": state.total_requests,
                    "denied_requests": state.denied_requests,
                }
                for name, state in self._limiters.items()
            },
        }
    
    def wait_time(self, source_name: str) -> float:
        """Get estimated wait time in seconds for next request."""
        if source_name not in self._limiters:
            return 0.0
        
        state = self._limiters[source_name]
        self._refill(state)
        
        if state.tokens >= 1:
            return 0.0
        
        # Calculate time to get 1 token
        needed = 1 - state.tokens
        return needed / state.refill_rate


class BackoffManager:
    """
    Manages exponential backoff for failed requests.
    """
    
    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 300.0,  # 5 minutes
        multiplier: float = 2.0,
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        
        self._failures: dict[str, int] = {}
        self._last_failure: dict[str, datetime] = {}
    
    def record_failure(self, source_name: str) -> float:
        """
        Record a failure and return the delay before next attempt.
        
        Returns:
            Delay in seconds before next attempt
        """
        self._failures[source_name] = self._failures.get(source_name, 0) + 1
        self._last_failure[source_name] = datetime.utcnow()
        
        delay = min(
            self.max_delay,
            self.base_delay * (self.multiplier ** (self._failures[source_name] - 1))
        )
        
        logger.info(
            "backoff_delay",
            source=source_name,
            failures=self._failures[source_name],
            delay_seconds=delay,
        )
        
        return delay
    
    def record_success(self, source_name: str) -> None:
        """Record a successful request, resetting the backoff."""
        if source_name in self._failures:
            del self._failures[source_name]
        if source_name in self._last_failure:
            del self._last_failure[source_name]
    
    def get_delay(self, source_name: str) -> float:
        """Get current delay for a source (0 if no recent failures)."""
        if source_name not in self._failures:
            return 0.0
        
        failures = self._failures[source_name]
        delay = min(
            self.max_delay,
            self.base_delay * (self.multiplier ** (failures - 1))
        )
        
        # Check if delay has elapsed
        last = self._last_failure.get(source_name)
        if last:
            elapsed = (datetime.utcnow() - last).total_seconds()
            remaining = delay - elapsed
            return max(0.0, remaining)
        
        return 0.0
    
    async def wait_if_needed(self, source_name: str) -> None:
        """Wait for backoff delay if applicable."""
        delay = self.get_delay(source_name)
        if delay > 0:
            logger.debug("backing_off", source=source_name, seconds=delay)
            await asyncio.sleep(delay)

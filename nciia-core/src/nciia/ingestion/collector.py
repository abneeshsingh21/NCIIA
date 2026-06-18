"""
OSINT Collector - Main Ingestion Coordinator

Orchestrates all OSINT sources, rate limiting, delta detection,
and signal emission in a unified collection pipeline.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Callable, Awaitable
from uuid import UUID

import structlog

from nciia.ingestion.sources import (
    BaseSource,
    SourceResult,
    WebSearchSource,
    PasteSiteSource,
    DomainSource,
)
from nciia.ingestion.delta import DeltaDetector
from nciia.ingestion.rate_limiter import RateLimiter, BackoffManager
from nciia.models import Signal
from nciia.db import get_database
from nciia.utils import get_settings

logger = structlog.get_logger(__name__)


# Type for signal handlers
SignalHandler = Callable[[Signal], Awaitable[None]]


@dataclass
class CollectorStats:
    """Statistics for the collector."""
    
    started_at: Optional[datetime] = None
    signals_collected: int = 0
    duplicates_skipped: int = 0
    errors: int = 0
    sources_active: int = 0
    last_collection: Optional[datetime] = None


from nciia.simulation.scenario import ScenarioGenerator

class OSINTCollector:
    """
    Main OSINT collection coordinator.
    
    Manages multiple sources, handles rate limiting and delta detection,
    and emits signals to the processing pipeline.
    """
    
    def __init__(self):
        self.sources: dict[str, BaseSource] = {}
        self.delta_detector = DeltaDetector()
        self.rate_limiter = RateLimiter()
        self.backoff = BackoffManager()
        
        self.stats = CollectorStats()
        self._running = False
        self._handlers: list[SignalHandler] = []
        self._collection_tasks: dict[str, asyncio.Task] = {}
        self._queue = asyncio.Queue()
        self._simulator = ScenarioGenerator()
    
    def add_source(self, source: BaseSource) -> None:
        """Register an OSINT source."""
        self.sources[source.name] = source
        self.rate_limiter.configure_source(
            source.name,
            source.config.rate_limit_per_minute,
        )
        logger.info("source_registered", source=source.name)
    
    def remove_source(self, source_name: str) -> None:
        """Remove an OSINT source."""
        if source_name in self.sources:
            del self.sources[source_name]
            if source_name in self._collection_tasks:
                self._collection_tasks[source_name].cancel()
    
    def add_handler(self, handler: SignalHandler) -> None:
        """Add a signal handler to be called for each new signal."""
        self._handlers.append(handler)
    
    async def initialize(self) -> None:
        """Initialize all sources."""
        settings = get_settings()
        
        # Create default sources based on config
        enabled = settings.osint.enabled_sources
        
        if "web_search" in enabled:
            self.add_source(WebSearchSource())
        
        if "paste_sites" in enabled:
            self.add_source(PasteSiteSource())
        
        if "domain_records" in enabled:
            self.add_source(DomainSource())
        
        # Initialize each source
        for source in self.sources.values():
            await source.initialize()
        
        self.stats.sources_active = len(self.sources)
        logger.info("collector_initialized", sources=list(self.sources.keys()))
    
    async def cleanup(self) -> None:
        """Cleanup all resources."""
        self._running = False
        
        # Cancel collection tasks
        for task in self._collection_tasks.values():
            task.cancel()
        
        # Cleanup sources
        for source in self.sources.values():
            await source.cleanup()
        
        logger.info("collector_cleanup")
    
    async def start(self) -> None:
        """Start continuous collection from all sources."""
        self._running = True
        self.stats.started_at = datetime.utcnow()
        
        logger.info("collector_started")
        
        # Start collection task for each source
        for name, source in self.sources.items():
            if source.is_enabled:
                task = asyncio.create_task(
                    self._collection_loop(source),
                    name=f"collect_{name}",
                )
                self._collection_tasks[name] = task
        
        # Start Simulation Task
        self._collection_tasks["simulation"] = asyncio.create_task(
            self._simulator.start_simulation(self._queue),
            name="simulation_engine"
        )
        self._collection_tasks["queue_processor"] = asyncio.create_task(
            self._process_queue(),
            name="signal_processor"
        )
    
    async def stop(self) -> None:
        """Stop collection."""
        self._running = False
        
        for task in self._collection_tasks.values():
            task.cancel()
        
        self._collection_tasks.clear()
        self._collection_tasks.clear()
        self._simulator.stop()
        logger.info("collector_stopped")
    
    async def search(self, query: str, sources: Optional[list[str]] = None) -> list[Signal]:
        """
        Perform a one-time search across specified sources.
        
        Args:
            query: Search query
            sources: List of source names (None = all)
            
        Returns:
            List of signals found
        """
        signals = []
        target_sources = (
            [self.sources[s] for s in sources if s in self.sources]
            if sources
            else list(self.sources.values())
        )
        
        for source in target_sources:
            if not source.is_enabled:
                continue
            
            # Rate limit check
            if not await self.rate_limiter.acquire(source.name):
                logger.warning("search_rate_limited", source=source.name)
                continue
            
            try:
                async for result in source.search(query):
                    signal = await self._process_result(result, source)
                    if signal:
                        signals.append(signal)
                        
                self.backoff.record_success(source.name)
                
            except Exception as e:
                logger.error("search_error", source=source.name, error=str(e))
                self.backoff.record_failure(source.name)
                self.stats.errors += 1
        
        return signals
    
    async def _collection_loop(self, source: BaseSource) -> None:
        """Main collection loop for a source."""
        while self._running:
            try:
                # Wait for backoff if needed
                await self.backoff.wait_if_needed(source.name)
                
                # Rate limit
                if not await self.rate_limiter.acquire(source.name, timeout=60):
                    await asyncio.sleep(10)
                    continue
                
                # Collect updates
                async for result in source.check_updates():
                    signal = await self._process_result(result, source)
                    if signal:
                        await self._emit_signal(signal)
                
                self.backoff.record_success(source.name)
                self.stats.last_collection = datetime.utcnow()
                
                # Wait for next check interval
                await asyncio.sleep(source.config.check_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("collection_error", source=source.name, error=str(e))
                delay = self.backoff.record_failure(source.name)
                self.stats.errors += 1
                await asyncio.sleep(delay)
    
    async def _process_result(
        self,
        result: SourceResult,
        source: BaseSource,
    ) -> Optional[Signal]:
        """Process a source result into a signal."""
        # Delta detection
        is_new, content_hash = self.delta_detector.is_new(
            result.content,
            source=source.name,
        )
        
        if not is_new:
            self.stats.duplicates_skipped += 1
            return None
        
        # Convert to signal
        signal = source.to_signal(result)
        signal.content_hash = content_hash
        
        # Store in database
        db = await get_database()
        await db.insert_signal(signal.model_dump())
        
        self.stats.signals_collected += 1
        logger.info(
            "signal_collected",
            source=source.name,
            hash=content_hash[:8],
        )
        
        return signal
    
    async def _emit_signal(self, signal: Signal) -> None:
        """Emit a signal to all registered handlers."""
        for handler in self._handlers:
            try:
                await handler(signal)
            except Exception as e:
                logger.error("handler_error", error=str(e))
    
    def get_stats(self) -> dict[str, Any]:
        """Get collector statistics."""
        return {
            "started_at": self.stats.started_at.isoformat() if self.stats.started_at else None,
            "signals_collected": self.stats.signals_collected,
            "duplicates_skipped": self.stats.duplicates_skipped,
            "errors": self.stats.errors,
            "sources_active": self.stats.sources_active,
            "last_collection": self.stats.last_collection.isoformat() if self.stats.last_collection else None,
            "rate_limiter": self.rate_limiter.get_stats(),
            "delta_detector": self.delta_detector.get_stats(),
        }


    async def _process_queue(self) -> None:
        """Process signals from the internal simulation queue."""
        while self._running:
            try:
                signal = await self._queue.get()
                
                # Check for duplicates via delta detector
                is_new, content_hash = self.delta_detector.is_new(
                    signal.content, 
                    source="simulation"
                )
                
                if is_new:
                    signal.content_hash = content_hash
                    # Save to DB
                    db = await get_database()
                    await db.insert_signal(signal.model_dump())
                    
                    # Emit
                    await self._emit_signal(signal)
                    self.stats.signals_collected += 1
                
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("queue_process_error", error=str(e))


# Global collector instance
_collector: Optional[OSINTCollector] = None


async def get_collector() -> OSINTCollector:
    """Get or create the global collector."""
    global _collector
    if _collector is None:
        _collector = OSINTCollector()
        await _collector.initialize()
    return _collector

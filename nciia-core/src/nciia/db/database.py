"""
Database Layer for N-CIIA

SQLite-based async database with full audit logging.
Designed for MVP with clean upgrade path to PostgreSQL.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

import aiosqlite
import structlog

logger = structlog.get_logger(__name__)


class Database:
    """
    Async SQLite database manager for N-CIIA.
    
    Handles all CRUD operations with automatic audit logging
    and transaction management.
    """
    
    def __init__(self, db_path: str | Path = "data/db/nciia.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self) -> None:
        """Establish database connection."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._connection.execute("PRAGMA journal_mode = WAL")
        await self.initialize_schema()
        logger.info("database_connected", path=str(self.db_path))
    
    async def disconnect(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("database_disconnected")
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Context manager for database transactions."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        
        try:
            yield self._connection
            await self._connection.commit()
        except Exception as e:
            await self._connection.rollback()
            logger.error("transaction_failed", error=str(e))
            raise
    
    async def initialize_schema(self) -> None:
        """Create all database tables."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        
        await self._connection.executescript(SCHEMA_SQL)
        await self._connection.commit()
        logger.info("schema_initialized")
    
    # =====================
    # Signal Operations
    # =====================
    
    async def insert_signal(self, signal_data: dict[str, Any]) -> UUID:
        """Insert a new signal."""
        async with self.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO signals (
                    id, type, source_url, source_name, raw_content, extracted_text,
                    metadata, discovered_at, content_timestamp, content_hash,
                    is_processed, processing_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(signal_data["id"]),
                    signal_data["type"],
                    signal_data.get("source_url"),
                    signal_data["source_name"],
                    signal_data["raw_content"],
                    signal_data.get("extracted_text"),
                    json.dumps(signal_data.get("metadata", {})),
                    signal_data.get("discovered_at", datetime.utcnow()).isoformat(),
                    signal_data.get("content_timestamp", "").isoformat() if signal_data.get("content_timestamp") else None,
                    signal_data.get("content_hash"),
                    signal_data.get("is_processed", False),
                    json.dumps(signal_data.get("processing_notes", [])),
                )
            )
            await self._log_action(conn, "signal_created", str(signal_data["id"]))
            return signal_data["id"]
    
    async def get_signal(self, signal_id: UUID) -> Optional[dict[str, Any]]:
        """Retrieve a signal by ID."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        
        cursor = await self._connection.execute(
            "SELECT * FROM signals WHERE id = ?",
            (str(signal_id),)
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None
    
    async def get_signals_by_hash(self, content_hash: str) -> list[dict[str, Any]]:
        """Find signals with matching content hash (deduplication)."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        
        cursor = await self._connection.execute(
            "SELECT * FROM signals WHERE content_hash = ?",
            (content_hash,)
        )
        rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]
    
    async def mark_signal_processed(self, signal_id: UUID, notes: list[str] | None = None) -> None:
        """Mark a signal as processed."""
        async with self.transaction() as conn:
            await conn.execute(
                """
                UPDATE signals 
                SET is_processed = ?, processing_notes = ?
                WHERE id = ?
                """,
                (True, json.dumps(notes or []), str(signal_id))
            )
            await self._log_action(conn, "signal_processed", str(signal_id))
    
    # =====================
    # Persona Operations
    # =====================
    
    async def insert_persona(self, persona_data: dict[str, Any]) -> UUID:
        """Insert a new persona."""
        async with self.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO personas (
                    id, case_id, primary_identifier, identifier_type,
                    entities, aliases, signal_ids, platforms_detected,
                    first_activity, last_activity, activity_count,
                    behavioral_fingerprint_id, threat_score, overall_confidence,
                    created_at, updated_at, is_active_watch, analyst_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(persona_data["id"]),
                    str(persona_data.get("case_id")) if persona_data.get("case_id") else None,
                    persona_data["primary_identifier"],
                    persona_data["identifier_type"],
                    json.dumps([e.model_dump() if hasattr(e, 'model_dump') else e for e in persona_data.get("entities", [])]),
                    json.dumps([a.model_dump() if hasattr(a, 'model_dump') else a for a in persona_data.get("aliases", [])]),
                    json.dumps([str(s) for s in persona_data.get("signal_ids", [])]),
                    json.dumps(persona_data.get("platforms_detected", [])),
                    persona_data.get("first_activity", "").isoformat() if persona_data.get("first_activity") else None,
                    persona_data.get("last_activity", "").isoformat() if persona_data.get("last_activity") else None,
                    persona_data.get("activity_count", 0),
                    str(persona_data.get("behavioral_fingerprint_id")) if persona_data.get("behavioral_fingerprint_id") else None,
                    json.dumps(persona_data.get("threat_score").model_dump() if persona_data.get("threat_score") and hasattr(persona_data.get("threat_score"), 'model_dump') else persona_data.get("threat_score")),
                    json.dumps(persona_data.get("overall_confidence").model_dump() if persona_data.get("overall_confidence") and hasattr(persona_data.get("overall_confidence"), 'model_dump') else persona_data.get("overall_confidence")),
                    persona_data.get("created_at", datetime.utcnow()).isoformat(),
                    persona_data.get("updated_at", datetime.utcnow()).isoformat(),
                    persona_data.get("is_active_watch", False),
                    json.dumps(persona_data.get("analyst_notes", [])),
                )
            )
            await self._log_action(conn, "persona_created", str(persona_data["id"]))
            return persona_data["id"]
    
    async def get_persona(self, persona_id: UUID) -> Optional[dict[str, Any]]:
        """Retrieve a persona by ID."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        
        cursor = await self._connection.execute(
            "SELECT * FROM personas WHERE id = ?",
            (str(persona_id),)
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None
    
    async def search_personas(
        self,
        identifier: Optional[str] = None,
        case_id: Optional[UUID] = None,
        is_active_watch: Optional[bool] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search personas with filters."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        
        query = "SELECT * FROM personas WHERE 1=1"
        params: list[Any] = []
        
        if identifier:
            query += " AND primary_identifier LIKE ?"
            params.append(f"%{identifier}%")
        
        if case_id:
            query += " AND case_id = ?"
            params.append(str(case_id))
        
        if is_active_watch is not None:
            query += " AND is_active_watch = ?"
            params.append(is_active_watch)
        
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]
    
    async def update_persona(self, persona_id: UUID, updates: dict[str, Any]) -> None:
        """Update persona fields."""
        async with self.transaction() as conn:
            # Build dynamic update query
            set_clauses = []
            params = []
            
            for key, value in updates.items():
                set_clauses.append(f"{key} = ?")
                if isinstance(value, (dict, list)):
                    params.append(json.dumps(value))
                elif isinstance(value, datetime):
                    params.append(value.isoformat())
                elif isinstance(value, UUID):
                    params.append(str(value))
                else:
                    params.append(value)
            
            set_clauses.append("updated_at = ?")
            params.append(datetime.utcnow().isoformat())
            params.append(str(persona_id))
            
            await conn.execute(
                f"UPDATE personas SET {', '.join(set_clauses)} WHERE id = ?",
                params
            )
            await self._log_action(conn, "persona_updated", str(persona_id), {"fields": list(updates.keys())})
    
    # =====================
    # Case Operations
    # =====================
    
    async def insert_case(self, case_data: dict[str, Any]) -> UUID:
        """Insert a new investigation case."""
        async with self.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO cases (
                    id, name, description, persona_ids, evidence_ids,
                    status, priority, analyst_id, team_ids,
                    created_at, updated_at, closed_at, action_log
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(case_data["id"]),
                    case_data["name"],
                    case_data["description"],
                    json.dumps([str(p) for p in case_data.get("persona_ids", [])]),
                    json.dumps([str(e) for e in case_data.get("evidence_ids", [])]),
                    case_data.get("status", "open"),
                    case_data.get("priority", "medium"),
                    case_data.get("analyst_id"),
                    json.dumps(case_data.get("team_ids", [])),
                    case_data.get("created_at", datetime.utcnow()).isoformat(),
                    case_data.get("updated_at", datetime.utcnow()).isoformat(),
                    case_data.get("closed_at", "").isoformat() if case_data.get("closed_at") else None,
                    json.dumps(case_data.get("action_log", [])),
                )
            )
            await self._log_action(conn, "case_created", str(case_data["id"]))
            return case_data["id"]
    
    async def get_case(self, case_id: UUID) -> Optional[dict[str, Any]]:
        """Retrieve a case by ID."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        
        cursor = await self._connection.execute(
            "SELECT * FROM cases WHERE id = ?",
            (str(case_id),)
        )
        row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None
    
    # =====================
    # Evidence Operations
    # =====================
    
    async def insert_evidence(self, evidence_data: dict[str, Any]) -> UUID:
        """Insert evidence package."""
        async with self.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO evidence (
                    id, case_id, persona_id, items, events,
                    indicators_of_compromise, threat_score, overall_confidence,
                    analyst_id, analyst_conclusions, analyst_annotations,
                    created_at, finalized_at, is_finalized
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(evidence_data["id"]),
                    str(evidence_data["case_id"]),
                    str(evidence_data.get("persona_id")) if evidence_data.get("persona_id") else None,
                    json.dumps([i.model_dump() if hasattr(i, 'model_dump') else i for i in evidence_data.get("items", [])]),
                    json.dumps(evidence_data.get("events", [])),
                    json.dumps([ioc.model_dump() if hasattr(ioc, 'model_dump') else ioc for ioc in evidence_data.get("indicators_of_compromise", [])]),
                    json.dumps(evidence_data.get("threat_score").model_dump() if evidence_data.get("threat_score") and hasattr(evidence_data.get("threat_score"), 'model_dump') else evidence_data.get("threat_score")),
                    json.dumps(evidence_data.get("overall_confidence").model_dump() if evidence_data.get("overall_confidence") and hasattr(evidence_data.get("overall_confidence"), 'model_dump') else evidence_data.get("overall_confidence")),
                    evidence_data.get("analyst_id"),
                    json.dumps(evidence_data.get("analyst_conclusions", [])),
                    json.dumps(evidence_data.get("analyst_annotations", {})),
                    evidence_data.get("created_at", datetime.utcnow()).isoformat(),
                    evidence_data.get("finalized_at", "").isoformat() if evidence_data.get("finalized_at") else None,
                    evidence_data.get("is_finalized", False),
                )
            )
            await self._log_action(conn, "evidence_created", str(evidence_data["id"]))
            return evidence_data["id"]
    
    # =====================
    # Audit Log
    # =====================
    
    async def _log_action(
        self,
        conn: aiosqlite.Connection,
        action: str,
        entity_id: str,
        details: Optional[dict[str, Any]] = None,
        analyst_id: Optional[str] = None,
    ) -> None:
        """Log an action for audit trail."""
        await conn.execute(
            """
            INSERT INTO audit_log (action, entity_id, details, analyst_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                action,
                entity_id,
                json.dumps(details or {}),
                analyst_id,
                datetime.utcnow().isoformat(),
            )
        )
    
    async def get_audit_log(
        self,
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit log with filters."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        
        query = "SELECT * FROM audit_log WHERE 1=1"
        params: list[Any] = []
        
        if entity_id:
            query += " AND entity_id = ?"
            params.append(entity_id)
        
        if action:
            query += " AND action = ?"
            params.append(action)
        
        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]
    
    # =====================
    # Utilities
    # =====================
    
    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
        """Convert a database row to dictionary."""
        result = dict(row)
        # Parse JSON fields
        for key in result:
            if isinstance(result[key], str):
                try:
                    if result[key].startswith('{') or result[key].startswith('['):
                        result[key] = json.loads(result[key])
                except (json.JSONDecodeError, AttributeError):
                    pass
        return result


# =====================
# Database Schema
# =====================

SCHEMA_SQL = """
-- Signals table
CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    source_url TEXT,
    source_name TEXT NOT NULL,
    raw_content TEXT NOT NULL,
    extracted_text TEXT,
    metadata TEXT DEFAULT '{}',
    discovered_at TEXT NOT NULL,
    content_timestamp TEXT,
    content_hash TEXT,
    is_processed INTEGER DEFAULT 0,
    processing_notes TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(type);
CREATE INDEX IF NOT EXISTS idx_signals_hash ON signals(content_hash);
CREATE INDEX IF NOT EXISTS idx_signals_discovered ON signals(discovered_at);

-- Personas table
CREATE TABLE IF NOT EXISTS personas (
    id TEXT PRIMARY KEY,
    case_id TEXT,
    primary_identifier TEXT NOT NULL,
    identifier_type TEXT NOT NULL,
    entities TEXT DEFAULT '[]',
    aliases TEXT DEFAULT '[]',
    signal_ids TEXT DEFAULT '[]',
    platforms_detected TEXT DEFAULT '[]',
    first_activity TEXT,
    last_activity TEXT,
    activity_count INTEGER DEFAULT 0,
    behavioral_fingerprint_id TEXT,
    threat_score TEXT,
    overall_confidence TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_active_watch INTEGER DEFAULT 0,
    analyst_notes TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_personas_identifier ON personas(primary_identifier);
CREATE INDEX IF NOT EXISTS idx_personas_case ON personas(case_id);
CREATE INDEX IF NOT EXISTS idx_personas_watch ON personas(is_active_watch);

-- Cases table
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    persona_ids TEXT DEFAULT '[]',
    evidence_ids TEXT DEFAULT '[]',
    status TEXT DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    analyst_id TEXT,
    team_ids TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    closed_at TEXT,
    action_log TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_analyst ON cases(analyst_id);

-- Evidence table
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    persona_id TEXT,
    items TEXT DEFAULT '[]',
    events TEXT DEFAULT '[]',
    indicators_of_compromise TEXT DEFAULT '[]',
    threat_score TEXT,
    overall_confidence TEXT,
    analyst_id TEXT,
    analyst_conclusions TEXT DEFAULT '[]',
    analyst_annotations TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    finalized_at TEXT,
    is_finalized INTEGER DEFAULT 0,
    FOREIGN KEY (case_id) REFERENCES cases(id)
);

CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_evidence_persona ON evidence(persona_id);

-- Behavioral fingerprints table
CREATE TABLE IF NOT EXISTS behavioral_fingerprints (
    id TEXT PRIMARY KEY,
    persona_id TEXT,
    vocabulary_fingerprint TEXT DEFAULT '[]',
    punctuation_pattern TEXT DEFAULT '{}',
    sentence_length_distribution TEXT DEFAULT '{}',
    active_hours TEXT DEFAULT '[]',
    active_days TEXT DEFAULT '[]',
    posting_frequency REAL DEFAULT 0.0,
    common_phrases TEXT DEFAULT '[]',
    topic_interests TEXT DEFAULT '[]',
    sample_count INTEGER DEFAULT 0,
    confidence TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (persona_id) REFERENCES personas(id)
);

CREATE INDEX IF NOT EXISTS idx_fingerprints_persona ON behavioral_fingerprints(persona_id);

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details TEXT DEFAULT '{}',
    analyst_id TEXT,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);

-- Watchers table (for real-time monitoring)
CREATE TABLE IF NOT EXISTS watchers (
    id TEXT PRIMARY KEY,
    persona_id TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    check_interval_seconds INTEGER DEFAULT 300,
    last_checked TEXT,
    next_check TEXT,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (persona_id) REFERENCES personas(id)
);

CREATE INDEX IF NOT EXISTS idx_watchers_active ON watchers(is_active);
CREATE INDEX IF NOT EXISTS idx_watchers_next ON watchers(next_check);
"""


# =====================
# Database Singleton
# =====================

_db_instance: Optional[Database] = None


async def get_database(db_path: str = "data/db/nciia.db") -> Database:
    """Get or create database singleton."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
        await _db_instance.connect()
    return _db_instance


async def close_database() -> None:
    """Close database connection."""
    global _db_instance
    if _db_instance:
        await _db_instance.disconnect()
        _db_instance = None

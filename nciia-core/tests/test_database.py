"""
Test Database Operations
"""

import pytest
import asyncio
from pathlib import Path
from uuid import uuid4

from nciia.db import Database
from nciia.models import Signal, SignalType, Persona, EntityType, Case


@pytest.fixture
async def db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    database = Database(db_path)
    await database.connect()
    yield database
    await database.disconnect()


class TestDatabase:
    """Test database operations."""
    
    @pytest.mark.asyncio
    async def test_connect_disconnect(self, tmp_path):
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        await db.connect()
        assert db._connection is not None
        await db.disconnect()
        assert db._connection is None
    
    @pytest.mark.asyncio
    async def test_insert_and_get_signal(self, db):
        signal = Signal(
            type=SignalType.PASTE_SITE,
            source_name="Test",
            raw_content="Test content",
        )
        
        await db.insert_signal(signal.model_dump())
        retrieved = await db.get_signal(signal.id)
        
        assert retrieved is not None
        assert retrieved["raw_content"] == "Test content"
    
    @pytest.mark.asyncio
    async def test_signal_deduplication(self, db):
        content = "Same content for dedup test"
        s1 = Signal(type=SignalType.WEB_CONTENT, source_name="A", raw_content=content)
        s2 = Signal(type=SignalType.WEB_CONTENT, source_name="B", raw_content=content)
        
        await db.insert_signal(s1.model_dump())
        
        existing = await db.get_signals_by_hash(s2.content_hash)
        assert len(existing) == 1
    
    @pytest.mark.asyncio
    async def test_insert_and_search_persona(self, db):
        persona = Persona(
            primary_identifier="testuser123",
            identifier_type=EntityType.USERNAME,
        )
        
        await db.insert_persona(persona.model_dump())
        
        results = await db.search_personas(identifier="testuser")
        assert len(results) >= 1
    
    @pytest.mark.asyncio
    async def test_case_operations(self, db):
        case = Case(name="Test Case", description="Test description")
        
        await db.insert_case(case.model_dump())
        retrieved = await db.get_case(case.id)
        
        assert retrieved is not None
        assert retrieved["name"] == "Test Case"
    
    @pytest.mark.asyncio
    async def test_audit_log(self, db):
        # Create a signal to generate audit log
        signal = Signal(
            type=SignalType.PASTE_SITE,
            source_name="Test",
            raw_content="Audit test",
        )
        await db.insert_signal(signal.model_dump())
        
        # Check audit log
        logs = await db.get_audit_log(entity_id=str(signal.id))
        assert len(logs) >= 1
        assert logs[0]["action"] == "signal_created"

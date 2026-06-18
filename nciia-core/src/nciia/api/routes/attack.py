"""API routes for MITRE ATT&CK tagging and navigator export."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from nciia.attack.tagger import tag_text, tag_signal, generate_navigator_layer, get_tactic_summary
from nciia.utils import get_logger

router = APIRouter()
logger = get_logger(__name__)


class TagTextRequest(BaseModel):
    text: str
    min_confidence: float = 0.1


@router.post("/tag")
async def tag_text_endpoint(req: TagTextRequest) -> dict[str, Any]:
    """Tag arbitrary text with MITRE ATT&CK techniques."""
    matches = tag_text(req.text, req.min_confidence)
    return {
        "input_length": len(req.text),
        "techniques_found": len(matches),
        "techniques": [
            {
                "technique_id": m.technique_id,
                "name": m.name,
                "tactic": m.tactic,
                "matched_keywords": m.matched_keywords,
                "confidence": m.confidence,
                "navigator_url": f"https://attack.mitre.org/techniques/{m.technique_id}/",
            }
            for m in matches
        ],
    }


@router.get("/signals/tagged")
async def get_tagged_signals(limit: int = 50) -> dict[str, Any]:
    """Return recent signals with ATT&CK tags and tactic summary."""
    try:
        from nciia.db import get_database
        import json

        db = await get_database()
        rows = await db._connection.execute_fetchall(
            "SELECT id, raw_content, extracted_text, source_name, metadata "
            "FROM signals ORDER BY created_at DESC LIMIT ?",
            (min(limit, 200),),
        )

        tagged: list[dict] = []
        tagged_for_summary: list[list[dict]] = []

        for row in rows:
            sig = {
                "id": str(row[0]),
                "raw_content": row[1] or "",
                "extracted_text": row[2],
                "source_name": row[3] or "",
                "metadata": json.loads(row[4]) if row[4] else {},
            }
            tags = tag_signal(sig)
            if tags:
                tagged.append({"signal_id": str(row[0]), "source": row[3], "techniques": tags})
                tagged_for_summary.append(tags)

        return {
            "total_signals": len(rows),
            "signals_with_techniques": len(tagged),
            "tactic_summary": get_tactic_summary(tagged_for_summary),
            "tagged_signals": tagged[:50],
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/navigator/layer")
async def get_navigator_layer(limit: int = 200) -> dict[str, Any]:
    """Generate ATT&CK Navigator layer from all recent signals."""
    try:
        from nciia.db import get_database
        import json

        db = await get_database()
        rows = await db._connection.execute_fetchall(
            "SELECT id, raw_content, extracted_text, source_name, metadata "
            "FROM signals ORDER BY created_at DESC LIMIT ?",
            (min(limit, 500),),
        )

        tagged_signals = []
        for row in rows:
            sig = {
                "id": str(row[0]),
                "raw_content": row[1] or "",
                "extracted_text": row[2],
                "source_name": row[3] or "",
                "metadata": json.loads(row[4]) if row[4] else {},
            }
            tags = tag_signal(sig)
            if tags:
                tagged_signals.append(tags)

        return generate_navigator_layer(tagged_signals)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/techniques")
async def list_techniques() -> dict[str, Any]:
    """List all indexed ATT&CK techniques."""
    from nciia.attack.tagger import ATTACK_TECHNIQUES
    from collections import defaultdict

    by_tactic: dict[str, list] = defaultdict(list)
    for tid, name, tactic, keywords in ATTACK_TECHNIQUES:
        by_tactic[tactic].append({
            "id": tid,
            "name": name,
            "keywords_count": len(keywords),
            "url": f"https://attack.mitre.org/techniques/{tid}/",
        })

    return {
        "total_techniques": len(ATTACK_TECHNIQUES),
        "total_tactics": len(by_tactic),
        "by_tactic": dict(by_tactic),
    }

"""
Streaming LLM Analyst — N-CIIA

Real Groq-powered analyst with RAG over the live SQLite database.
Returns token-by-token via Server-Sent Events (SSE).
Supports multi-turn memory and structured intelligence report generation.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator

from nciia.utils import get_logger, get_settings

logger = get_logger(__name__)


# ─── Session memory ───────────────────────────────────────────────────────────

class AnalystSession:
    MAX_TURNS = 20

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.history: list[dict] = []
        self.created_at = time.time()
        self.last_active = time.time()

    def add(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.MAX_TURNS * 2:
            # Keep system context + last N turns
            self.history = self.history[-self.MAX_TURNS * 2:]
        self.last_active = time.time()

    def messages(self, system_prompt: str) -> list[dict]:
        return [{"role": "system", "content": system_prompt}] + self.history


_sessions: dict[str, AnalystSession] = {}

def get_session(session_id: str) -> AnalystSession:
    if session_id not in _sessions:
        _sessions[session_id] = AnalystSession(session_id)
    return _sessions[session_id]

def new_session() -> str:
    sid = str(uuid.uuid4())
    _sessions[sid] = AnalystSession(sid)
    return sid


# ─── RAG context fetcher ──────────────────────────────────────────────────────

async def build_rag_context(query: str) -> str:
    """
    Retrieve relevant live data from the database to ground the LLM's response.
    Returns a formatted context block injected into the system prompt.
    """
    context_parts: list[str] = []

    try:
        from nciia.db import get_database
        db = await get_database()
        conn = db._connection

        # Recent unprocessed signals
        signals = await conn.execute_fetchall(
            "SELECT source_name, raw_content, discovered_at FROM signals "
            "ORDER BY discovered_at DESC LIMIT 10"
        )
        if signals:
            context_parts.append("## Recent Intelligence Signals (last 10)")
            for row in signals:
                content = (row[1] or "")[:200]
                context_parts.append(f"- [{row[2][:10]}] {row[0]}: {content}")

        # High-risk personas
        personas = await conn.execute_fetchall(
            "SELECT primary_identifier, identifier_type, platforms_detected, activity_count "
            "FROM personas WHERE is_active_watch = 1 ORDER BY updated_at DESC LIMIT 5"
        )
        if personas:
            context_parts.append("\n## Active Watch Personas (top 5)")
            for row in personas:
                platforms = json.loads(row[2]) if row[2] else []
                context_parts.append(
                    f"- {row[0]} ({row[1]}) | Platforms: {', '.join(platforms[:3])} | "
                    f"Activity: {row[3]}"
                )

        # Open cases
        cases = await conn.execute_fetchall(
            "SELECT name, status, priority, description FROM cases "
            "WHERE status IN ('open','active') ORDER BY updated_at DESC LIMIT 5"
        )
        if cases:
            context_parts.append("\n## Active Cases")
            for row in cases:
                context_parts.append(f"- [{row[2].upper()}] {row[0]} ({row[1]}): {(row[3] or '')[:100]}")

        # Recent alerts
        alerts_rows = await conn.execute_fetchall(
            "SELECT source_name, extracted_text, discovered_at FROM signals "
            "WHERE is_processed = 0 ORDER BY discovered_at DESC LIMIT 5"
        )
        if alerts_rows:
            context_parts.append("\n## Unprocessed Alerts")
            for row in alerts_rows:
                text = (row[1] or row[0])[:120]
                context_parts.append(f"- {row[2][:16]}: {text}")

    except Exception as exc:
        logger.warning("rag_fetch_failed", error=str(exc))
        context_parts.append("(Live database context unavailable)")

    return "\n".join(context_parts) if context_parts else "No live data available."


# ─── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """You are ARIA — Advanced Reconnaissance Intelligence Analyst, the AI core of the N-CIIA (National Cyber Investigation & Intelligence Assistant) platform.

You are a world-class cyber threat intelligence analyst with expertise in:
- OSINT (Open Source Intelligence)
- MITRE ATT&CK framework
- Malware analysis and reverse engineering
- Digital forensics and incident response (DFIR)
- Dark web monitoring and persona attribution
- Network intelligence (BGP, ASN, passive DNS)
- Threat actor profiling and attribution

## Current Live Intelligence Context
{rag_context}

## Your Capabilities
1. Analyze signals and personas from the live database above
2. Generate structured threat intelligence reports (STIX 2.1 compatible)
3. Map observed TTPs to MITRE ATT&CK techniques
4. Recommend investigation pivots and next steps
5. Draft takedown requests, IOC lists, and analyst summaries
6. Correlate cross-platform digital footprints

## Response Format
- Use markdown formatting for reports
- Be precise, actionable, and evidence-based
- Always cite which data from the context informed your answer
- Flag when you lack sufficient data to make a confident assessment
- For IOC lists, use code blocks with one IOC per line

Current time: {timestamp}
Platform: N-CIIA v1.0.0 | Analyst: Authenticated
"""


# ─── Streaming response ───────────────────────────────────────────────────────

async def stream_analyst_response(
    question: str,
    session_id: str,
) -> AsyncIterator[str]:
    """
    Streams SSE-formatted tokens from the LLM.
    Each yielded string is a complete SSE 'data:' line.
    """
    settings = get_settings()

    # Build RAG context
    rag_context = await build_rag_context(question)
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        rag_context=rag_context,
        timestamp=timestamp,
    )

    session = get_session(session_id)
    session.add("user", question)

    messages = session.messages(system_prompt)

    # Try Groq first, fall back to OpenAI-compatible
    api_key = getattr(settings, "llm_api_key", None) or \
              __import__("os").environ.get("NCIIA_LLM_API_KEY", "")
    provider = getattr(settings, "llm_provider", "groq") or \
               __import__("os").environ.get("NCIIA_LLM_PROVIDER", "groq")

    if not api_key:
        yield 'data: {"error": "LLM API key not configured. Set NCIIA_LLM_API_KEY in .env"}\n\n'
        return

    if provider == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        model = "llama-3.3-70b-versatile"
    elif provider == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        model = "gpt-4o"
    else:
        url = f"{__import__('os').environ.get('NCIIA_LLM_BASE_URL', 'http://localhost:11434')}/v1/chat/completions"
        model = __import__("os").environ.get("NCIIA_LLM_MODEL", "llama3")

    import aiohttp

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 2048,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    full_response = ""
    timeout = aiohttp.ClientTimeout(total=120, connect=10)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as client:
            async with client.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    yield f'data: {{"error": "LLM API error {resp.status}: {body[:200]}"}}\n\n'
                    return

                async for raw_line in resp.content:
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line.startswith("data:"):
                        continue
                    chunk_str = line[5:].strip()
                    if chunk_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(chunk_str)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            full_response += delta
                            safe = json.dumps({"token": delta})
                            yield f"data: {safe}\n\n"
                    except Exception:
                        continue

    except aiohttp.ClientError as exc:
        yield f'data: {{"error": "Connection failed: {exc}"}}\n\n'
        return

    # Save full response to session
    if full_response:
        session.add("assistant", full_response)
        logger.info("analyst_response_complete",
                    session_id=session_id,
                    tokens_approx=len(full_response.split()))

    yield 'data: {"done": true}\n\n'


async def generate_report(
    report_type: str,
    target_id: str,
    target_type: str,
) -> str:
    """Generate a full intelligence report (non-streaming)."""
    prompts = {
        "threat_intel": (
            f"Generate a comprehensive threat intelligence report for {target_type} '{target_id}'. "
            "Include: Executive Summary, Key Findings, TTPs mapped to MITRE ATT&CK, "
            "IOC List, Attribution Assessment, and Recommended Actions. "
            "Format as professional markdown."
        ),
        "persona_profile": (
            f"Generate a complete persona profile report for '{target_id}'. "
            "Include: Identity Assessment, Platform Footprint, Behavioral Analysis, "
            "Threat Level Justification, Linked IOCs, and Investigation Recommendations."
        ),
        "incident": (
            f"Generate an incident response report for case '{target_id}'. "
            "Include: Timeline, Affected Systems, Attack Vector, TTPs, "
            "Containment Actions Taken, and Lessons Learned."
        ),
    }

    question = prompts.get(report_type, f"Generate a detailed report about {target_id}")
    sid = new_session()
    full = ""
    async for chunk in stream_analyst_response(question, sid):
        if chunk.startswith("data:"):
            try:
                data = json.loads(chunk[5:].strip())
                if "token" in data:
                    full += data["token"]
            except Exception:
                pass
    return full

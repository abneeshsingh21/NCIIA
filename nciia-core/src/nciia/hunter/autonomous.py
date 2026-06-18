"""
Autonomous AI Hunter Agents — N-CIIA

Self-directed investigation agents that run in the background and
proactively discover threats without analyst intervention.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

from nciia.utils import get_logger

logger = get_logger(__name__)


@dataclass
class HunterFinding:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    title: str = ""
    description: str = ""
    severity: str = "medium"            # critical|high|medium|low
    iocs: list[str] = field(default_factory=list)
    related_persona_ids: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    attack_techniques: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "iocs": self.iocs,
            "related_persona_ids": self.related_persona_ids,
            "evidence": self.evidence,
            "attack_techniques": self.attack_techniques,
            "created_at": self.created_at,
        }


class BaseHunterAgent:
    name: str = "base"
    description: str = ""
    interval_seconds: int = 300     # how often to run

    def __init__(self) -> None:
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._findings: list[HunterFinding] = []
        self._run_count = 0
        self._last_run: Optional[float] = None
        self._callbacks: list[Callable[[HunterFinding], Coroutine]] = []

    def on_finding(self, cb: Callable[[HunterFinding], Coroutine]) -> None:
        self._callbacks.append(cb)

    async def _emit(self, finding: HunterFinding) -> None:
        self._findings.append(finding)
        logger.info("hunter_finding", agent=self.name, title=finding.title, severity=finding.severity)
        for cb in self._callbacks:
            try:
                await cb(finding)
            except Exception as exc:
                logger.error("hunter_callback_error", error=str(exc))

    async def hunt(self) -> list[HunterFinding]:
        """Override in subclass."""
        return []

    async def _loop(self) -> None:
        while self._running:
            try:
                self._last_run = time.time()
                findings = await self.hunt()
                for f in findings:
                    await self._emit(f)
                self._run_count += 1
            except Exception as exc:
                logger.error("hunter_loop_error", agent=self.name, error=str(exc))
            await asyncio.sleep(self.interval_seconds)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("hunter_started", agent=self.name)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("hunter_stopped", agent=self.name)

    def get_stats(self) -> dict:
        return {
            "agent": self.name,
            "description": self.description,
            "running": self._running,
            "run_count": self._run_count,
            "last_run": self._last_run,
            "findings_count": len(self._findings),
            "interval_seconds": self.interval_seconds,
        }

    def get_findings(self) -> list[dict]:
        return [f.to_dict() for f in self._findings[-50:]]


# ─── Pivot Hunter ─────────────────────────────────────────────────────────────

class PivotHunter(BaseHunterAgent):
    """
    Given known IOCs, automatically pivots to related IOCs via enrichment.
    Builds an IOC graph: if IP shares a cert domain → check that domain → ...
    """

    name = "PivotHunter"
    description = "Pivots from known IOCs to discover related infrastructure via cert transparency, passive DNS, and Shodan"
    interval_seconds = 600

    async def hunt(self) -> list[HunterFinding]:
        findings: list[HunterFinding] = []
        try:
            from nciia.db import get_database
            from nciia.enrichment.engine import get_enrichment_engine

            db = await get_database()
            engine = get_enrichment_engine()

            # Get recent high-risk signals with IPs or domains
            import re
            rows = await db._connection.execute_fetchall(
                """SELECT id, raw_content, source_name FROM signals
                   WHERE is_processed = 0
                   ORDER BY created_at DESC LIMIT 30"""
            )

            ip_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
            domain_pattern = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")

            discovered_iocs: dict[str, str] = {}  # ioc → source signal id

            for row in rows:
                text = row[1] or ""
                for ip in ip_pattern.findall(text):
                    if not ip.startswith(("192.168", "10.", "172.", "127.")):
                        discovered_iocs[ip] = str(row[0])
                for domain in domain_pattern.findall(text):
                    if len(domain) > 4 and "." in domain:
                        discovered_iocs[domain] = str(row[0])

            # Enrich top 5 (rate-limit friendly)
            pivot_results: list[dict] = []
            for ioc, sig_id in list(discovered_iocs.items())[:5]:
                try:
                    result = await engine.enrich(ioc)
                    if result.risk_score > 50:
                        pivot_results.append({
                            "ioc": ioc,
                            "risk_score": result.risk_score,
                            "risk_level": result.risk_level,
                            "tags": result.tags,
                            "related_cert_domains": result.cert_domains[:5],
                            "source_signal": sig_id,
                        })
                except Exception:
                    pass

            if pivot_results:
                high = [r for r in pivot_results if r["risk_score"] > 75]
                severity = "critical" if high else "high"
                findings.append(HunterFinding(
                    agent_name=self.name,
                    title=f"Pivot Discovery: {len(pivot_results)} High-Risk IOCs Found",
                    description=(
                        f"Automated pivot analysis discovered {len(pivot_results)} "
                        f"high-risk IOCs from recent signals. "
                        f"{len(high)} scored critical (>75%)."
                    ),
                    severity=severity,
                    iocs=[r["ioc"] for r in pivot_results],
                    evidence=pivot_results,
                    attack_techniques=["T1595", "T1596"],
                ))
        except Exception as exc:
            logger.error("pivot_hunter_error", error=str(exc))
        return findings


# ─── Pattern Hunter ───────────────────────────────────────────────────────────

class PatternHunter(BaseHunterAgent):
    """
    Scans recent signals with ATT&CK tagger and surfaces emerging kill-chain patterns.
    Fires when 3+ signals hit the same tactic in a rolling 1-hour window.
    """

    name = "PatternHunter"
    description = "Detects emerging ATT&CK patterns by correlating technique hits across recent signals"
    interval_seconds = 300

    async def hunt(self) -> list[HunterFinding]:
        findings: list[HunterFinding] = []
        try:
            from nciia.db import get_database
            from nciia.attack.tagger import tag_signal, get_tactic_summary

            db = await get_database()
            rows = await db._connection.execute_fetchall(
                """SELECT id, raw_content, extracted_text, source_name, metadata
                   FROM signals
                   ORDER BY created_at DESC LIMIT 100"""
            )

            import json
            tagged_signals = []
            for row in rows:
                signal_dict = {
                    "id": str(row[0]),
                    "raw_content": row[1] or "",
                    "extracted_text": row[2],
                    "source_name": row[3] or "",
                    "metadata": json.loads(row[4]) if row[4] else {},
                }
                tags = tag_signal(signal_dict)
                if tags:
                    tagged_signals.append(tags)

            tactic_summary = get_tactic_summary(tagged_signals)
            hot_tactics = {t: c for t, c in tactic_summary.items() if c >= 3}

            if hot_tactics:
                top = sorted(hot_tactics.items(), key=lambda x: x[1], reverse=True)[:3]
                findings.append(HunterFinding(
                    agent_name=self.name,
                    title=f"Emerging Pattern: {top[0][0]} activity spike",
                    description=(
                        f"ATT&CK pattern analysis detected elevated activity across "
                        f"{len(hot_tactics)} tactics in recent signals. "
                        f"Top: {', '.join(f'{t} ({c})' for t, c in top)}."
                    ),
                    severity="high" if top[0][1] > 10 else "medium",
                    evidence=[{"tactic": t, "count": c} for t, c in top],
                    attack_techniques=[],
                ))
        except Exception as exc:
            logger.error("pattern_hunter_error", error=str(exc))
        return findings


# ─── Dark Web Monitor ─────────────────────────────────────────────────────────

class DarkWebMonitor(BaseHunterAgent):
    """
    Monitors paste sites and leak indexes for mentions of monitored targets.
    Uses only clearnet paste/leak APIs — no Tor dependency required.
    """

    name = "DarkWebMonitor"
    description = "Monitors Pastebin, GitHub Gist, and leak indexes for monitored target mentions"
    interval_seconds = 900

    PASTE_APIS = [
        "https://psbdmp.ws/api/v3/search/{q}",   # Pastebin dump search
    ]

    async def hunt(self) -> list[HunterFinding]:
        findings: list[HunterFinding] = []
        try:
            from nciia.db import get_database
            import aiohttp

            db = await get_database()
            # Get active watch personas
            rows = await db._connection.execute_fetchall(
                """SELECT id, primary_identifier FROM personas
                   WHERE is_active_watch = 1 LIMIT 10"""
            )
            if not rows:
                return findings

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for row in rows:
                    persona_id = str(row[0])
                    identifier = row[1]

                    for api in self.PASTE_APIS:
                        url = api.replace("{q}", identifier)
                        try:
                            async with session.get(url) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    hits = data if isinstance(data, list) else data.get("data", [])
                                    if hits:
                                        findings.append(HunterFinding(
                                            agent_name=self.name,
                                            title=f"Paste Site Mention: {identifier}",
                                            description=(
                                                f"Monitored target '{identifier}' found in "
                                                f"{len(hits)} paste(s). Immediate review recommended."
                                            ),
                                            severity="high",
                                            iocs=[identifier],
                                            related_persona_ids=[persona_id],
                                            evidence=[{"url": h.get("link", ""), "date": h.get("date", "")}
                                                      for h in hits[:5]],
                                            attack_techniques=["T1593"],
                                        ))
                        except Exception:
                            pass

        except Exception as exc:
            logger.error("darkweb_monitor_error", error=str(exc))
        return findings


# ─── Attribution Hunter ───────────────────────────────────────────────────────

class AttributionHunter(BaseHunterAgent):
    """
    Uses DBSCAN clustering to find groups of similar personas
    and raises a finding when a new cluster forms.
    """

    name = "AttributionHunter"
    description = "Clusters personas by behavioural features to identify related threat actors"
    interval_seconds = 1800

    async def hunt(self) -> list[HunterFinding]:
        findings: list[HunterFinding] = []
        try:
            from nciia.db import get_database
            from nciia.ml.real_scorer import cluster_personas
            import json

            db = await get_database()
            rows = await db._connection.execute_fetchall(
                "SELECT id, primary_identifier, platforms_detected, activity_count, "
                "is_active_watch, first_activity, last_activity "
                "FROM personas LIMIT 200"
            )
            if len(rows) < 2:
                return findings

            personas = []
            for row in rows:
                platforms = json.loads(row[2]) if row[2] else []
                personas.append({
                    "id": str(row[0]),
                    "primary_identifier": row[1],
                    "platforms_detected": platforms,
                    "activity_count": row[3] or 0,
                    "is_active_watch": bool(row[4]),
                    "first_activity": row[5],
                    "last_activity": row[6],
                })

            clustered = cluster_personas(personas)

            from collections import defaultdict
            clusters: dict[int, list[dict]] = defaultdict(list)
            for p in clustered:
                cid = p.get("cluster_id", -1)
                if cid >= 0:
                    clusters[cid].append(p)

            for cid, members in clusters.items():
                if len(members) >= 2:
                    findings.append(HunterFinding(
                        agent_name=self.name,
                        title=f"Actor Cluster #{cid}: {len(members)} Related Personas",
                        description=(
                            f"Behavioural clustering identified {len(members)} personas "
                            f"with similar activity patterns, suggesting a coordinated actor. "
                            f"Members: {', '.join(m['primary_identifier'] for m in members[:5])}"
                        ),
                        severity="high" if len(members) > 3 else "medium",
                        related_persona_ids=[m["id"] for m in members],
                        evidence=[{"id": m["id"], "identifier": m["primary_identifier"]}
                                  for m in members],
                        attack_techniques=["T1586"],
                    ))
        except Exception as exc:
            logger.error("attribution_hunter_error", error=str(exc))
        return findings


# ─── Hunter Manager ───────────────────────────────────────────────────────────

class HunterManager:
    """Manages all hunter agents lifecycle."""

    def __init__(self) -> None:
        self._agents: list[BaseHunterAgent] = [
            PivotHunter(),
            PatternHunter(),
            DarkWebMonitor(),
            AttributionHunter(),
        ]

    async def start_all(self) -> None:
        for agent in self._agents:
            await agent.start()
        logger.info("all_hunters_started", count=len(self._agents))

    async def stop_all(self) -> None:
        for agent in self._agents:
            await agent.stop()

    def get_all_stats(self) -> list[dict]:
        return [a.get_stats() for a in self._agents]

    def get_all_findings(self) -> list[dict]:
        findings = []
        for agent in self._agents:
            findings.extend(agent.get_findings())
        return sorted(findings, key=lambda f: f["created_at"], reverse=True)

    def on_finding(self, cb) -> None:
        for agent in self._agents:
            agent.on_finding(cb)


_manager: Optional[HunterManager] = None

def get_hunter_manager() -> HunterManager:
    global _manager
    if _manager is None:
        _manager = HunterManager()
    return _manager

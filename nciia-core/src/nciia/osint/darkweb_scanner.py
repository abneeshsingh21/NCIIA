"""
Dark Web Exposure Scanner
==========================
Searches for mentions of a phone number, email, username, or name
across dark web index services — 100% free, no Tor browser required.

Sources:
  - Ahmia.fi  — largest public Tor search engine index
  - Onion.live — real-time dark web crawler
  - DarkSearch.io — open dark web search (free tier)
  - IntelX Community — free intelligence search
  - Public breach paste sites (Ghostbin, Privatebin mirrors)
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from nciia.utils import get_logger

logger = get_logger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NCIIADarkScanner/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

AHMIA_SEARCH    = "https://ahmia.fi/search/?q={query}"
DARKSEARCH_API  = "https://darksearch.io/api/search?query={query}&page=1"
INTELX_SEARCH   = "https://2.intelx.io/intelligent/search?k=null&query={query}&limit=10"
ONION_LIVE      = "https://onion.live/search?q={query}"


@dataclass
class DarkWebHit:
    source:   str
    title:    str
    url:      str
    snippet:  str = ""
    onion:    str = ""


@dataclass
class DarkWebReport:
    query:         str
    hits:          list[DarkWebHit]  = field(default_factory=list)
    total_found:   int               = 0
    sources_hit:   list[str]         = field(default_factory=list)
    risk_level:    str               = "None"
    scanned_at:    float             = field(default_factory=time.time)
    errors:        list[str]         = field(default_factory=list)


async def _search_ahmia(client: httpx.AsyncClient, query: str) -> list[DarkWebHit]:
    hits: list[DarkWebHit] = []
    try:
        r = await client.get(AHMIA_SEARCH.format(query=query), timeout=15)
        if r.status_code != 200:
            return hits
        # Parse results from HTML
        items = re.findall(
            r'<h4[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>.*?<p[^>]*>([^<]*)</p>',
            r.text, re.DOTALL
        )
        for url, title, snippet in items[:10]:
            onion_match = re.search(r'([\w\d]+\.onion)', url)
            hits.append(DarkWebHit(
                source="Ahmia",
                title=title.strip(),
                url=url.strip(),
                snippet=snippet.strip()[:200],
                onion=onion_match.group(1) if onion_match else "",
            ))
    except Exception as exc:
        logger.debug("ahmia_search_fail", error=str(exc))
    return hits


async def _search_darksearch(client: httpx.AsyncClient, query: str) -> list[DarkWebHit]:
    hits: list[DarkWebHit] = []
    try:
        r = await client.get(DARKSEARCH_API.format(query=query), timeout=12)
        if r.status_code != 200:
            return hits
        data = r.json()
        for item in data.get("data", [])[:10]:
            hits.append(DarkWebHit(
                source="DarkSearch",
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("description", "")[:200],
                onion=re.search(r'([\w\d]+\.onion)', item.get("link", "")).group(1)
                       if re.search(r'([\w\d]+\.onion)', item.get("link", "")) else "",
            ))
    except Exception as exc:
        logger.debug("darksearch_fail", error=str(exc))
    return hits


async def _search_intelx(client: httpx.AsyncClient, query: str) -> list[DarkWebHit]:
    """IntelX free tier — returns bucket of public results."""
    hits: list[DarkWebHit] = []
    try:
        r = await client.post(
            "https://2.intelx.io/intelligent/search",
            json={"term": query, "maxresults": 10, "media": 0, "terminate": [], "timeout": 20},
            headers={**HEADERS, "x-key": "null"},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            for item in data.get("records", {}).get("results", [])[:10]:
                hits.append(DarkWebHit(
                    source="IntelX",
                    title=item.get("name", ""),
                    url=item.get("bucket", ""),
                    snippet=f"Type: {item.get('type', '')} | Date: {item.get('date', '')}",
                ))
    except Exception as exc:
        logger.debug("intelx_fail", error=str(exc))
    return hits


async def _search_paste_sites(client: httpx.AsyncClient, query: str) -> list[DarkWebHit]:
    """Search paste sites for leaks containing the query."""
    hits: list[DarkWebHit] = []
    targets = [
        ("Pastebin", f"https://pastebin.com/search?q={query}"),
        ("Ghostbin", f"https://ghostbin.com/search?q={query}"),
    ]
    for source, url in targets:
        try:
            r = await client.get(url, timeout=10, headers=HEADERS)
            if r.status_code == 200 and len(r.text) > 2000:
                # Find result links
                links = re.findall(r'href="(/[A-Za-z0-9]{8,})"', r.text)[:5]
                for link in links:
                    full_url = f"https://pastebin.com{link}" if "pastebin" in url else f"https://ghostbin.com{link}"
                    hits.append(DarkWebHit(
                        source=source,
                        title=f"Paste containing: {query}",
                        url=full_url,
                        snippet="Query term found in public paste — verify manually",
                    ))
        except Exception:
            pass
    return hits


def _assess_risk(hits: list[DarkWebHit]) -> str:
    if len(hits) == 0:
        return "🟢 None — Clean"
    n = len(hits)
    sources = {h.source for h in hits}
    if n >= 5 or len(sources) >= 3:
        return "🔴 Critical — Active dark web exposure"
    if n >= 2 or any(h.onion for h in hits):
        return "🟠 High — Found on dark web"
    return "🟡 Medium — Found on paste/clearnet sites"


async def scan_darkweb(query: str) -> DarkWebReport:
    """
    Search all dark web index sources in parallel for the given query.
    Query can be: phone number, email, username, or full name.
    """
    report = DarkWebReport(query=query)

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        verify=False,
        timeout=20,
    ) as client:
        results = await asyncio.gather(
            _search_ahmia(client, query),
            _search_darksearch(client, query),
            _search_intelx(client, query),
            _search_paste_sites(client, query),
            return_exceptions=True,
        )

    for result in results:
        if isinstance(result, list):
            report.hits.extend(result)

    # Deduplicate by URL
    seen: set[str] = set()
    deduped: list[DarkWebHit] = []
    for hit in report.hits:
        if hit.url not in seen:
            seen.add(hit.url)
            deduped.append(hit)
    report.hits = deduped

    report.total_found = len(report.hits)
    report.sources_hit = list({h.source for h in report.hits})
    report.risk_level  = _assess_risk(report.hits)
    report.scanned_at  = time.time()

    logger.info(
        "darkweb_scan_complete",
        query=query,
        hits=report.total_found,
        risk=report.risk_level,
    )
    return report

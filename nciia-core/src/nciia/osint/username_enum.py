"""
Cross-Platform Identity Enumeration Engine — N-CIIA

Probes 100+ platforms to discover an actor's digital footprint
from a single username, email, or real name seed.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

import aiohttp

from nciia.utils import get_logger

logger = get_logger(__name__)

# ─── Platform definitions ─────────────────────────────────────────────────────
# Format: (platform_name, url_template, success_code_or_text, category)

PLATFORMS = [
    # Social
    ("Twitter/X",    "https://twitter.com/{u}",                   200, "social"),
    ("Instagram",    "https://www.instagram.com/{u}/",            200, "social"),
    ("TikTok",       "https://www.tiktok.com/@{u}",               200, "social"),
    ("Facebook",     "https://www.facebook.com/{u}",              200, "social"),
    ("LinkedIn",     "https://www.linkedin.com/in/{u}",           200, "professional"),
    ("Snapchat",     "https://www.snapchat.com/add/{u}",          200, "social"),
    ("Pinterest",    "https://www.pinterest.com/{u}/",            200, "social"),
    ("Tumblr",       "https://{u}.tumblr.com",                    200, "social"),
    ("Flickr",       "https://www.flickr.com/people/{u}",         200, "social"),
    ("Twitch",       "https://www.twitch.tv/{u}",                 200, "streaming"),
    ("YouTube",      "https://www.youtube.com/@{u}",              200, "streaming"),
    ("Vimeo",        "https://vimeo.com/{u}",                     200, "streaming"),
    ("Dailymotion",  "https://www.dailymotion.com/{u}",           200, "streaming"),
    # Tech
    ("GitHub",       "https://github.com/{u}",                    200, "tech"),
    ("GitLab",       "https://gitlab.com/{u}",                    200, "tech"),
    ("Bitbucket",    "https://bitbucket.org/{u}/",                200, "tech"),
    ("StackOverflow","https://stackoverflow.com/users/login?ssrc=head", 200, "tech"),
    ("HackerNews",   "https://news.ycombinator.com/user?id={u}", 200, "tech"),
    ("Dev.to",       "https://dev.to/{u}",                        200, "tech"),
    ("Codepen",      "https://codepen.io/{u}",                    200, "tech"),
    ("npm",          "https://www.npmjs.com/~{u}",                200, "tech"),
    ("PyPI",         "https://pypi.org/user/{u}/",                200, "tech"),
    ("Docker Hub",   "https://hub.docker.com/u/{u}",              200, "tech"),
    # Gaming
    ("Steam",        "https://steamcommunity.com/id/{u}",         200, "gaming"),
    ("Xbox",         "https://www.xbox.com/en-US/play/user/{u}",  200, "gaming"),
    ("PSN",          "https://psnprofiles.com/{u}",               200, "gaming"),
    ("Roblox",       "https://www.roblox.com/user.aspx?username={u}", 200, "gaming"),
    # Forums/Communities
    ("Reddit",       "https://www.reddit.com/user/{u}",           200, "forum"),
    ("Quora",        "https://www.quora.com/profile/{u}",         200, "forum"),
    ("Medium",       "https://medium.com/@{u}",                   200, "blog"),
    ("Substack",     "https://{u}.substack.com",                  200, "blog"),
    ("Patreon",      "https://www.patreon.com/{u}",               200, "creative"),
    ("Behance",      "https://www.behance.net/{u}",               200, "creative"),
    ("Dribbble",     "https://dribbble.com/{u}",                  200, "creative"),
    ("ArtStation",   "https://www.artstation.com/{u}",            200, "creative"),
    # Messaging
    ("Telegram",     "https://t.me/{u}",                          200, "messaging"),
    ("Signal",       "https://signal.me/#p/{u}",                  200, "messaging"),
    # Professional
    ("AngelList",    "https://angel.co/u/{u}",                    200, "professional"),
    ("ProductHunt",  "https://www.producthunt.com/@{u}",          200, "professional"),
    # Crypto/Financial
    ("Etherscan",    "https://etherscan.io/address/{u}",          200, "crypto"),
    ("Bitcointalk",  "https://bitcointalk.org/index.php?action=profile;u=1", 200, "crypto"),
    # OSINT-relevant
    ("Pastebin",     "https://pastebin.com/u/{u}",                200, "paste"),
    ("Keybase",      "https://keybase.io/{u}",                    200, "identity"),
    ("Gravatar",     "https://en.gravatar.com/{u}",               200, "identity"),
    ("About.me",     "https://about.me/{u}",                      200, "identity"),
    ("Linktree",     "https://linktr.ee/{u}",                     200, "social"),
]


@dataclass
class PlatformResult:
    platform: str
    url: str
    found: bool
    status_code: int
    response_time_ms: int
    category: str
    error: Optional[str] = None


@dataclass
class EnumerationReport:
    query: str
    query_type: str                         # username | email | hash
    started_at: float = field(default_factory=time.time)
    duration_ms: int = 0
    found_on: list[PlatformResult] = field(default_factory=list)
    not_found_on: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    email_hash_md5: str = ""
    email_hash_sha256: str = ""
    gravatar_url: str = ""

    def to_dict(self):
        d = asdict(self)
        d["total_found"] = len(self.found_on)
        d["total_checked"] = len(self.found_on) + len(self.not_found_on)
        d["categories"] = {}
        for r in self.found_on:
            d["categories"].setdefault(r["category"], []).append(r["platform"])
        return d


class UsernameEnumerator:
    """
    Probes platforms in parallel with rate limiting.
    Uses realistic browser headers to avoid bot detection.
    """

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)
    CONCURRENCY = 25  # max parallel requests

    async def enumerate(self, query: str) -> EnumerationReport:
        """Probe all platforms for the given username/email."""
        start = time.time()
        query = query.strip()

        # Determine query type
        if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", query):
            q_type = "email"
            username = query.split("@")[0]
            md5_hash = hashlib.md5(query.lower().encode()).hexdigest()
            sha256_hash = hashlib.sha256(query.lower().encode()).hexdigest()
        else:
            q_type = "username"
            username = query
            md5_hash = ""
            sha256_hash = ""

        report = EnumerationReport(
            query=query,
            query_type=q_type,
            email_hash_md5=md5_hash,
            email_hash_sha256=sha256_hash,
            gravatar_url=f"https://www.gravatar.com/avatar/{md5_hash}?d=404" if md5_hash else "",
        )

        sem = asyncio.Semaphore(self.CONCURRENCY)
        connector = aiohttp.TCPConnector(ssl=False, limit=self.CONCURRENCY)

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=self.TIMEOUT,
            headers=self.HEADERS,
        ) as session:
            tasks = [
                self._probe(session, sem, username, name, url_tmpl, code, cat, report)
                for name, url_tmpl, code, cat in PLATFORMS
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        report.duration_ms = int((time.time() - start) * 1000)
        report.found_on.sort(key=lambda r: r.platform)

        logger.info(
            "enumeration_complete",
            query=query,
            found=len(report.found_on),
            checked=len(PLATFORMS),
            duration_ms=report.duration_ms,
        )
        return report

    async def _probe(
        self,
        session: aiohttp.ClientSession,
        sem: asyncio.Semaphore,
        username: str,
        platform: str,
        url_tmpl: str,
        expected_code: int,
        category: str,
        report: EnumerationReport,
    ) -> None:
        url = url_tmpl.replace("{u}", username)
        t0 = time.time()

        async with sem:
            try:
                async with session.get(
                    url,
                    allow_redirects=True,
                    max_redirects=3,
                ) as resp:
                    elapsed = int((time.time() - t0) * 1000)
                    found = (resp.status == expected_code)

                    if found:
                        report.found_on.append(PlatformResult(
                            platform=platform,
                            url=str(resp.url),
                            found=True,
                            status_code=resp.status,
                            response_time_ms=elapsed,
                            category=category,
                        ))
                    else:
                        report.not_found_on.append(platform)

            except asyncio.TimeoutError:
                report.errors.append(f"{platform}: timeout")
            except Exception as exc:
                report.errors.append(f"{platform}: {type(exc).__name__}")


# ─── Singleton ────────────────────────────────────────────────────────────────

_enumerator: Optional[UsernameEnumerator] = None

def get_enumerator() -> UsernameEnumerator:
    global _enumerator
    if _enumerator is None:
        _enumerator = UsernameEnumerator()
    return _enumerator

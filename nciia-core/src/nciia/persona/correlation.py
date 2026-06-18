"""
Platform Correlation for Persona Reconstruction

Maps and correlates identities across different platforms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

import structlog

from nciia.models import Entity, EntityType, Confidence

logger = structlog.get_logger(__name__)


@dataclass
class PlatformProfile:
    """A detected presence on a specific platform."""
    
    platform: str
    identifier: str
    profile_url: Optional[str] = None
    confidence: float = 0.5
    verified: bool = False
    metadata: dict = field(default_factory=dict)


# Known platform URL patterns
PLATFORM_PATTERNS = {
    "twitter": [
        r"twitter\.com/([a-zA-Z0-9_]+)",
        r"x\.com/([a-zA-Z0-9_]+)",
    ],
    "github": [
        r"github\.com/([a-zA-Z0-9-]+)",
    ],
    "linkedin": [
        r"linkedin\.com/in/([a-zA-Z0-9-]+)",
    ],
    "instagram": [
        r"instagram\.com/([a-zA-Z0-9_.]+)",
    ],
    "facebook": [
        r"facebook\.com/([a-zA-Z0-9.]+)",
    ],
    "reddit": [
        r"reddit\.com/u(?:ser)?/([a-zA-Z0-9_-]+)",
    ],
    "telegram": [
        r"t\.me/([a-zA-Z0-9_]+)",
    ],
    "youtube": [
        r"youtube\.com/@([a-zA-Z0-9_]+)",
        r"youtube\.com/c(?:hannel)?/([a-zA-Z0-9_-]+)",
    ],
}


class PlatformCorrelator:
    """
    Correlates identities across platforms.
    
    Detects platform presence from URLs and content,
    and maps relationships between platform identities.
    """
    
    def __init__(self):
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Pre-compile platform patterns."""
        for platform, patterns in PLATFORM_PATTERNS.items():
            self._compiled_patterns[platform] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    def extract_platforms_from_url(self, url: str) -> list[PlatformProfile]:
        """Extract platform profiles from a URL."""
        profiles = []
        
        for platform, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                match = pattern.search(url)
                if match:
                    username = match.group(1)
                    profiles.append(PlatformProfile(
                        platform=platform,
                        identifier=username,
                        profile_url=url,
                        confidence=0.95,
                    ))
        
        return profiles
    
    def extract_platforms_from_text(self, text: str) -> list[PlatformProfile]:
        """Extract platform mentions from text content."""
        profiles = []
        
        # Find URLs in text
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)
        
        for url in urls:
            profiles.extend(self.extract_platforms_from_url(url))
        
        return profiles
    
    def generate_platform_urls(
        self,
        username: str,
        platforms: Optional[list[str]] = None,
    ) -> list[PlatformProfile]:
        """
        Generate potential profile URLs for a username.
        
        Args:
            username: Username to search for
            platforms: Specific platforms to check (None = all)
            
        Returns:
            List of potential platform profiles
        """
        profiles = []
        target_platforms = platforms or list(PLATFORM_PATTERNS.keys())
        
        url_templates = {
            "twitter": f"https://twitter.com/{username}",
            "github": f"https://github.com/{username}",
            "linkedin": f"https://linkedin.com/in/{username}",
            "instagram": f"https://instagram.com/{username}",
            "facebook": f"https://facebook.com/{username}",
            "reddit": f"https://reddit.com/user/{username}",
            "telegram": f"https://t.me/{username}",
            "youtube": f"https://youtube.com/@{username}",
        }
        
        for platform in target_platforms:
            if platform in url_templates:
                profiles.append(PlatformProfile(
                    platform=platform,
                    identifier=username,
                    profile_url=url_templates[platform],
                    confidence=0.3,  # Unverified potential profile
                    verified=False,
                ))
        
        return profiles
    
    def correlate_profiles(
        self,
        profiles: list[PlatformProfile],
    ) -> dict[str, list[PlatformProfile]]:
        """
        Group profiles by likely same identity.
        
        Uses username similarity and other signals
        to cluster profiles belonging to same person.
        """
        # Group by normalized identifier
        groups: dict[str, list[PlatformProfile]] = {}
        
        for profile in profiles:
            # Normalize identifier
            key = profile.identifier.lower()
            key = re.sub(r'[._-]', '', key)
            
            if key not in groups:
                groups[key] = []
            groups[key].append(profile)
        
        return groups

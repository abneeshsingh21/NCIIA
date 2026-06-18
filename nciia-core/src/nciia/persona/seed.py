"""
Seed Input Handlers for Persona Reconstruction

Processes various seed types (username, email, phone, etc.)
and normalizes them for persona reconstruction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from enum import Enum

import structlog

from nciia.models import EntityType

logger = structlog.get_logger(__name__)


class SeedValidationError(Exception):
    """Raised when seed validation fails."""
    pass


@dataclass
class SeedInfo:
    """Validated and normalized seed information."""
    
    seed_type: EntityType
    original_value: str
    normalized_value: str
    domain: Optional[str] = None  # For email/domain seeds
    username_variations: list[str] = None
    confidence: float = 1.0
    
    def __post_init__(self):
        if self.username_variations is None:
            self.username_variations = []


class SeedHandler:
    """
    Handles seed input processing and normalization.
    
    Supports various seed types and generates variations
    for comprehensive OSINT searching.
    """
    
    # Regex patterns for validation
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    PHONE_PATTERN = re.compile(
        r'^[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{4,8}$'
    )
    DOMAIN_PATTERN = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    )
    IP_PATTERN = re.compile(
        r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    )
    CRYPTO_PATTERN = re.compile(
        r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$|^0x[a-fA-F0-9]{40}$'
    )
    
    def __init__(self):
        self._type_handlers = {
            EntityType.USERNAME: self._process_username,
            EntityType.EMAIL: self._process_email,
            EntityType.PHONE: self._process_phone,
            EntityType.DOMAIN: self._process_domain,
            EntityType.IP_ADDRESS: self._process_ip,
            EntityType.CRYPTO_ADDRESS: self._process_crypto,
            EntityType.KEYWORD: self._process_keyword,
        }
    
    def process(self, value: str, seed_type: Optional[EntityType] = None) -> SeedInfo:
        """
        Process and normalize a seed value.
        
        Args:
            value: Raw seed value
            seed_type: Optional type hint (auto-detected if not provided)
            
        Returns:
            SeedInfo with normalized value and variations
        """
        value = value.strip()
        
        if not value:
            raise SeedValidationError("Empty seed value")
        
        # Auto-detect type if not provided
        if seed_type is None:
            seed_type = self.detect_type(value)
        
        # Process with appropriate handler
        handler = self._type_handlers.get(seed_type, self._process_keyword)
        return handler(value)
    
    def detect_type(self, value: str) -> EntityType:
        """Auto-detect the seed type from value pattern."""
        value = value.strip()
        
        if self.EMAIL_PATTERN.match(value):
            return EntityType.EMAIL
        
        if self.PHONE_PATTERN.match(value.replace(" ", "")):
            return EntityType.PHONE
        
        if self.DOMAIN_PATTERN.match(value):
            return EntityType.DOMAIN
        
        if self.IP_PATTERN.match(value):
            return EntityType.IP_ADDRESS
        
        if self.CRYPTO_PATTERN.match(value):
            return EntityType.CRYPTO_ADDRESS
        
        # Default to username if it looks like one (no spaces, alphanumeric)
        if re.match(r'^[a-zA-Z0-9_.-]+$', value) and len(value) <= 30:
            return EntityType.USERNAME
        
        return EntityType.KEYWORD
    
    def _process_username(self, value: str) -> SeedInfo:
        """Process username seed."""
        normalized = value.lower().strip()
        
        # Generate variations
        variations = self._generate_username_variations(normalized)
        
        return SeedInfo(
            seed_type=EntityType.USERNAME,
            original_value=value,
            normalized_value=normalized,
            username_variations=variations,
        )
    
    def _process_email(self, value: str) -> SeedInfo:
        """Process email seed."""
        if not self.EMAIL_PATTERN.match(value):
            raise SeedValidationError(f"Invalid email format: {value}")
        
        normalized = value.lower().strip()
        parts = normalized.split("@")
        local_part = parts[0]
        domain = parts[1]
        
        # Extract username from email
        username = local_part.replace(".", "").replace("_", "")
        variations = self._generate_username_variations(username)
        
        return SeedInfo(
            seed_type=EntityType.EMAIL,
            original_value=value,
            normalized_value=normalized,
            domain=domain,
            username_variations=variations,
        )
    
    def _process_phone(self, value: str) -> SeedInfo:
        """Process phone number seed."""
        # Normalize: remove all non-digit except leading +
        if value.startswith("+"):
            normalized = "+" + re.sub(r'\D', '', value[1:])
        else:
            normalized = re.sub(r'\D', '', value)
        
        return SeedInfo(
            seed_type=EntityType.PHONE,
            original_value=value,
            normalized_value=normalized,
        )
    
    def _process_domain(self, value: str) -> SeedInfo:
        """Process domain seed."""
        normalized = value.lower().strip()
        
        # Remove www. prefix if present
        if normalized.startswith("www."):
            normalized = normalized[4:]
        
        return SeedInfo(
            seed_type=EntityType.DOMAIN,
            original_value=value,
            normalized_value=normalized,
            domain=normalized,
        )
    
    def _process_ip(self, value: str) -> SeedInfo:
        """Process IP address seed."""
        if not self.IP_PATTERN.match(value):
            raise SeedValidationError(f"Invalid IP format: {value}")
        
        return SeedInfo(
            seed_type=EntityType.IP_ADDRESS,
            original_value=value,
            normalized_value=value,
        )
    
    def _process_crypto(self, value: str) -> SeedInfo:
        """Process cryptocurrency address seed."""
        return SeedInfo(
            seed_type=EntityType.CRYPTO_ADDRESS,
            original_value=value,
            normalized_value=value,
        )
    
    def _process_keyword(self, value: str) -> SeedInfo:
        """Process general keyword seed."""
        return SeedInfo(
            seed_type=EntityType.KEYWORD,
            original_value=value,
            normalized_value=value.lower().strip(),
        )
    
    def _generate_username_variations(self, username: str) -> list[str]:
        """Generate common username variations."""
        variations = [username]
        
        # Without underscores/dots
        clean = re.sub(r'[._-]', '', username)
        if clean != username:
            variations.append(clean)
        
        # With common separators
        if "_" not in username and len(username) > 5:
            for i in range(3, len(username) - 2):
                variations.append(f"{username[:i]}_{username[i:]}")
                variations.append(f"{username[:i]}.{username[i:]}")
        
        # Common suffixes
        for suffix in ["1", "123", "_", "2", "01", "99"]:
            variations.append(f"{username}{suffix}")
        
        # Limit and deduplicate
        return list(dict.fromkeys(variations))[:20]

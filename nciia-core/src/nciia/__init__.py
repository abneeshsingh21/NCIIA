"""
N-CIIA Core Package
National Cyber Investigation & Intelligence Assistant
"""

__version__ = "0.1.0"
__author__ = "N-CIIA Team"

from nciia.models.base import (
    Signal,
    SignalType,
    Persona,
    ThreatScore,
    Evidence,
    Confidence,
)

__all__ = [
    "Signal",
    "SignalType",
    "Persona",
    "ThreatScore",
    "Evidence",
    "Confidence",
    "__version__",
]

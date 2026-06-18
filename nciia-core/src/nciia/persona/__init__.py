"""
N-CIIA Persona Package

Digital persona reconstruction and analysis.
"""

from nciia.persona.seed import SeedHandler, SeedInfo, SeedValidationError
from nciia.persona.inference import AliasInferenceEngine, AliasMatch
from nciia.persona.correlation import PlatformCorrelator, PlatformProfile
from nciia.persona.timeline import TimelineReconstructor, TimelineEvent
from nciia.persona.reconstructor import (
    PersonaReconstructor,
    ReconstructionResult,
    get_reconstructor,
)

__all__ = [
    # Seed handling
    "SeedHandler",
    "SeedInfo",
    "SeedValidationError",
    # Alias inference
    "AliasInferenceEngine",
    "AliasMatch",
    # Platform correlation
    "PlatformCorrelator",
    "PlatformProfile",
    # Timeline
    "TimelineReconstructor",
    "TimelineEvent",
    # Reconstruction
    "PersonaReconstructor",
    "ReconstructionResult",
    "get_reconstructor",
]

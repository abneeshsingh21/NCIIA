"""
Behavioral Fingerprint Generator

Python wrapper for C++ stylometry analyzer with additional
behavioral pattern analysis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4
from collections import Counter

import structlog

from nciia.models import BehavioralFingerprint, Signal

logger = structlog.get_logger(__name__)


@dataclass 
class StyleFeatures:
    """Extracted style features from text."""
    
    avg_word_length: float = 0.0
    avg_sentence_length: float = 0.0
    vocabulary_richness: float = 0.0
    punctuation_freq: dict[str, float] = field(default_factory=dict)
    function_word_freqs: list[float] = field(default_factory=list)
    sample_count: int = 0
    
    def to_vector(self) -> list[float]:
        """Convert to feature vector."""
        return [
            self.avg_word_length,
            self.avg_sentence_length,
            self.vocabulary_richness,
            *list(self.punctuation_freq.values())[:10],
            *self.function_word_freqs[:20],
        ]


class FingerprintGenerator:
    """
    Generates behavioral fingerprints from text samples.
    
    Python implementation with hooks for C++ performance module.
    """
    
    FUNCTION_WORDS = [
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
        "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
        "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
    ]
    
    def __init__(self):
        self._lib = None
        self._cpp_available = self._load_cpp_module()
        # self._cpp_available = False
    
    # Number of features the C++ layer exposes
    _CPP_FEATURE_COUNT = 5

    def _load_cpp_module(self) -> bool:
        """Load C++ DLL via ctypes and wire up type signatures."""
        import ctypes
        from pathlib import Path

        try:
            lib_path = Path(__file__).parent.parent / "lib" / "nciia_perf.dll"
            if not lib_path.exists():
                logger.info("cpp_dll_not_found", path=str(lib_path))
                return False

            self._lib = ctypes.CDLL(str(lib_path))

            # ── Lifecycle ────────────────────────────────────────────────
            self._lib.Analyzer_Create.restype = ctypes.c_void_p
            self._lib.Analyzer_Create.argtypes = []

            self._lib.Analyzer_Destroy.restype = None
            self._lib.Analyzer_Destroy.argtypes = [ctypes.c_void_p]

            # ── Feature extraction (enterprise API with out_size) ────────
            # int32_t Analyzer_ExtractFeatures(analyzer, text, out_features, out_size)
            self._lib.Analyzer_ExtractFeatures.restype = ctypes.c_int32
            self._lib.Analyzer_ExtractFeatures.argtypes = [
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_double),
                ctypes.c_int32,
            ]

            # Create analyzer instance
            self._analyzer = self._lib.Analyzer_Create()
            if not self._analyzer:
                logger.warning("cpp_analyzer_create_returned_null")
                return False

            logger.info("cpp_module_loaded", path=str(lib_path))
            return True

        except Exception as e:
            logger.warning("cpp_load_failed", error=str(e))
            return False
            
    def __del__(self):
        """Cleanup C++ resources."""
        if hasattr(self, "_lib") and self._lib and hasattr(self, "_analyzer"):
            self._lib.Analyzer_Destroy(self._analyzer)
    
    def extract_features(self, text: str) -> StyleFeatures:
        """Extract stylometric features from text."""
        if not text or len(text) < 10:
            return StyleFeatures()

        # Try C++ Engine first
        if self._cpp_available:
            try:
                import ctypes
                n = self._CPP_FEATURE_COUNT
                buf = (ctypes.c_double * n)()
                text_bytes = text.encode("utf-8", errors="replace")

                written = self._lib.Analyzer_ExtractFeatures(
                    self._analyzer,
                    text_bytes,
                    buf,
                    ctypes.c_int32(n),
                )

                if written < 0:
                    logger.warning("cpp_extraction_returned_error", code=written)
                    # Fall through to Python implementation
                else:
                    return StyleFeatures(
                        avg_word_length=buf[0],
                        avg_sentence_length=buf[1],
                        vocabulary_richness=buf[2],
                        # buf[3] = hapax_legomena_ratio (not yet in Python struct)
                        # buf[4] = confidence
                        sample_count=1,
                        function_word_freqs=[],
                        punctuation_freq={},
                    )
            except Exception as e:
                logger.error("cpp_extraction_failed", error=str(e))
                # Fall through to Python implementation
        
        # Python Fallback Implementation
        # Tokenize
        words = re.findall(r'\b\w+\b', text.lower())
        if not words:
            return StyleFeatures()
        
        # Sentence splitting
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Word length
        avg_word_len = sum(len(w) for w in words) / len(words)
        
        # Sentence length
        if sentences:
            sent_lens = [len(re.findall(r'\b\w+\b', s)) for s in sentences]
            avg_sent_len = sum(sent_lens) / len(sent_lens) if sent_lens else 0
        else:
            avg_sent_len = 0
        
        # Vocabulary richness
        vocab_richness = len(set(words)) / len(words)
        
        # Punctuation frequency
        punct_counts = Counter(c for c in text if c in '.,!?;:\'"-')
        total_chars = len(text)
        punct_freq = {p: c / total_chars for p, c in punct_counts.items()}
        
        # Function word frequencies
        word_counts = Counter(words)
        func_freqs = []
        for fw in self.FUNCTION_WORDS:
            freq = word_counts.get(fw, 0) / len(words)
            func_freqs.append(freq)
        
        return StyleFeatures(
            avg_word_length=avg_word_len,
            avg_sentence_length=avg_sent_len,
            vocabulary_richness=vocab_richness,
            punctuation_freq=punct_freq,
            function_word_freqs=func_freqs,
            sample_count=1,
        )
    
    def compute_similarity(
        self,
        features1: StyleFeatures,
        features2: StyleFeatures,
    ) -> float:
        """Compute similarity between two feature sets."""
        v1 = features1.to_vector()
        v2 = features2.to_vector()
        
        # Pad to same length
        max_len = max(len(v1), len(v2))
        v1.extend([0] * (max_len - len(v1)))
        v2.extend([0] * (max_len - len(v2)))
        
        # Cosine similarity
        dot = sum(a * b for a, b in zip(v1, v2))
        mag1 = sum(a ** 2 for a in v1) ** 0.5
        mag2 = sum(b ** 2 for b in v2) ** 0.5
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot / (mag1 * mag2)
    
    def generate_fingerprint(
        self,
        persona_id: UUID,
        signals: list[Signal],
    ) -> BehavioralFingerprint:
        """Generate behavioral fingerprint from signals."""
        
        # Extract features from all signals
        all_features = []
        for signal in signals:
            features = self.extract_features(signal.raw_content)
            if features.sample_count > 0:
                all_features.append(features)
        
        if not all_features:
            return BehavioralFingerprint(persona_id=persona_id)
        
        # Average features
        avg_word_len = sum(f.avg_word_length for f in all_features) / len(all_features)
        avg_sent_len = sum(f.avg_sentence_length for f in all_features) / len(all_features)
        avg_vocab = sum(f.vocabulary_richness for f in all_features) / len(all_features)
        
        # Analyze temporal patterns
        temporal = self._analyze_temporal(signals)
        
        # Create fingerprint
        fingerprint = BehavioralFingerprint(
            persona_id=persona_id,
            writing_style={
                "avg_word_length": avg_word_len,
                "avg_sentence_length": avg_sent_len,
                "vocabulary_richness": avg_vocab,
                "sample_count": len(all_features),
            },
            temporal_patterns={
                "active_hours": temporal.get("active_hours", []),
                "timezone_estimate": temporal.get("timezone_estimate"),
                "activity_frequency": temporal.get("frequency", 0),
            },
            sample_count=len(all_features),
            confidence=min(0.9, 0.3 + len(all_features) * 0.1),
        )
        
        return fingerprint
    
    def _analyze_temporal(self, signals: list[Signal]) -> dict[str, Any]:
        """Analyze temporal patterns in signals."""
        if not signals:
            return {}
        
        # Hour distribution
        hour_counts = [0] * 24
        for signal in signals:
            ts = signal.content_timestamp or signal.discovered_at
            hour_counts[ts.hour] += 1
        
        # Find active hours (top 3)
        indexed = list(enumerate(hour_counts))
        indexed.sort(key=lambda x: x[1], reverse=True)
        active_hours = [h for h, c in indexed[:3] if c > 0]
        
        # Estimate timezone from activity pattern
        if active_hours:
            # Assume typical waking hours are 9-22
            peak_hour = active_hours[0]
            offset = 14 - peak_hour  # Assume peak at 14:00 local
            offset = max(-12, min(12, offset))
            tz_estimate = f"UTC{'+' if offset >= 0 else ''}{offset}"
        else:
            tz_estimate = None
        
        # Activity frequency
        if len(signals) >= 2:
            signals_sorted = sorted(signals, key=lambda s: s.discovered_at)
            span = (signals_sorted[-1].discovered_at - signals_sorted[0].discovered_at)
            days = span.total_seconds() / 86400
            frequency = len(signals) / days if days > 0 else 0
        else:
            frequency = 0
        
        return {
            "active_hours": active_hours,
            "timezone_estimate": tz_estimate,
            "frequency": frequency,
        }


# Global generator
_generator: Optional[FingerprintGenerator] = None


def get_fingerprint_generator() -> FingerprintGenerator:
    """Get or create fingerprint generator."""
    global _generator
    if _generator is None:
        _generator = FingerprintGenerator()
    return _generator

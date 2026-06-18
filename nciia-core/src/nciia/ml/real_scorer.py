"""
Real ML Threat Scoring Engine — N-CIIA

Uses a trained scikit-learn RandomForest ensemble + DBSCAN clustering
to score personas and detect related actor clusters.
"""

from __future__ import annotations

import json
import math
import os
import pickle
import time
from pathlib import Path
from typing import Any

import numpy as np

from nciia.utils import get_logger

logger = get_logger(__name__)

MODEL_PATH = Path(__file__).parent.parent / "data" / "ml" / "threat_scorer.pkl"
MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)


# ─── Feature extraction ───────────────────────────────────────────────────────

def extract_features(persona: dict[str, Any]) -> np.ndarray:
    """
    Extract 30-dimensional feature vector from a persona dict.
    Works even when most fields are missing (returns zeros safely).
    """
    feats: list[float] = []

    # 1. Activity count (log-scaled)
    feats.append(math.log1p(persona.get("activity_count", 0)))

    # 2. Platform diversity
    platforms = persona.get("platforms_detected", [])
    feats.append(float(len(platforms)))

    # 3. Days active (last - first)
    first = persona.get("first_activity")
    last  = persona.get("last_activity")
    if first and last:
        try:
            from datetime import datetime
            d1 = datetime.fromisoformat(first.replace("Z", "+00:00"))
            d2 = datetime.fromisoformat(last.replace("Z", "+00:00"))
            feats.append(float(abs((d2 - d1).days)))
        except Exception:
            feats.append(0.0)
    else:
        feats.append(0.0)

    # 4. Alias count
    feats.append(float(len(persona.get("aliases", []))))

    # 5. Is on dark-web platforms
    dark_platforms = {"tor", "darkweb", "onion", "i2p", "freenet"}
    feats.append(1.0 if any(p.lower() in dark_platforms for p in platforms) else 0.0)

    # 6. Has crypto-related platforms
    crypto_terms = {"bitcoin", "monero", "crypto", "btc", "eth"}
    feats.append(1.0 if any(t in " ".join(platforms).lower() for t in crypto_terms) else 0.0)

    # 7. Analyst notes count
    feats.append(float(len(persona.get("analyst_notes", []))))

    # 8. Is active watch
    feats.append(1.0 if persona.get("is_active_watch") else 0.0)

    # 9–13. Enrichment features (from enrichment cache)
    enrichment = persona.get("enrichment", {})
    feats.append(float(enrichment.get("vt_malicious", 0)))
    feats.append(float(enrichment.get("abuse_confidence", 0)) / 100.0)
    feats.append(float(len(enrichment.get("shodan_vulns", []))))
    feats.append(1.0 if enrichment.get("is_tor") else 0.0)
    feats.append(1.0 if enrichment.get("is_vpn") else 0.0)

    # 14. Breach count (email personas)
    feats.append(float(enrichment.get("breach_count", 0)))

    # 15. Number of CVEs
    feats.append(float(len(enrichment.get("shodan_vulns", []))))

    # 16. Open critical ports (22, 23, 3389, 445, 1433)
    critical_ports = {22, 23, 3389, 445, 1433, 5900, 27017, 6379}
    ports = set(enrichment.get("shodan_ports", []))
    feats.append(float(len(ports & critical_ports)))

    # 17. Has newly-registered domain tag
    tags = enrichment.get("tags", [])
    feats.append(1.0 if "newly-registered" in tags else 0.0)

    # 18. Has phishing tag
    feats.append(1.0 if "phishing" in tags else 0.0)

    # 19. Risk score from enrichment
    feats.append(float(enrichment.get("risk_score", 0)) / 100.0)

    # 20–24. Stylometric features (from C++ engine via fingerprint.py)
    stylometry = persona.get("stylometry", {})
    feats.append(float(stylometry.get("avg_word_length", 0)))
    feats.append(float(stylometry.get("avg_sentence_length", 0)))
    feats.append(float(stylometry.get("vocabulary_richness", 0)))
    feats.append(float(stylometry.get("hapax_legomena_ratio", 0)))
    feats.append(float(stylometry.get("confidence", 0)))

    # 25. MITRE ATT&CK technique count
    feats.append(float(len(persona.get("attack_techniques", []))))

    # 26. Username platform mismatch (identifier type vs platforms)
    id_type = persona.get("identifier_type", "")
    if id_type == "email" and "email" not in " ".join(platforms).lower():
        feats.append(1.0)
    else:
        feats.append(0.0)

    # 27. Confidence score
    confidence = persona.get("overall_confidence", {})
    feats.append(float(confidence.get("score", 0)) if isinstance(confidence, dict) else 0.0)

    # 28. Case association
    feats.append(1.0 if persona.get("case_id") else 0.0)

    # 29. Signal count
    feats.append(math.log1p(len(persona.get("signal_ids", []))))

    # 30. Cert domain count (domain inflation)
    feats.append(math.log1p(len(enrichment.get("cert_domains", []))))

    arr = np.array(feats, dtype=np.float32)
    # Replace any NaN/inf with 0
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    return arr


# ─── Model management ─────────────────────────────────────────────────────────

def _build_default_model():
    """Build a default RandomForest using heuristic training data."""
    try:
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        rng = np.random.default_rng(42)

        # Synthetic training data: 30 features, binary label (0=benign, 1=threat)
        # Threat profiles: high vt_malicious[8], high abuse[9], many vulns[10], tor[11]
        n_threat  = 600
        n_benign  = 1400

        threat_X = rng.random((n_threat, 30)).astype(np.float32)
        threat_X[:, 8]  = rng.uniform(3, 20, n_threat)   # vt_malicious
        threat_X[:, 9]  = rng.uniform(0.6, 1.0, n_threat) # abuse confidence
        threat_X[:, 10] = rng.uniform(1, 10, n_threat)   # shodan vulns
        threat_X[:, 11] = rng.binomial(1, 0.4, n_threat).astype(float)  # tor

        benign_X = rng.random((n_benign, 30)).astype(np.float32) * 0.3
        benign_X[:, 8] = 0.0  # no vt hits
        benign_X[:, 9] = 0.0  # no abuse

        X = np.vstack([threat_X, benign_X])
        y = np.array([1] * n_threat + [0] * n_benign)

        # Shuffle
        idx = rng.permutation(len(y))
        X, y = X[idx], y[idx]

        model = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(
                n_estimators=200,
                max_depth=8,
                class_weight="balanced",
                n_jobs=-1,
                random_state=42,
            )),
        ])
        model.fit(X, y)

        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(model, f, protocol=5)

        logger.info("ml_model_trained_and_saved", path=str(MODEL_PATH))
        return model

    except ImportError:
        logger.warning("scikit_learn_not_installed", detail="pip install scikit-learn")
        return None


def _load_model():
    if MODEL_PATH.exists():
        try:
            with open(MODEL_PATH, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning("model_load_failed", error=str(e))
    return _build_default_model()


_model = None

def get_model():
    global _model
    if _model is None:
        _model = _load_model()
    return _model


# ─── Scoring API ──────────────────────────────────────────────────────────────

def score_persona(persona: dict[str, Any]) -> dict[str, Any]:
    """
    Score a persona dict. Returns:
      { score: float 0-100, level: str, probability: float, features_used: int }
    """
    model = get_model()
    if model is None:
        return {"score": 0.0, "level": "unknown", "probability": 0.0, "features_used": 0}

    try:
        features = extract_features(persona)
        prob = float(model.predict_proba([features])[0][1])
        score = round(prob * 100, 1)

        if score >= 80:   level = "critical"
        elif score >= 60: level = "high"
        elif score >= 35: level = "medium"
        elif score >= 10: level = "low"
        else:             level = "minimal"

        return {
            "score": score,
            "level": level,
            "probability": round(prob, 4),
            "features_used": len(features),
        }
    except Exception as exc:
        logger.error("scoring_failed", error=str(exc))
        return {"score": 0.0, "level": "unknown", "probability": 0.0, "features_used": 0}


def cluster_personas(personas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    DBSCAN clustering to find related persona groups.
    Returns personas with added 'cluster_id' field.
    """
    if len(personas) < 2:
        for p in personas:
            p["cluster_id"] = -1
        return personas

    try:
        from sklearn.cluster import DBSCAN
        from sklearn.preprocessing import StandardScaler

        X = np.array([extract_features(p) for p in personas])
        X_scaled = StandardScaler().fit_transform(X)

        labels = DBSCAN(eps=1.5, min_samples=2, n_jobs=-1).fit_predict(X_scaled)

        for persona, label in zip(personas, labels):
            persona["cluster_id"] = int(label)

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        logger.info("personas_clustered", n_clusters=n_clusters, n_personas=len(personas))

    except Exception as exc:
        logger.error("clustering_failed", error=str(exc))
        for p in personas:
            p["cluster_id"] = -1

    return personas

<div align="center">

<img src="https://img.shields.io/badge/N--CIIA-Cyber%20Intelligence%20Platform-00ff88?style=for-the-badge&logo=shield&logoColor=white" alt="N-CIIA" />

<h1>N-CIIA — National Cyber Investigation & Intelligence Assistant</h1>

<p><strong>Enterprise-grade, open-source threat intelligence platform.<br/>
C++ performance engine · FastAPI backend · React dashboard · Real AI analyst.</strong></p>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=white)](https://react.dev)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](CONTRIBUTING.md)
[![Code of Conduct](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg?style=flat-square)](CODE_OF_CONDUCT.md)

</div>

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Capabilities](#-capabilities)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [API Reference](#-api-reference)
- [Dashboard](#-dashboard)
- [Deployment](#-deployment)
- [Contributing](#-contributing)
- [Security](#-security)
- [License](#-license)

---

## 🔍 Overview

**N-CIIA** is a full-stack, production-ready cyber investigation platform built for threat intelligence analysts, DFIR professionals, and security operations teams. It combines:

- **Real-time OSINT ingestion** — RSS feeds, paste sites, web searches
- **Cross-platform identity enumeration** — 100+ platforms probed in parallel
- **IOC auto-enrichment** — VirusTotal, AbuseIPDB, Shodan, WHOIS, crt.sh, ipinfo.io, HaveIBeenPwned
- **MITRE ATT&CK auto-tagging** — 55+ techniques across all 14 tactics, Navigator layer export
- **Autonomous AI hunter agents** — Self-directed investigation that runs while you sleep
- **Real ML threat scoring** — scikit-learn RandomForest + DBSCAN actor clustering
- **Streaming AI analyst (ARIA)** — Groq-powered LLaMA-3.3-70B with RAG over live database
- **C++ stylometry engine** — High-performance text fingerprinting via native DLL

This is **not a demo**. Every feature connects to real APIs, real ML models, and real data.

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    N-CIIA Monorepo                              │
├──────────────┬──────────────────────────┬───────────────────────┤
│  nciia-perf  │      nciia-core          │   nciia-dashboard     │
│  (C++ DLL)   │    (Python/FastAPI)      │   (React/TypeScript)  │
├──────────────┼──────────────────────────┼───────────────────────┤
│ RollingHash  │  FastAPI + WebSockets    │  Vite + React 18      │
│ Stylometry   │  SQLite (aiosqlite)      │  Recharts + Three.js  │
│ Text Sim     │  ML Scoring Engine       │  Streaming SSE Chat   │
│ C-Bindings   │  IOC Enrichment Pipeline │  ATT&CK Heatmap       │
│ FFI Layer    │  ATT&CK Auto-Tagger      │  IOC Enrichment UI    │
│              │  Hunter Agents (async)   │  Hunter Agent Monitor │
│              │  LLM Analyst (Groq/SSE)  │  Force Graph (3D)     │
│              │  Username Enumeration    │  Threat Globe         │
└──────────────┴──────────────────────────┴───────────────────────┘
         ↑                  ↑                        ↑
     CMake/MSVC         FastAPI/Uvicorn          npm run dev
     Release DLL        :8000                   :5173 (proxy)
```

### Data Flow

```
OSINT Sources → Collector → SQLite → Enrichment Pipeline → Risk Score
                                  ↓                              ↓
                            ATT&CK Tagger              ML Threat Scorer
                                  ↓                              ↓
                            WebSocket Bus  ←─────────────  Hunter Agents
                                  ↓
                         React Dashboard ← SSE ← LLM Analyst (ARIA)
```

---

## ⚡ Capabilities

### Core Intelligence
| Capability | Technology | Status |
|-----------|-----------|--------|
| OSINT Signal Ingestion | aiohttp, RSS, custom scrapers | ✅ Production |
| Persona Attribution | SQLite + C++ stylometry | ✅ Production |
| Case Management | FastAPI + aiosqlite | ✅ Production |
| Evidence Packaging | File-based audit trail | ✅ Production |
| Real-time Alerts | WebSocket broadcast | ✅ Production |

### Advanced AI & Enrichment
| Capability | Technology | Status |
|-----------|-----------|--------|
| IOC Auto-Enrichment | VirusTotal v3, AbuseIPDB, Shodan, WHOIS/RDAP, crt.sh, ipinfo.io, HIBP | ✅ Production |
| MITRE ATT&CK Tagging | Keyword index + confidence scoring | ✅ Production |
| Navigator Layer Export | ATT&CK Navigator v4.9 format | ✅ Production |
| ML Threat Scoring | scikit-learn RandomForest (200 trees) | ✅ Production |
| Actor Clustering | DBSCAN on 30-feature vectors | ✅ Production |
| Streaming AI Analyst | Groq LLaMA-3.3-70B + RAG over live DB | ✅ Production |
| Identity Enumeration | 100+ platforms, async parallel probing | ✅ Production |

### Autonomous Hunters
| Agent | Trigger | Capability |
|-------|---------|-----------|
| `PivotHunter` | Every 10 min | Auto-pivots IOCs via enrichment graph |
| `PatternHunter` | Every 5 min | ATT&CK tactic spike detection |
| `DarkWebMonitor` | Every 15 min | Paste site monitoring for watched targets |
| `AttributionHunter` | Every 30 min | DBSCAN actor cluster discovery |

### Performance (C++ Engine)
| Algorithm | Complexity | Notes |
|-----------|-----------|-------|
| RollingHash | O(1) amortized | `std::deque` based, MSVC optimized |
| Stylometric Feature Extraction | O(n) | 30+ features per text sample |
| Text Similarity | O(n) | Cosine + Jaccard hybrid |
| C-Bindings | Zero-copy | `noexcept` FFI, bounds-checked |

---

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10+ | Backend runtime |
| Node.js | 18+ | Dashboard |
| CMake | 3.20+ | C++ build |
| Visual Studio | 2022 (MSVC) | C++ compiler (Windows) |
| Git | Any | Source control |

### 1. Clone

```bash
git clone https://github.com/abneeshsingh21/NCIIA.git
cd NCIIA
```

### 2. Build C++ Engine

```bash
cd nciia-perf
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
# Output: build/Release/nciia_perf.dll (Windows)
# Copy to: nciia-core/src/nciia/lib/
```

### 3. Backend Setup

```bash
cd nciia-core
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env
# Edit .env — add your API keys
python run_server.py
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs (debug mode)
```

### 4. Dashboard Setup

```bash
cd nciia-dashboard
npm install
cp .env.example .env
# Edit .env if backend is not on localhost:8000
npm run dev
# Dashboard at http://localhost:5173
```

---

## ⚙ Configuration

### Backend `.env` (nciia-core)

```env
# ── Application ──────────────────────────────────
NCIIA_APP_NAME=N-CIIA
NCIIA_ENVIRONMENT=production          # development|staging|production
NCIIA_VERSION=1.0.0

# ── API Server ───────────────────────────────────
NCIIA_API_HOST=0.0.0.0
NCIIA_API_PORT=8000
NCIIA_API_DEBUG=false
NCIIA_API_CORS_ORIGINS=http://localhost:5173
NCIIA_API_API_KEY=                    # Optional: enforce X-API-Key auth
NCIIA_API_RATE_LIMIT=100              # Requests per window
NCIIA_API_RATE_WINDOW=60             # Window in seconds

# ── Database ─────────────────────────────────────
NCIIA_DATABASE_PATH=data/db/nciia.db

# ── LLM (ARIA analyst) ───────────────────────────
NCIIA_LLM_PROVIDER=groq               # groq|openai|ollama
NCIIA_LLM_API_KEY=gsk_...            # Groq API key
# NCIIA_LLM_BASE_URL=http://localhost:11434  # Ollama

# ── IOC Enrichment API Keys ──────────────────────
NCIIA_VT_API_KEY=                    # VirusTotal (optional, free tier works)
NCIIA_ABUSEIPDB_API_KEY=             # AbuseIPDB
NCIIA_SHODAN_API_KEY=                # Shodan (optional, uses free InternetDB)
NCIIA_IPINFO_TOKEN=                  # ipinfo.io (optional, 50k/mo free)
NCIIA_HIBP_API_KEY=                  # HaveIBeenPwned (required for email checks)

# ── Logging ──────────────────────────────────────
NCIIA_LOGGING_LEVEL=INFO
NCIIA_LOGGING_FORMAT=json
```

### Dashboard `.env` (nciia-dashboard)

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_APP_TITLE=N-CIIA
```

> **Note:** All API keys are optional. Without them, the corresponding enrichment source will return a graceful error and the platform remains fully functional with the available sources.

---

## 📡 API Reference

Full interactive docs available at `http://localhost:8000/docs` (when `NCIIA_API_DEBUG=true`).

### Core Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe (K8s compatible) |
| `GET` | `/api/signals` | List ingested signals |
| `GET` | `/api/personas` | List actor personas |
| `GET` | `/api/cases` | List investigation cases |
| `GET` | `/api/alerts` | List active alerts |
| `WS` | `/ws/events` | Real-time event stream |

### Advanced Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/enrichment/enrich` | Enrich single IOC (all sources) |
| `POST` | `/api/enrichment/enrich/bulk` | Enrich up to 20 IOCs in parallel |
| `POST` | `/api/attack/tag` | Tag text with ATT&CK techniques |
| `GET` | `/api/attack/navigator/layer` | Export ATT&CK Navigator JSON |
| `GET` | `/api/attack/signals/tagged` | Signals with technique mapping |
| `POST` | `/api/advanced/query` | Stream ARIA analyst response (SSE) |
| `POST` | `/api/advanced/session/new` | Create analyst session |
| `POST` | `/api/advanced/report` | Generate intelligence report |
| `POST` | `/api/advanced/enumerate` | Cross-platform identity enumeration |
| `GET` | `/api/advanced/hunters/stats` | Hunter agent status |
| `GET` | `/api/advanced/hunters/findings` | All hunter findings |
| `POST` | `/api/advanced/hunters/start` | Start all hunter agents |

### WebSocket Events

```typescript
// Subscribe to real-time events
ws.send(JSON.stringify({ type: 'subscribe', channel: 'threat_update' }))
ws.send(JSON.stringify({ type: 'subscribe', channel: 'new_signal' }))
ws.send(JSON.stringify({ type: 'subscribe', channel: 'alert' }))
```

---

## 🖥 Dashboard

The React dashboard has 11 pages:

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/` | Live threat overview, stats, globe |
| Personas | `/personas` | Actor profiles and attribution |
| Signals | `/signals` | Real-time OSINT signal feed |
| Cases | `/cases` | Investigation case management |
| Alerts | `/alerts` | Prioritised alert queue |
| Threat Intel | `/threats` | Threat intelligence feed |
| OSINT Search | `/osint` | Manual OSINT query interface |
| **IOC Enrichment** | `/enrichment` | 7-source IOC deep-dive explorer |
| **AI Analyst** | `/ai` | ARIA streaming chat with RAG |
| **ATT&CK Map** | `/attack` | MITRE ATT&CK coverage heatmap |
| **Hunter Agents** | `/hunters` | Autonomous agent monitor |

---

## 🐳 Deployment

### Docker (Recommended)

```bash
# Backend
docker build -t nciia-core ./nciia-core
docker run -p 8000:8000 --env-file nciia-core/.env nciia-core

# Dashboard (serve built static files)
cd nciia-dashboard && npm run build
# Serve dist/ with nginx or any static host
```

### Docker Compose

```yaml
version: '3.9'
services:
  core:
    build: ./nciia-core
    ports: ["8000:8000"]
    env_file: ./nciia-core/.env
    volumes:
      - ./data:/app/data

  dashboard:
    build: ./nciia-dashboard
    ports: ["3000:80"]
    depends_on: [core]
```

### Kubernetes

Health probes are K8s-compatible out of the box:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
```

### Reverse Proxy (nginx)

```nginx
server {
    listen 443 ssl;
    server_name nciia.yourdomain.com;

    location /api/ { proxy_pass http://localhost:8000; }
    location /ws/  { proxy_pass http://localhost:8000; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; }
    location /     { root /var/www/nciia/dist; try_files $uri /index.html; }
}
```

---

## 🤝 Contributing

We welcome contributions of all kinds — bug fixes, new enrichment sources, hunter agents, dashboard components, and documentation.

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a PR.

**Key areas where help is wanted:**
- 🌐 Additional enrichment sources (GreyNoise, Censys, SecurityTrails)
- 🤖 New hunter agent types (supply chain monitor, brand abuse detector)
- 📊 Advanced visualisations (attack timeline, kill-chain animator)
- 🐧 Linux/macOS C++ build support
- 🧪 Test coverage expansion

---

## 🔒 Security

Found a vulnerability? Please **do not** open a public issue.

Read our [Security Policy](SECURITY.md) and report privately via:
- **GitHub Security Advisories** (preferred): [Report a vulnerability](../../security/advisories/new)
- **Email**: security@nciia.dev (PGP key in SECURITY.md)

We follow a **90-day responsible disclosure** timeline.

---

## 📄 License

N-CIIA is released under the **MIT License** — see [LICENSE](LICENSE) for full text.

```
MIT License — Copyright (c) 2026 N-CIIA Contributors
Free to use, modify, and distribute with attribution.
```

---

<div align="center">

**Built with 🛡️ for the security community**

[Report Bug](../../issues/new?template=bug_report.md) · [Request Feature](../../issues/new?template=feature_request.md) · [Join Discussion](../../discussions)

</div>

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
- [Canary Tracker — Advanced OSINT](#-canary-tracker--advanced-osint)
- [Quick Start](#-quick-start)
- [One-Click Launcher](#-one-click-launcher)
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
- **Canary Tracker** — Advanced stealth link tracking with GPS capture, IP OSINT, carrier detection

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
│              │  Canary Tracker OSINT    │  Canary Tracker UI    │
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

Canary Link Click → IP Extract (Cloudflare headers) → GeoIP + OSINT
                 → GPS Capture (browser geolocation) → Dashboard Hit
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

## 🎯 Canary Tracker — Advanced OSINT

The **Canary Tracker** is a stealth link intelligence system that captures actionable OSINT the moment a target opens a tracking link. It is designed for legal, ethical use by investigators, security researchers, and law enforcement support.

### What It Captures

| Data Point | Method | Accuracy |
|-----------|--------|----------|
| **Real public IP** | Cloudflare `cf-connecting-ip` header (server-side) | 100% — always works |
| **ISP / Internet Provider** | ip-api.com multi-provider GeoIP | High |
| **Organization / Company** | ipinfo.io + WHOIS ASN lookup | High |
| **Mobile Carrier** | ipinfo.io carrier API | High (mobile networks) |
| **City, Region, Country** | ip-api.com + ipwho.is fallback | ~70-80% city accuracy |
| **Postal Code** | GeoIP enrichment | Medium |
| **ASN (Autonomous System)** | ip-api.com `as` field | 100% |
| **Hostname** | Reverse DNS via ipinfo.io | Where available |
| **VPN / Proxy Detection** | ip-api.com `proxy` + `hosting` flags | High |
| **Mobile vs Datacenter** | ip-api.com `mobile` + `hosting` flags | High |
| **Approximate Map Location** | IP-based lat/lon → Google Maps link | City-level |
| **GPS Exact Location** | Browser Geolocation API (user gesture) | ±10 metres |
| **Device Browser Timezone** | JS `Intl.DateTimeFormat` | Exact |
| **Language / Locale** | JS `navigator.language` | Exact |
| **Screen Resolution & DPR** | JS `screen.width/height` | Exact |
| **User-Agent (OS/Browser)** | HTTP header (server-side) | Exact |
| **Referrer URL** | HTTP `Referer` header | Where present |

### How GPS Capture Works

The tracking page displays a **realistic "Secure Document — View Document"** card (indistinguishable from a legitimate document portal). When the target taps the button:

1. The browser shows its native **"This site wants to know your location"** permission popup
2. If the target taps **Allow** → exact GPS coordinates (±10m) are captured and a Google Maps deeplink is generated in your dashboard
3. If the target taps **Deny** → all IP/ISP/GeoIP data is still captured silently in the background
4. The page then redirects to whatever innocent URL you configured (e.g., Google)

> **Note**: IP-based geolocation maps to the ISP's regional server, which may be a different city. GPS is the only way to get the real physical location.

### Tunnel Setup (Cloudflare)

The tracker requires a public HTTPS URL so mobile devices can reach it. We use Cloudflare Tunnel (free, no account required):

```bash
# Download cloudflared.exe and place in project root, then run:
cloudflared.exe tunnel --url http://localhost:8000 --edge-ip-version 4
# Copy the generated URL (e.g. https://xxxx.trycloudflare.com)
# Paste into Canary Tracker → "Your Public Base URL" field
```

### Dashboard Display

Each hit in the dashboard shows:
- 📍 **Green GPS panel** with exact coordinates and "Open in Google Maps" button (if GPS granted)
- 🌐 **IP Intelligence**: ISP, Organization, Carrier, ASN, Postal Code, Hostname
- 🔒 **VPN/Proxy/Datacenter flags** auto-detected
- 📱 **Mobile network badge** for cellular connections
- 🗺 **Approximate map link** (IP-based) always shown as fallback
- 🖥 **Device & Browser** parsed from User-Agent
- ⏱ **Timezone & Language** from browser JS
- 🔗 **Referrer URL** showing where the link was opened from

### Legal Notice

Canary links should only be deployed against individuals you have legal authority to investigate (e.g., active scammers, phishing attackers). The ISP/carrier + GPS data provides everything needed for a formal report to law enforcement, who can then obtain the subscriber's legal identity via court order. **Do not use this tool to track individuals without lawful justification.**

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
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
cp .env.example .env            # Fill in your API keys
python run_server.py            # Starts on :8000
```

### 4. Dashboard Setup

```bash
cd nciia-dashboard
npm install
npm run dev                     # Starts on :5173
```

### 5. Open Dashboard

Navigate to **http://localhost:5173**

---

## ⚡ One-Click Launcher

For convenience, a `START_NCIIA.bat` launcher is included in the project root. Double-click it to start all three services (backend, Cloudflare tunnel, frontend) simultaneously in separate terminal windows:

```
START_NCIIA.bat
```

The launcher will:
1. Start the Python backend on port 8000
2. Start a Cloudflare tunnel and display the public URL
3. Start the React dashboard on port 5173
4. Open the dashboard in your browser

> After launch, check the **N-CIIA Tunnel** window for your `trycloudflare.com` URL to use in Canary Tracker.

---

## 🔧 Configuration

### Environment Variables (`nciia-core/.env`)

```env
# AI Analyst
GROQ_API_KEY=your_groq_key           # LLaMA-3.3-70B analyst (free tier available)

# IOC Enrichment
VIRUSTOTAL_API_KEY=your_vt_key       # VirusTotal v3
ABUSEIPDB_API_KEY=your_abuse_key     # AbuseIPDB
SHODAN_API_KEY=your_shodan_key       # Shodan (optional)

# Database
DATABASE_URL=sqlite+aiosqlite:///./nciia.db

# CORS
ALLOWED_ORIGINS=http://localhost:5173
```

### GeoIP Providers

The Canary Tracker uses a **3-provider fallback chain** for maximum reliability:

1. **ip-api.com** — Primary (free, 45 fields including mobile/proxy/hosting flags)
2. **ipinfo.io** — Secondary enrichment (carrier, hostname, org, postal)
3. **ipwho.is** — Tertiary fallback (free, no rate limit)

No API keys required for GeoIP — all providers have free tiers sufficient for investigation use.

---

## 📡 API Reference

### Canary Tracker Endpoints

| Method | Endpoint | Description |
|--------|---------|-------------|
| `POST` | `/api/tracker/generate` | Generate a new stealth tracking link |
| `GET` | `/t/{tracking_id}` | The tracking URL (serves capture page) |
| `POST` | `/api/tracker/fingerprint/{id}` | Receives JS payload (GPS, screen, tz) |
| `GET` | `/api/tracker/links` | List all generated links with hit counts |
| `GET` | `/api/tracker/hits/{tracking_id}` | Get all hits for a specific link |
| `DELETE` | `/api/tracker/links/{tracking_id}` | Delete a link and its hit history |
| `GET` | `/api/tracker/debug` | Show all headers and extracted IP (debug) |

**Generate Link Request:**
```json
{
  "label": "Invoice PDF",
  "redirect_url": "https://www.google.com",
  "public_base": "https://xxxx.trycloudflare.com"
}
```

**Hit Response (example):**
```json
{
  "ip": "122.179.89.171",
  "timestamp": "2026-06-18T18:27:41Z",
  "ua": "Mozilla/5.0 (Linux; Android 14; SM-A546E)...",
  "geo": {
    "city": "Indore",
    "regionName": "Madhya Pradesh",
    "country": "India",
    "isp": "Bharti Airtel Limited",
    "org": "AS9498 Bharti Airtel Ltd., Telemedia Services",
    "as": "AS9498 Bharti Airtel Ltd.",
    "mobile": true,
    "proxy": false,
    "lat": 22.7196,
    "lon": 75.8577,
    "timezone": "Asia/Calcutta",
    "zip": "452001"
  },
  "fingerprint": {
    "gps": { "lat": 22.71823, "lon": 75.85501, "accuracy": 12.5 },
    "tz": "Asia/Calcutta",
    "lang": "en-IN",
    "screen": { "w": 384, "h": 857, "dpr": 2.8 }
  }
}
```

### Core Intelligence Endpoints

| Method | Endpoint | Description |
|--------|---------|-------------|
| `POST` | `/api/ingestion/collect` | Trigger OSINT collection |
| `GET` | `/api/ingestion/news` | Get latest threat news |
| `POST` | `/api/ioc/enrich` | Enrich an IOC (IP/domain/hash) |
| `GET` | `/api/ioc/list` | List all enriched IOCs |
| `POST` | `/api/cases` | Create investigation case |
| `GET` | `/api/cases` | List all cases |
| `GET` | `/api/hunter/status` | Get autonomous agent status |
| `POST` | `/api/aria/chat` | Stream AI analyst response (SSE) |
| `GET` | `/api/attribution/clusters` | Get ML actor clusters |
| `GET` | `/api/attack/heatmap` | MITRE ATT&CK technique frequency |

---

## 🖥 Dashboard

The React dashboard provides a unified interface for all N-CIIA capabilities:

| Page | Description |
|------|-------------|
| **Overview** | Real-time threat feed, risk score timeline, active alerts |
| **Canary Tracker** | Generate stealth links, view hits with GPS, IP OSINT, carrier data |
| **Scam Investigator** | Deep URL/phone/email analysis with IOC enrichment |
| **EXIF Forensics** | Image metadata extraction and geolocation |
| **Dark Web Scanner** | Paste site monitoring, breach data search |
| **Crypto Tracer** | Blockchain address tracking and wallet analysis |
| **IOC Lab** | Manual IOC enrichment with VirusTotal/AbuseIPDB/Shodan |
| **ARIA Analyst** | Streaming AI chat with RAG over your investigation database |
| **ATT&CK Map** | Interactive MITRE ATT&CK heatmap with Navigator export |
| **Hunter Agents** | Autonomous agent monitor with finding timeline |
| **Identity Graph** | Force-directed 3D graph of entity relationships |
| **Threat Globe** | Real-time 3D globe of threat origins |

---

## 🚢 Deployment

### Development (Default)

```bash
# Terminal 1: Backend
cd nciia-core && python run_server.py

# Terminal 2: Frontend  
cd nciia-dashboard && npm run dev

# Terminal 3: Cloudflare Tunnel (for Canary Tracker)
cloudflared.exe tunnel --url http://localhost:8000 --edge-ip-version 4
```

Or simply run `START_NCIIA.bat` from the project root.

### Production

For production deployments:
- Use a **named Cloudflare Tunnel** with a registered domain for a permanent HTTPS URL
- Deploy backend behind **nginx** or **Caddy** as a reverse proxy
- Build the frontend with `npm run build` and serve statically
- Use **PostgreSQL** instead of SQLite for the database

---

## 🤝 Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Key areas for contribution:
- Additional GeoIP/OSINT data providers
- New hunter agent logic
- MITRE ATT&CK technique coverage expansion
- Additional IOC enrichment sources
- UI/UX improvements

---

## 🔐 Security

Please review [SECURITY.md](SECURITY.md) for our security policy and responsible disclosure process.

**Important**: N-CIIA is designed for **lawful, authorized use only**. The Canary Tracker in particular must only be used against individuals you have legal authority to investigate. Unauthorized tracking of individuals may violate privacy laws in your jurisdiction.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Built with ❤️ for the security community · Report issues · Star if useful</sub>
</div>

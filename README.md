# N-CIIA — National Cyber Investigation & Intelligence Assistant

> Enterprise-grade, real-time cybersecurity threat intelligence platform.
> Combines a high-performance C++ behavioural analysis engine, a Python FastAPI intelligence backend, and a React-based analyst dashboard.

---

## Architecture

```
NCIIA/
├── nciia-perf/        C++20 shared library (.dll/.so) — stylometry, hashing, similarity
├── nciia-core/        Python 3.12 FastAPI backend — OSINT, personas, ML, WebSocket
└── nciia-dashboard/   React 18 + TypeScript + Vite — analyst dashboard UI
```

```
┌─────────────────────────────────────────────┐
│           nciia-dashboard (React)           │
│  • WebSocket (singleton)  • REST API client │
└────────────────┬────────────────────────────┘
                 │ HTTP / WebSocket
┌────────────────▼────────────────────────────┐
│          nciia-core (FastAPI / Python)       │
│  • /api/signals  • /api/personas            │
│  • /api/cases    • /api/threats             │
│  • /ws/live      • /health                  │
│  • Rate limiter  • API-key auth             │
└────────────────┬────────────────────────────┘
                 │ ctypes FFI
┌────────────────▼────────────────────────────┐
│        nciia-perf (C++20 .dll/.so)          │
│  • Stylometry  • RollingHash  • Similarity  │
└─────────────────────────────────────────────┘
```

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | ≥ 3.11 |
| Node.js | ≥ 18 |
| CMake | ≥ 3.16 |
| MSVC Build Tools **or** GCC/Clang | ≥ C++20 |

---

## Quick Start

### 1. Build the C++ performance library

```powershell
cd nciia-perf
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
# Copy the output DLL into nciia-core
copy build\Release\nciia_perf.dll ..\nciia-core\src\nciia\lib\
```

### 2. Set up the Python backend

```powershell
cd nciia-core
py -3.12 -m venv ..\venv
..\venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
# Edit .env and fill in NCIIA_LLM_API_KEY etc.
py run_server.py
# Server runs at http://localhost:8000
```

### 3. Set up the React dashboard

```powershell
cd nciia-dashboard
npm install
copy .env.example .env
npm run dev
# Dashboard runs at http://localhost:5173
```

Open **http://localhost:5173** in your browser.

---

## Configuration

### Backend (`nciia-core/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `NCIIA_LLM_API_KEY` | Groq / OpenAI API key | — |
| `NCIIA_LLM_PROVIDER` | `groq` \| `openai` \| `ollama` | `groq` |
| `NCIIA_API_API_KEY` | Optional bearer API key for all routes | (open) |
| `NCIIA_API_RATE_LIMIT` | Requests per window per IP | `100` |
| `NCIIA_API_CORS_ORIGINS` | JSON array of allowed origins | `["http://localhost:5173"]` |
| `NCIIA_ENVIRONMENT` | `development` \| `production` | `development` |

### Frontend (`nciia-dashboard/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_BASE_URL` | Backend base URL | `http://localhost:8000` |
| `VITE_WS_URL` | WebSocket base URL | `ws://localhost:8000` |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/health/ready` | Readiness probe (checks DB) |
| GET | `/api/signals` | List intelligence signals |
| GET | `/api/personas` | List / search personas |
| POST | `/api/personas` | Create new persona |
| GET | `/api/cases` | List investigation cases |
| POST | `/api/cases` | Create new case |
| GET | `/api/threats` | List threat indicators |
| POST | `/api/threats/block` | Block an IOC |
| POST | `/api/threats/unblock` | Unblock an IOC |
| WS | `/ws/live` | Real-time event stream |

Full OpenAPI docs (development only): **http://localhost:8000/docs**

---

## Security

- **Rate limiting**: sliding-window per client IP (configurable)
- **API-key auth**: optional `X-API-Key` enforcement via middleware
- **CORS**: explicit allow-list, no wildcard
- **Request tracing**: every response carries `X-Request-ID`
- **Audit log**: all mutations written to `audit_log` table
- **C++ FFI safety**: all exported functions wrapped in `try/catch`, with bounds-checked output buffers

---

## Project Status

| Component | Status |
|-----------|--------|
| C++ build (MSVC) | ✅ Fixed — all compilation errors resolved |
| Python backend | ✅ Enterprise middleware added |
| React dashboard | ✅ Live API, singleton WS, zero mock data |
| GitHub CI | 🔜 Planned |

---

## License

Proprietary — All rights reserved.

# N-CIIA Core

**National Cyber Investigation & Intelligence Assistant** - Core Intelligence Engine

## Overview

This is the Python-based intelligence brain of N-CIIA, responsible for:

- OSINT data ingestion and processing
- Digital persona reconstruction
- Threat scoring and analysis
- ML-based prediction
- Evidence packaging
- API endpoints (FastAPI)

## Installation

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows

# Install in development mode
pip install -e ".[dev]"

# Download spaCy model
python -m spacy download en_core_web_sm
```

## Quick Start

```bash
# Start the API server
nciia-server

# Or with uvicorn directly
uvicorn nciia.api.server:app --reload --host 0.0.0.0 --port 8000
```

## Project Structure

```
src/nciia/
├── api/           # FastAPI endpoints
├── ingestion/     # OSINT data ingestion
├── persona/       # Digital persona reconstruction
├── behavioral/    # Behavioral analysis
├── threat/        # Threat scoring
├── ml/            # ML models
├── evidence/      # Evidence packaging
├── llm/           # LLM integration
├── db/            # Database layer
├── models/        # Data models
└── utils/         # Utilities
```

## Testing

```bash
pytest tests/ -v --cov=nciia
```

## License

MIT License

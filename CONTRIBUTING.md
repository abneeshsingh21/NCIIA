# Contributing to N-CIIA

Thank you for investing your time in contributing to N-CIIA! 🎉

We welcome contributions from the security community — whether you're fixing a bug, adding a new enrichment source, building a hunter agent, or improving documentation.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Commit Convention](#commit-convention)
- [Pull Request Process](#pull-request-process)
- [Code Style](#code-style)
- [Architecture Decisions](#architecture-decisions)

---

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).  
By participating, you agree to uphold it. Please report unacceptable behaviour to the maintainers.

---

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/NCIIA.git
   cd NCIIA
   ```
3. **Create a branch** for your work:
   ```bash
   git checkout -b feat/my-new-feature
   # or
   git checkout -b fix/issue-123
   ```
4. Make your changes, following the guidelines below.
5. **Open a Pull Request** — we'll review it promptly.

---

## How to Contribute

### 🐛 Bug Reports

Before filing a bug, please:
- Search [existing issues](../../issues) to avoid duplicates.
- Check the [FAQ in the Wiki](../../wiki/FAQ).

Use the **[Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md)** and include:
- Steps to reproduce
- Expected vs. actual behaviour
- Environment (OS, Python version, Node version)
- Relevant logs (redact any sensitive data)

### 💡 Feature Requests

Use the **[Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md)** and describe:
- The problem you're solving
- Your proposed solution
- Alternatives considered

### 🔥 Good First Issues

Look for issues labelled [`good first issue`](../../issues?q=label%3A%22good+first+issue%22) — these are specifically curated for new contributors.

### 🧠 High-Priority Areas

| Area | What's Needed |
|------|--------------|
| Enrichment Sources | GreyNoise, Censys, SecurityTrails, PassiveTotal integrations |
| Hunter Agents | Supply chain monitor, brand abuse detector, typosquat watcher |
| C++ Engine | Linux/macOS CMake support, additional stylometric features |
| Dashboard | Attack timeline animator, kill-chain diagram, dark/light theme toggle |
| Tests | Backend: pytest coverage >80%; Frontend: Vitest + Testing Library |
| Docs | Tutorials, deployment guides, API cookbook |

---

## Development Setup

### Backend (nciia-core)

```bash
cd nciia-core
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp .env.example .env

# Run tests
pytest

# Lint
ruff check src/
mypy src/nciia/ --ignore-missing-imports

# Format
black src/
```

### Frontend (nciia-dashboard)

```bash
cd nciia-dashboard
npm install

# Dev server
npm run dev

# Type check
npx tsc --noEmit

# Build
npm run build

# Lint
npx eslint src/
```

### C++ Engine (nciia-perf)

```bash
cd nciia-perf

# Windows (MSVC)
cmake -B build -G "Visual Studio 17 2022" -A x64 -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release

# Linux (GCC)
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build

# Run tests
cd build && ctest -C Release --output-on-failure
```

---

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

**Types:**
| Type | When to use |
|------|------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Code restructure, no behaviour change |
| `perf` | Performance improvement |
| `test` | Adding or fixing tests |
| `build` | Build system, dependencies |
| `ci` | CI/CD configuration |
| `chore` | Maintenance, misc |

**Scopes:** `core`, `dashboard`, `perf`, `enrichment`, `attack`, `hunter`, `ml`, `docs`

**Examples:**
```
feat(enrichment): add GreyNoise API integration
fix(core): handle empty signals list in ATT&CK tagger
docs(readme): add Docker Compose deployment guide
perf(perf): replace vector with deque in RollingHash
test(core): add pytest coverage for enrichment engine
```

---

## Pull Request Process

1. **Keep PRs focused** — one feature or fix per PR. Large PRs are harder to review.
2. **Write tests** for new functionality. Aim for meaningful coverage, not vanity metrics.
3. **Update documentation** — README, docstrings, or the Wiki as appropriate.
4. **Fill out the PR template** completely.
5. **Pass all CI checks** — tests, linting, and type checking must be green.
6. **Request a review** from a maintainer.

### Review Criteria

PRs will be reviewed against these criteria:

- [ ] Does it solve a real problem?
- [ ] Is the code clean, readable, and consistent with the codebase?
- [ ] Are edge cases handled (empty inputs, API failures, network timeouts)?
- [ ] Are new dependencies justified and minimal?
- [ ] Is sensitive data (API keys, PII) never logged or hardcoded?
- [ ] Does it maintain backward compatibility or clearly document breaking changes?

### Merge Policy

- At least **1 maintainer approval** required.
- All CI checks must pass.
- PRs are merged using **squash merge** to keep history clean.

---

## Code Style

### Python (nciia-core)

- **Formatter:** `black` (line length 100)
- **Linter:** `ruff`
- **Type checker:** `mypy --strict`
- **Imports:** `isort` (via ruff)
- Use `from __future__ import annotations` at the top of every file.
- All public functions and classes must have docstrings.
- Use `get_logger(__name__)` for structured logging — never `print()`.
- Never use bare `except:` — always catch specific exceptions.

### TypeScript (nciia-dashboard)

- **Strict mode** enabled (`"strict": true` in tsconfig.json).
- No `any` types — use proper interfaces.
- No inline styles — use CSS classes defined in `index.css` or `advanced.css`.
- No mock/hardcoded data in components — all data from API or WebSocket.
- Error states must be handled — every `fetch()` needs a `catch`.

### C++ (nciia-perf)

- All exported FFI functions must be `noexcept` with `try/catch`.
- MSVC-compatible compiler flags only (no `-O3`, `-g`, etc.).
- Use `std::deque` for sliding-window operations (not `std::vector::erase(begin())`).
- Bounds-check all pointer writes with `out_size` parameter pattern.

---

## Architecture Decisions

### Why SQLite?

Keeps deployment simple — no separate database process. `aiosqlite` provides async access. For high-volume deployments (>100 analysts), PostgreSQL integration is on the roadmap.

### Why Groq / LLaMA-3?

Speed. Groq's LPU delivers tokens 10–25× faster than GPU-based APIs, which is critical for the streaming analyst UX. The platform also supports OpenAI-compatible APIs and local Ollama for air-gapped deployments.

### Why C++ for stylometry?

Python's GIL and dynamic dispatch make tight numerical loops expensive. The C++ DLL via ctypes achieves 50–200× speedup for text fingerprinting on large corpora.

### Why no Redux/Zustand?

The WebSocket singleton + React Context pattern covers all shared state needs. Adding a state management library would add complexity without meaningful benefit at this scale.

---

## Questions?

Open a [Discussion](../../discussions) — we're happy to help you get oriented.

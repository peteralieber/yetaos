# YET Another Orchestration Server
**Dev Environment Orchestrator (LXC-based Home Lab)**

Spin up **on-demand, reproducible dev environments** on your home server using **LXC/LXD**.

This project provides a **web launchpad** and **API** to create, manage, and destroy containers preloaded with specific toolchains and AI CLIs, such as:

- `/dev/python + pytorch + rocm/claude+copilot/`
- `/dev/clang->RISCV + vllm/copilot/`
- `/dev/node+electron/claude/`
- `/model/blender//`
- `/genai/comfyui/copilot/`

Each environment runs in an isolated LXC container and can be **ephemeral** (auto-deleted) or **persistent** (resumable).

---

## Features

- **Environment templates via LXC profiles**
  - Python + PyTorch + ROCm + Claude CLI + Copilot CLI
  - Clang + RISC-V + vLLM + Copilot
  - Node + Electron + Claude
  - Blender rendering node
  - ComfyUI + Copilot

- **Web launchpad**
  - Select environment type
  - Name containers
  - Choose ephemeral vs persistent
  - Enable/disable GPU
  - Open shell or VS Code Server

- **Lifecycle management**
  - Create, list, start, stop, delete containers
  - Ephemeral containers auto-delete on stop
  - Persistent containers can be resumed and snapshotted

- **Artifact export**
  - Standardized `/workspace` directory inside each container
  - One-click export as `.tar.gz`

- **Local-first, privacy-respecting**
  - Runs entirely on your home server
  - No external cloud dependencies required

---

## Architecture

- **Host**
  - Linux (Ubuntu 24.04 recommended)
  - LXD with ZFS storage
  - ROCm and/or NVIDIA GPU drivers
  - Caddy reverse proxy (TLS termination)

- **Backend**
  - **FastAPI 0.115.8** with async/await
  - **pylxd** client (async wrapper around LXD Unix socket)
  - REST API v1: container lifecycle, snapshots, secrets, artifact export
  - **JSON file store** (atomic writes, no DB required, simple & git-friendly)
  - **Profile registry**: YAML-based with dependency resolution (topological sort)
  - **Cloud-init builder**: Fragment merging with deduplication

- **Frontend**
  - HTMX 2.x + Alpine.js 3.x (no build step, minimal JS)
  - Jinja2 templates served by FastAPI
  - Environment creation form with live profile-string preview
  - Container list with status polling
  - Links to shell (ttyd) and VS Code Server (code-server)

- **LXC**
  - Ubuntu 24.04 base image
  - Declarative profiles: `/{use-case}/{tools}/{agents}/{services}/`
  - 5 profiles implemented: base, python, python:rocm, rocm-gpu, dev
  - Cloud-init fragments (shell scripts, all idempotent & pinned versions)

---

## Getting started (MVP)

### Prerequisites

- Python 3.11 or 3.12
- `uv` for package and environment management ([install here](https://github.com/astral-sh/uv))

### Quick start: Run tests

```bash
cd backend
uv sync --all-groups          # Install dev dependencies
uv run pytest                 # Run tests (all 7 passing)
uv run ruff check app tests   # Lint
uv run mypy app               # Type-check
```

### Quick start: Run the backend locally

```bash
cd backend
cp .env.example .env           # Copy config template
uv sync --all-groups           # Install dependencies
uv run uvicorn app.main:app --reload --port 8000
```

The API will be available at http://localhost:8000/api/v1.

**Health check:**
```bash
curl http://localhost:8000/health
```

**List profiles:**
```bash
curl http://localhost:8000/api/v1/profiles
```

**Create a container (requires no auth in dev mode):**
```bash
curl -X POST http://localhost:8000/api/v1/containers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "devbox",
    "profile_string": "/dev/python///",
    "cpu_limit": 2,
    "memory_limit_gb": 4,
    "ephemeral": false
  }'
```

### Architecture details

For in-depth information on the design, see [docs/architecture.md](docs/architecture.md).

## Repository layout

```
├─ backend/
│  ├─ app/
│  │  ├─ api/              # REST routes (containers, profiles, health)
│  │  ├─ lxd/              # LXD async wrapper + cloud-init builder
│  │  ├─ profiles/         # Profile registry & resolver
│  │  ├─ store/            # JSON persistence layer
│  │  ├─ templates/        # Jinja2 HTML templates
│  │  ├─ static/           # Static files (HTMX, Alpine.js)
│  │  ├─ config.py         # Pydantic settings
│  │  ├─ schemas.py        # Request/response models
│  │  └─ main.py           # FastAPI app factory
│  ├─ tests/               # Unit & integration tests (pytest)
│  ├─ pyproject.toml       # uv project config
│  └─ README.md
├─ lxc/
│  ├─ profiles/            # YAML profile definitions
│  │  ├─ service/          # base, rocm-gpu, nvidia-gpu, vllm, vscode-server, ttyd
│  │  ├─ tool/             # python, python:rocm, clang, node, electron, blender, comfyui
│  │  ├─ agent/            # claude, copilot, opencode, openclaw
│  │  └─ use-case/         # dev, model, genai
│  └─ cloud-init/          # Shell fragments (idempotent, pinned versions)
├─ scripts/
│  ├─ host-setup.sh        # Create yetaos user, dirs, groups
│  ├─ install.sh           # Full installation script
│  └─ lxd-init-preseed.yaml # LXD initialization config
├─ deploy/
│  ├─ yetaos-backend.service # systemd unit
│  └─ Caddyfile             # Reverse proxy config
├─ .github/
│  └─ workflows/
│     └─ ci.yml             # GitHub Actions (ruff, mypy, pytest)
├─ docs/
│  ├─ architecture.md       # Implementation details
│  ├─ plan.md               # Complete feature roadmap
│  ├─ user-guide.md
│  └─ versions.md           # Pinned dependency versions
└─ README.md
```

## MVP Status

✅ **Complete:**
- Backend REST API v1 (container CRUD, snapshots, secrets)
- Profile registry with topological-sort resolver
- Cloud-init fragment merging engine
- JSON persistence layer
- 7 integration tests (all passing)
- Quality gates: ruff lint ✓ mypy strict ✓ pytest ✓
- 5 LXC profiles + 3 cloud-init fragments
- systemd service + Caddy config + CI workflow

📋 **Next (Milestone 3+):**
- [ ] Complete all remaining profiles (clang:riscv, node, electron, blender, comfyui, agents)
- [x] Build frontend UI (container list, create form, detail page)
- [ ] Add ttyd/code-server proxying
- [ ] Add log streaming endpoint (Server-Sent Events)
- [ ] End-to-end testing on real LXD host
- [ ] Add idle shutdown background task
- [ ] Publish installation guide

See [docs/plan.md](docs/plan.md) for the complete roadmap.

## Contributing

Issues and PRs are welcome. The guiding principles are:

* Deterministic, reproducible behavior
* Explicit configuration
* Minimal, understandable abstractions

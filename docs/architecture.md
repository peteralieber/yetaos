# Project Architecture

## High-level overview

YETAOS is a **FastAPI-based orchestrator** for spinning up reproducible, declarative LXC containers on a home server. Containers are composed from YAML-based **profiles** (service, tool, agent, use-case categories) with automatic dependency resolution, cloud-init fragment merging, and a REST API for lifecycle management.

```
┌─────────────────────────────────────────────────────┐
│ Browser (HTMX + Alpine.js)                          │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP/HTTPS
        ┌──────────────┴──────────────┐
        │  Caddy Reverse Proxy        │  :443 → :8000
        │  (TLS termination)          │  Proxies: shell, VS Code
        └──────────────┬──────────────┘
                       │
    ┌──────────────────┴──────────────────┐
    │ FastAPI 0.115.8                     │
    │ ┌─────────────────────────────────┐ │
    │ │ REST API v1 Routes              │ │
    │ │ - /api/v1/containers            │ │
    │ │ - /api/v1/profiles              │ │
    │ │ - /health                       │ │
    │ └────────────┬─────────────────────┘ │
    │              │                       │
    │ ┌────────────┼─────────────────────┐ │
    │ │ Core Layer │                     │ │
    │ │ ┌──────────▼─────┐ ┌───────────┐│ │
    │ │ │ LXD Service    │ │  Profile  ││ │
    │ │ │ (async wrapper)│ │ Resolver  ││ │
    │ │ └────────────────┘ └───────────┘│ │
    │ │ ┌────────────────┐ ┌───────────┐│ │
    │ │ │ Cloud-init     │ │ JSON      ││ │
    │ │ │ Builder        │ │ Store     ││ │
    │ │ └────────────────┘ └───────────┘│ │
    │ └────────────────────────────────┘ │
    └──────────────┬─────────────────────┘
                   │ Unix socket
        ┌──────────▼─────────────┐
        │ LXD Daemon             │
        │ /var/snap/lxd/common/  │
        │ lxd/unix.socket        │
        └──────────┬─────────────┘
                   │
        ┌──────────▼──────────────────────┐
        │ LXC Containers                  │
        │ ubuntu/24.04 + profiles         │
        │ ┌─────────────────────────────┐ │
        │ │ /dev/python:rocm            │ │
        │ │ /dev/clang:riscv            │ │
        │ │ /genai/comfyui              │ │
        │ │ (more as we implement)      │ │
        │ └─────────────────────────────┘ │
        └────────────────────────────────┘
```

---

## Backend: Core components

### REST API (FastAPI)

**Routes** (`app/api/`):
- `GET /health` — Liveness check
- `GET /api/v1/profiles` — List available profiles
- `GET /api/v1/profiles/resolve?profile_string=/dev/python///` — Resolve dependency order
- `POST /api/v1/containers` — Create container
- `GET /api/v1/containers` — List containers
- `GET /api/v1/containers/{name}` — Get container detail
- `POST /api/v1/containers/{name}/start` — Start container
- `POST /api/v1/containers/{name}/stop` — Stop container
- `DELETE /api/v1/containers/{name}` — Delete container
- `POST /api/v1/containers/{name}/snapshot` — Create snapshot
- `PUT /api/v1/containers/{name}/secrets` — Update secrets

**Auth**: Bearer token (optional in dev mode; can be bypassed from localhost).

### Profile Registry & Resolver (`app/profiles/`)

**Registry** (`registry.py`):
- Loads YAML files from `lxc/profiles/` directory tree
- Parses into `ProfileDefinition` Pydantic models
- Maps `category/name[:subprofile]` → metadata (description, dependencies, LXD config, cloud-init script path)

**Profile YAML format**:
```yaml
name: tool/python
description: Python 3.11 and uv tooling
category: tool
depends:
  - service/base
lxd:
  config:
    limits.cpu: "2"
  devices: {}
cloud_init: lxc/cloud-init/tool/python.sh
```

**Resolver** (`resolver.py`):
- Parses profile string: `/{use-case}/{tools}/{agents}/{services}/`
  - e.g., `/dev/python:rocm+clang/claude+copilot/rocm-gpu+vllm/`
  - Empty segment means "skip" (e.g., `//` skips agents)
- Returns list of `category/name[:sub]` tokens
- Performs **depth-first, topological-sort resolution** on dependencies
- Detects and reports cycles
- Returns **ordered profile list** respecting all transitive deps

**Example resolution**:
```
Input:  /dev/python:rocm/claude/rocm-gpu/
Tokens: [use-case/dev, tool/python:rocm, agent/claude, service/rocm-gpu]
↓ (after resolver.resolve())
Output: [
  service/base,           # dep of dev
  service/rocm-gpu,       # requested
  tool/python,            # requested (no rocm sub)
  tool/python:rocm,       # requested sub
  agent/claude,           # requested
  use-case/dev            # requested
]
```

### Cloud-Init Builder (`app/lxd/cloud_init.py`)

- Reads shell fragments from disk (one per profile, under `lxc/cloud-init/`)
- For each profile in the resolved list, extracts comments and non-empty commands
- **Deduplicates** commands from the same profile (seen set)
- **Merges** into a single cloud-config YAML document:
  ```yaml
  #cloud-config
  package_update: true
  package_upgrade: false
  write_files:
    - path: /etc/dev-orchestrator/metadata.json
      content: |
        { "profile_string": "...", "resolved_profiles": [...], "created_at": "..." }
  runcmd:
    - mkdir -p /workspace /models /data
    - apt-get update
    - apt-get install -y python3
    - python3 -m pip install --upgrade uv==0.6.10
    # ... (rocm, agents, etc.)
  ```
- **Respects ordering**: fragments applied in resolved profile order

### LXD Service (`app/lxd/containers.py`)

**Design**: Async wrapper around `pylxd` client to avoid blocking FastAPI event loop.

```python
async def create_container(name, profiles, user_data, config):
    # 1. Build LXD container definition
    # 2. Call pylxd in executor (non-blocking)
    # 3. Start container
    
async def get_status(name):
    # 1. Fetch container from LXD
    # 2. Return status string (running, stopped, error, etc.)
```

**No real GPU/device passthrough yet** in MVP — profiles define the config, but actual passthrough happens when profiles are applied to real LXD.

### JSON Store (`app/store/json_store.py`)

**Why not SQLite?**
At home-server scale (realistic max: tens to low-hundreds of containers):
- No relational queries needed
- Simple flat collection of metadata
- Human-readable and git-friendly
- Trivially backed up with `cp`

**Schema**:
```json
{
  "myenv": {
    "name": "myenv",
    "profile_string": "/dev/python:rocm/claude/rocm-gpu/",
    "resolved_profiles": ["service/base", "service/rocm-gpu", "tool/python", "tool/python:rocm", "agent/claude"],
    "ephemeral": false,
    "gpu_enabled": true,
    "created_at": "2026-04-30T00:00:00Z",
    "last_used": null,
    "status": "stopped",
    "workspace_path": "/srv/yetaos/workspaces/myenv"
  }
}
```

**Atomicity**: Writes to `.tmp` file, then `os.replace()` to prevent corruption on crash.  
**Concurrency**: `threading.Lock` (sufficient for single Uvicorn worker).

### Configuration (`app/config.py`)

Pydantic `Settings` from `.env`:
```dotenv
YETAOS_LXD_SOCKET=/var/snap/lxd/common/lxd/unix.socket
YETAOS_STORE_PATH=/tmp/yetaos/containers.json
YETAOS_PROFILES_DIR=../lxc/profiles
YETAOS_CLOUD_INIT_DIR=../lxc/cloud-init
YETAOS_WORKSPACES_DIR=/srv/yetaos/workspaces
YETAOS_SECRETS_DIR=/srv/yetaos/secrets
YETAOS_API_KEY=change-me          # or empty for local-only mode
YETAOS_HOST=0.0.0.0
YETAOS_PORT=8000
YETAOS_LOG_LEVEL=info
```

---

## Frontend: HTMX + Alpine.js (Minimal, no build step)

**Templates** (`app/templates/`):
- `base.html` — Layout, navigation
- `index.html` — Dashboard (container list, polling)
- `create.html` — Form for new environment (TBD)
- `container.html` — Detail page (TBD)

**Static assets** (`app/static/`):
- HTMX 2.x (via CDN)
- Alpine.js 3.x (via CDN)
- Pico.css or minimal custom styles

**Features** (MVP scope):
- Poll container status every 10 seconds (HTMX)
- Show logs from cloud-init-output.log (SSE, TBD)
- Direct links to `/containers/{name}/shell` and `/containers/{name}/code` (proxied)

---

## LXC Profiles & Cloud-Init

### Implemented profiles

**Service profiles** (`service/`):
- `base.yaml` — Base Ubuntu 24.04, common packages, mounts
- `rocm-gpu.yaml` — AMD GPU device passthrough (KFD, DRI)

**Tool profiles** (`tool/`):
- `python.yaml` — Python 3.11, uv
- `python:rocm.yaml` — Subprofile, PyTorch ROCm wheels
- `clang-riscv.yaml` — Clang 18 + RISC-V cross-compilation toolchain
- `node.yaml` — Node.js 20 LTS (via NodeSource)
- `electron.yaml` — Electron framework + display libs (depends on `tool/node`)

**Use-case profiles** (`use-case/`):
- `dev.yaml` — Generic dev container (base + shell)
- `blender.yaml` — Blender 4.1 LTS
- `comfyui.yaml` — ComfyUI stable-diffusion node graph (depends on `tool/python:rocm`)
- `agents.yaml` — AI CLI agents: Claude CLI + GitHub Copilot CLI (depends on `tool/node`)

### Cloud-init fragments

All idempotent, non-interactive, with pinned package versions:

**`service/base.sh`**:
```bash
set -e
mkdir -p /workspace /models /data
apt-get update
apt-get install -y curl git ca-certificates sudo htop jq build-essential
```

**`tool/python.sh`**:
```bash
set -e
apt-get update
apt-get install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update
apt-get install -y python3.11 python3.11-venv python3.11-dev
python3 -m pip install --upgrade uv==0.6.10
```

**`tool/python-rocm.sh`**:
```bash
set -e
python3 -m pip install torch==2.3.0+rocm6.1 --index-url https://download.pytorch.org/whl/rocm6.1
```

---

## Deployment

### Host setup (`scripts/host-setup.sh`)
- Creates `yetaos` system user
- Adds to `lxd`, `video`, `render` groups
- Creates `/srv/yetaos/{db,models,data,workspaces,secrets}`

### Installation (`scripts/install.sh`)
- Runs host setup
- Copies `.env.example` to `/etc/yetaos/.env`
- Installs via `uv` to `/opt/yetaos/venv`
- Copies systemd service & Caddy config
- Enables services

### Systemd service (`deploy/yetaos-backend.service`)
```ini
[Unit]
Description=YETAOS Dev Orchestrator Backend
After=network.target lxd.service

[Service]
User=yetaos
Group=yetaos
EnvironmentFile=/etc/yetaos/.env
ExecStart=/opt/yetaos/venv/bin/uvicorn app.main:app --workers 1 ...

[Install]
WantedBy=multi-user.target
```

### Reverse proxy (`deploy/Caddyfile`)
```caddy
dev-orchestrator.local {
    tls internal
    reverse_proxy /api/* localhost:8000
    handle /* { reverse_proxy localhost:8000 }
    # Proxied shell & code-server per container (TBD)
}
```

---

## Testing

**Unit tests** (`backend/tests/`):
- `test_resolver.py` — Profile string parsing, dependency resolution, cycles
- `test_cloud_init.py` — Fragment merging, ordering
- `test_store.py` — JSON persistence, atomicity
- `test_api.py` — HTTP endpoints (mocked LXD client)

**Mocked LXD**: `FakeClient` in `conftest.py` provides in-memory container simulation.  
**No real containers touched** during tests.

**CI** (`.github/workflows/ci.yml`):
- Ruff lint
- mypy type-check (strict mode)
- pytest (all groups)

---

## Security

- LXD socket accessible only by `yetaos` user
- API key stored in `/etc/yetaos/.env` (mode 0600)
- Secrets injected to tmpfs at container start, never persisted
- No container runs with `security.privileged = true`
- Profiles define minimal allow-rules (AppArmor)

---

## Next phases

**Milestone 3** (Frontend + Shell):
- Build create/list/detail UI templates
- Integrate ttyd/code-server proxying
- Add log streaming endpoint (SSE)

**Milestone 4** (Complete profiles — ✅ Done):
- Added `tool/clang:riscv`, `tool/node`, `tool/electron`
- Added `use-case/blender`, `use-case/comfyui`, `use-case/agents`
- 35 tests all passing

**Milestone 5** (Ops):
- Idle shutdown background task
- E2E testing on real LXD host
- Installation guide

See [docs/plan.md](../docs/plan.md) for the full roadmap.

# Implementation Plan

This document outlines the complete, end‑to‑end implementation plan for the Dev Environment Orchestrator (YETAOS) using LXC/LXD, a FastAPI backend, and a lightweight HTMX/Alpine.js web UI.

> **Decisions made here (rationale in parentheses):**
> - **Backend**: FastAPI (Python 3.11+) + `pylxd` — rich ecosystem, fast iteration, pylxd is the canonical Python LXD client
> - **Frontend**: HTMX + Alpine.js — no build step, minimal JS, fits the "functional over fancy" principle
> - **Reverse proxy**: Caddy — automatic TLS via ACME, readable single-file config
> - **Metadata store**: JSON file (`containers.json`) — human-readable, trivially backed up, no migrations, sufficient for the realistic scale of a home server (tens to low-hundreds of containers)
> - **Authentication**: Bearer API-key token stored in `.env`; passthrough on loopback for dev
> - **Shell access**: `ttyd` running inside each container on a fixed port, proxied by Caddy
> - **VS Code Server**: `code-server` running inside each container, proxied by Caddy
> - **Log streaming**: Server-Sent Events (SSE) endpoint backed by the LXD `exec` log tail

---

## 1. Host System Setup

### 1.1 Install and initialize LXD
- Install LXD via snap: `sudo snap install lxd`
- Run `lxd init --preseed` with a preseed YAML (committed to `scripts/lxd-init-preseed.yaml`):
  - Storage pool: ZFS on a dedicated partition or loop file (`lxd-pool`)
  - Bridge: `lxdbr0`, IPv4 `10.100.0.1/24`, NAT enabled
  - IPv6: disabled by default (can be re-enabled in preseed)
  - Remote images: only `ubuntu:` — no other remotes needed
- Add the service user to the `lxd` group: `sudo usermod -aG lxd $SERVICE_USER`
- Verify: `lxc list` returns an empty table with no errors

### 1.2 Install GPU drivers
- **ROCm** for AMD GPUs (primary target):
  - Install `rocm-hip-sdk` from AMD's APT repository (pin to a specific minor version, e.g. `6.1.x`)
  - Add service user to `video` and `render` groups
  - Validate: `rocminfo | grep "Agent 2"` returns a GPU agent; `clinfo` shows a device
  - Record validated ROCm version in `docs/versions.md`
- **NVIDIA** (secondary, optional):
  - Install drivers from `ubuntu-drivers-common` (`ubuntu-drivers autoinstall`)
  - Install `libnvidia-compute-*` for container passthrough
  - Validate: `nvidia-smi` shows the GPU

### 1.3 Create shared host directories
- `/srv/yetaos/models` — read-only model weight cache (mounted into containers)
- `/srv/yetaos/data` — optional shared datasets (mounted read-write)
- `/srv/yetaos/workspaces/<container-name>` — persistent workspace per container
- `/srv/yetaos/secrets` — per-container secret files (mode 0700, owned by service user)
- `/srv/yetaos/db` — JSON metadata store directory (`containers.json`)
- Create all dirs in `scripts/host-setup.sh` (idempotent: `mkdir -p`)

### 1.4 Service user
- Create a dedicated `yetaos` system user: `sudo useradd -r -s /bin/false yetaos`
- Add to groups: `lxd`, `video`, `render`
- All host directories under `/srv/yetaos` owned by `yetaos:yetaos`

---

## 2. LXC Profiles (Environment Templates)

### 2.1 Profile-string syntax

The short-hand CLI/API syntax for composing an environment is:

```
/<use-case>/<tools>/<agents>/<services>/
```

- Each segment is one or more `{profile}[:{subprofile}]` entries joined by `+`
- Empty segment = "none" (e.g. `//` skips agents)
- Examples:
  - `/dev/python/claude+copilot/rocm-gpu/`
  - `/dev/clang:riscv+qemu:riscv/copilot/vllm:gemma4/`
  - `/dev/node+electron/claude//`
  - `/model/blender///`
  - `/genai/comfyui/copilot/rocm-gpu/`

### 2.2 Profile YAML format

Each profile is a standalone YAML file under `lxc/profiles/`.  
The orchestrator reads these files to build the LXD profile set and to locate the matching cloud-init fragment.

```yaml
# lxc/profiles/<category>/<name>[/<subprofile>].yaml
name: dev/clang:riscv          # canonical profile identifier
description: "Clang cross-compiler targeting RISC-V"
category: tool                  # tool | agent | service | use-case
depends:
  - service/base                 # profiles that must be applied first

lxd:
  # Raw LXD profile config merged into the container config
  config:
    limits.cpu: "4"
    limits.memory: "8GB"
  devices: {}                    # additional device mappings (see service profiles)

cloud_init: lxc/cloud-init/dev/clang-riscv.sh   # path relative to repo root
```

Fields:
| Field | Required | Description |
|---|---|---|
| `name` | yes | Canonical `category/name[:sub]` identifier |
| `description` | yes | Human-readable label shown in UI |
| `category` | yes | `tool`, `agent`, `service`, or `use-case` |
| `depends` | no | List of profiles that must be applied before this one |
| `lxd.config` | no | LXD container config keys merged in |
| `lxd.devices` | no | LXD device entries merged in |
| `cloud_init` | no | Path to the cloud-init shell fragment for this profile |

### 2.3 Profile dependency resolution

The orchestrator resolves the full ordered profile list at container-create time:

1. Parse the profile string into a list of requested leaf profiles.
2. For each profile, recursively collect `depends` (depth-first, post-order).
3. Deduplicate while preserving first occurrence (stable topological sort).
4. The resolved list is applied to LXD in order; cloud-init fragments are concatenated in the same order.
5. The full resolved list is stored in the container metadata for reproducibility.

### 2.4 Baseline profile (`lxc/profiles/service/base.yaml`)
- Ubuntu 24.04 LTS (`ubuntu:24.04`)
- Networking: `lxdbr0`
- Default limits: 2 CPU, 4 GB RAM (overridable per profile)
- Cloud-init support enabled (`user.user-data` key)
- Mounts: `/workspace`, `/models` (read-only), `/data` (optional)
- Common packages pre-installed: `curl`, `git`, `ca-certificates`, `sudo`, `htop`, `jq`

### 2.5 Service profiles
- `lxc/profiles/service/rocm-gpu.yaml`
  - Devices: `/dev/kfd` (char, major 234), `/dev/dri/renderD128` (char)
  - Config: `raw.apparmor: "deny /proc/sysrq-trigger rwklx, ..."`
  - Adds `video` and `render` groups inside container
- `lxc/profiles/service/nvidia-gpu.yaml`
  - Devices: `/dev/nvidia0`, `/dev/nvidiactl`, `/dev/nvidia-uvm`
  - Config: `nvidia.runtime: "true"`, `nvidia.driver.capabilities: "compute,utility"`
- `lxc/profiles/service/vllm.yaml`
  - Depends: one of `rocm-gpu` or `nvidia-gpu`
  - Cloud-init: install vLLM from PyPI, configure startup service
  - Mounts: `/models` → `/srv/yetaos/models` (read-only)
  - Exposes port 8000 internally
- `lxc/profiles/service/vscode-server.yaml`
  - Cloud-init: install `code-server` pinned version
  - Starts `code-server` as a systemd user service on port 8080 inside container
  - Mounts: `/workspace`
- `lxc/profiles/service/ttyd.yaml`
  - Cloud-init: install `ttyd` from GitHub releases (pinned version)
  - Starts `ttyd` as a systemd service on port 7681 inside container

### 2.6 Agent profiles
- `lxc/profiles/agent/claude.yaml`
  - Cloud-init: install Claude CLI (pinned npm package `@anthropic-ai/claude-code`)
  - Injects `ANTHROPIC_API_KEY` from `/run/secrets/anthropic_api_key` at container start
- `lxc/profiles/agent/copilot.yaml`
  - Cloud-init: install GitHub CLI (`gh`), configure Copilot extension
  - Injects `GITHUB_TOKEN` from `/run/secrets/github_token`
- `lxc/profiles/agent/opencode.yaml`
  - Cloud-init: install `opencode` CLI (pinned npm package)
- `lxc/profiles/agent/openclaw.yaml`
  - Cloud-init: install `openclaw` CLI (pinned npm package)

### 2.7 Tool profiles
- `lxc/profiles/tool/python.yaml`
  - Cloud-init: Python 3.11 via deadsnakes PPA, `uv`, `venv`
  - Subprofile `python:rocm` — adds PyTorch ROCm wheels; depends on `service/rocm-gpu`
- `lxc/profiles/tool/clang.yaml`
  - Subprofile `clang:riscv` — Clang 18 + RISC-V GNU toolchain + QEMU user-mode emulation
- `lxc/profiles/tool/node.yaml`
  - Cloud-init: Node.js LTS via NodeSource APT repo, `pnpm`
- `lxc/profiles/tool/electron.yaml`
  - Depends: `tool/node`
  - Cloud-init: Electron builder, required system libraries for headless builds
- `lxc/profiles/tool/blender.yaml`
  - Cloud-init: Blender 4.x from official tar release (pinned), symlinked to `/usr/local/bin/blender`
- `lxc/profiles/tool/comfyui.yaml`
  - Depends: `tool/python`, `service/rocm-gpu` (or `nvidia-gpu`)
  - Cloud-init: clone ComfyUI at a pinned commit, install requirements, systemd service on port 8188

### 2.8 Use-case profiles
- `lxc/profiles/use-case/dev.yaml` — generic dev container; depends on `service/base`, `service/vscode-server`, `service/ttyd`
- `lxc/profiles/use-case/model.yaml` — rendering/model workload; depends on `service/base`, `service/ttyd`
- `lxc/profiles/use-case/genai.yaml` — generative AI workload; depends on `service/base`, `service/rocm-gpu`, `service/ttyd`

---

## 3. Cloud-Init Scripts

### 3.1 Script structure

Each profile's cloud-init fragment is a plain shell script stored at `lxc/cloud-init/<category>/<name>.sh`.  
All scripts must be:
- **Idempotent**: safe to run twice without side effects
- **Non-interactive**: no prompts; use `-y` / `--yes` / `DEBIAN_FRONTEND=noninteractive`
- **Versioned**: pin every package to a specific version; record versions in a comment at the top

The orchestrator generates a single merged cloud-init `user-data` document by concatenating the `runcmd` sections from each fragment in dependency order, wrapped in a standard header:

```yaml
#cloud-config
package_update: true
package_upgrade: false

write_files:
  - path: /etc/dev-orchestrator/metadata.json
    content: |
      { "profile_string": "...", "resolved_profiles": [...], "created_at": "..." }

runcmd:
  # --- service/base ---
  - ...
  # --- tool/python ---
  - ...
  # --- agent/claude ---
  - ...
```

Duplicate `runcmd` entries from the same profile are eliminated by tracking which profiles have already been merged.

### 3.2 Cloud-init fragments per profile

**`lxc/cloud-init/service/base.sh`**
```bash
# Creates standard directories and common tooling
mkdir -p /workspace /models /data
apt-get install -y curl git ca-certificates sudo htop jq build-essential
```

**`lxc/cloud-init/tool/python.sh`**
```bash
# Python 3.11 + uv
add-apt-repository -y ppa:deadsnakes/ppa
apt-get install -y python3.11 python3.11-venv python3.11-dev
pip install --upgrade uv==0.4.x   # pin version
```

**`lxc/cloud-init/tool/python-rocm.sh`** (subprofile)
```bash
# PyTorch with ROCm 6.1
pip install torch==2.3.0+rocm6.1 --index-url https://download.pytorch.org/whl/rocm6.1
```

**`lxc/cloud-init/tool/clang-riscv.sh`**
```bash
# Clang 18 + RISC-V toolchain
apt-get install -y clang-18 lld-18 gcc-riscv64-linux-gnu binutils-riscv64-linux-gnu qemu-user
update-alternatives --install /usr/bin/clang clang /usr/bin/clang-18 100
```

**`lxc/cloud-init/tool/node.sh`**
```bash
# Node.js LTS via NodeSource
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs
npm install -g pnpm@9
```

**`lxc/cloud-init/tool/blender.sh`**
```bash
# Blender 4.1.1 CLI
BLENDER_VERSION=4.1.1
curl -L https://download.blender.org/release/Blender${BLENDER_VERSION%.*}/blender-${BLENDER_VERSION}-linux-x64.tar.xz -o /tmp/blender.tar.xz
tar -xJf /tmp/blender.tar.xz -C /opt
ln -sf /opt/blender-${BLENDER_VERSION}-linux-x64/blender /usr/local/bin/blender
```

**`lxc/cloud-init/tool/comfyui.sh`**
```bash
# ComfyUI at pinned commit
git clone https://github.com/comfyanonymous/ComfyUI /opt/comfyui
cd /opt/comfyui && git checkout <pinned-commit>
pip install -r requirements.txt
# systemd unit written via write_files in merged cloud-init
```

**`lxc/cloud-init/agent/claude.sh`**
```bash
# Claude CLI (claude-code)
npm install -g @anthropic-ai/claude-code@0.x.x
```

**`lxc/cloud-init/agent/copilot.sh`**
```bash
# GitHub CLI + Copilot extension
apt-get install -y gh
gh extension install github/gh-copilot
```

**`lxc/cloud-init/service/vscode-server.sh`**
```bash
# code-server 4.x
VERSION=4.93.1
curl -fsSL https://github.com/coder/code-server/releases/download/v${VERSION}/code-server_${VERSION}_amd64.deb -o /tmp/cs.deb
dpkg -i /tmp/cs.deb
systemctl enable --now code-server@ubuntu
```

**`lxc/cloud-init/service/ttyd.sh`**
```bash
# ttyd 1.7.7
curl -L https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64 -o /usr/local/bin/ttyd
chmod +x /usr/local/bin/ttyd
# systemd unit written via write_files in merged cloud-init
```

### 3.3 Secret injection at container start

Secrets (API keys) are NOT baked into cloud-init.  
Instead, at container start the orchestrator:

1. Reads the per-container secret file from `/srv/yetaos/secrets/<container-name>.env`
2. Uses `lxc exec <name> -- sh -c "..."` to write each secret to `/run/secrets/<key>` (tmpfs, mode 0400)
3. Agent profiles source from `/run/secrets/` at shell init time via `/etc/profile.d/yetaos-secrets.sh`

This means secrets are never stored inside the container image or cloud-init user-data.

---

## 4. Backend Service (FastAPI)

### 4.1 Technology choices
- **Language**: Python 3.11
- **Framework**: FastAPI with Uvicorn
- **LXD client**: `pylxd` (talks to `/var/snap/lxd/common/lxd/unix.socket`)
- **Metadata store**: JSON file via Pydantic (see §4.7)
- **Config**: Pydantic Settings loaded from `.env`
- **Async**: FastAPI async routes; blocking pylxd calls wrapped in `asyncio.run_in_executor`

### 4.2 Project layout

```
backend/
├─ app/
│  ├─ main.py              # FastAPI app factory, startup/shutdown hooks
│  ├─ config.py            # Pydantic Settings (reads .env)
│  ├─ api/
│  │  ├─ containers.py     # Container lifecycle routes
│  │  ├─ profiles.py       # Profile registry routes
│  │  └─ health.py         # Health check
│  ├─ lxd/
│  │  ├─ client.py         # pylxd client singleton
│  │  ├─ containers.py     # Launch, stop, delete, exec helpers
│  │  ├─ profiles.py       # Apply/remove LXD profile
│  │  └─ cloud_init.py     # Merge fragments → user-data YAML
│  ├─ profiles/
│  │  ├─ registry.py       # Load profile YAMLs from disk
│  │  └─ resolver.py       # Dependency resolution (topological sort)
│  ├─ store/
│  │  ├─ models.py         # Pydantic models for container metadata
│  │  └─ json_store.py     # Atomic JSON read/write helpers
│  └─ schemas.py           # Pydantic request/response models
├─ tests/
│  ├─ conftest.py
│  ├─ test_resolver.py     # Unit tests for dependency resolution
│  ├─ test_cloud_init.py   # Unit tests for cloud-init merge
│  └─ test_api.py          # Integration tests (mock pylxd)
├─ pyproject.toml
├─ .env.example
└─ README.md
```

### 4.3 Configuration (`.env.example`)

```dotenv
YETAOS_LXD_SOCKET=/var/snap/lxd/common/lxd/unix.socket
YETAOS_STORE_PATH=/srv/yetaos/db/containers.json
YETAOS_PROFILES_DIR=/path/to/repo/lxc/profiles
YETAOS_CLOUD_INIT_DIR=/path/to/repo/lxc/cloud-init
YETAOS_WORKSPACES_DIR=/srv/yetaos/workspaces
YETAOS_SECRETS_DIR=/srv/yetaos/secrets
YETAOS_MODELS_DIR=/srv/yetaos/models
YETAOS_API_KEY=change-me          # Bearer token; leave blank to disable auth
YETAOS_HOST=0.0.0.0
YETAOS_PORT=8000
YETAOS_LOG_LEVEL=info
```

### 4.4 REST API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check; returns `{"status":"ok","lxd":"ok"}` |
| `GET` | `/api/v1/profiles` | List all available profiles with metadata |
| `GET` | `/api/v1/profiles/resolve` | Resolve a profile string → ordered profile list |
| `GET` | `/api/v1/containers` | List all tracked containers with status |
| `POST` | `/api/v1/containers` | Create a new container (body: `CreateContainerRequest`) |
| `GET` | `/api/v1/containers/{name}` | Get container detail + live LXD status |
| `POST` | `/api/v1/containers/{name}/start` | Start a stopped container |
| `POST` | `/api/v1/containers/{name}/stop` | Stop a running container |
| `DELETE` | `/api/v1/containers/{name}` | Delete container (and workspace if ephemeral) |
| `GET` | `/api/v1/containers/{name}/logs` | SSE stream of container `cloud-init-output.log` |
| `POST` | `/api/v1/containers/{name}/export` | Tar `/workspace`, stream as `.tar.gz` |
| `PUT` | `/api/v1/containers/{name}/secrets` | Update per-container secrets (writes to host secrets dir) |
| `POST` | `/api/v1/containers/{name}/snapshot` | Create a named snapshot |
| `GET` | `/api/v1/containers/{name}/snapshots` | List snapshots |
| `POST` | `/api/v1/containers/{name}/snapshots/{snap}/restore` | Restore snapshot |

### 4.5 Request/response schemas (Pydantic)

```python
class CreateContainerRequest(BaseModel):
    name: str                          # LXC-valid name, max 63 chars
    profile_string: str                # e.g. "/dev/python:rocm/claude/rocm-gpu/"
    ephemeral: bool = False
    cpu_limit: int = 2
    memory_limit_gb: int = 4
    enable_gpu: bool = False
    secrets: dict[str, str] = {}       # injected at start, not stored in DB

class ContainerResponse(BaseModel):
    name: str
    profile_string: str
    resolved_profiles: list[str]
    ephemeral: bool
    status: str                        # "running" | "stopped" | "frozen" | "error"
    created_at: datetime
    last_used: datetime | None
    shell_url: str | None              # e.g. /containers/<name>/shell
    code_url: str | None               # e.g. /containers/<name>/code
```

### 4.6 LXD integration layer

`app/lxd/containers.py` wraps `pylxd`:

- `create_container(name, profiles, user_data, config)` — calls `client.containers.create()` then `container.start()`
- `stop_container(name, force=False)` — `container.stop(wait=True)`
- `delete_container(name)` — `container.delete()`
- `exec_command(name, cmd, env={})` — `container.execute(cmd, environment=env)`
- `pull_file(name, remote_path)` → `bytes` — `container.files.get(remote_path)`
- `get_status(name)` → `str` — `container.status` (`Running`, `Stopped`, etc.)
- `stream_log(name, log_path)` → `AsyncGenerator[str]` — polls log file via exec, yields lines

All blocking pylxd calls are wrapped with `loop.run_in_executor(None, ...)` to avoid blocking the FastAPI event loop.

### 4.7 Metadata store (JSON file)

**Why not SQLite?**  
At home-server scale (realistic max: tens to low-hundreds of containers), a relational database adds complexity with no practical benefit: SQLAlchemy introduces ~300 lines of boilerplate (ORM models, session factory, migrations), Alembic migration scripts must be written for every schema change, and the data is a simple flat collection with no joins or complex queries. A JSON file is human-readable, trivially backed up with `cp`, inspectable without any tooling, and fast at this scale.

**Implementation (`app/store/`)**

Pydantic model:

```python
class ContainerRecord(BaseModel):
    name: str
    profile_string: str
    resolved_profiles: list[str]
    ephemeral: bool
    gpu_enabled: bool
    created_at: datetime
    last_used: datetime | None = None
    status: str                      # "running" | "stopped" | "error"
    workspace_path: str | None = None
```

`containers.json` layout — a JSON object keyed by container name:

```json
{
  "myenv": {
    "name": "myenv",
    "profile_string": "/dev/python:rocm/claude/rocm-gpu/",
    "resolved_profiles": ["service/base", "service/rocm-gpu", "tool/python", "tool/python-rocm", "agent/claude"],
    "ephemeral": false,
    "gpu_enabled": true,
    "created_at": "2026-04-17T00:00:00Z",
    "last_used": null,
    "status": "stopped",
    "workspace_path": "/srv/yetaos/workspaces/myenv"
  }
}
```

`app/store/json_store.py` helpers:

```python
def load() -> dict[str, ContainerRecord]
def save(records: dict[str, ContainerRecord]) -> None   # atomic: write to .tmp then os.replace
def get(name: str) -> ContainerRecord | None
def upsert(record: ContainerRecord) -> None
def delete(name: str) -> None
```

Writes are atomic (`write to containers.json.tmp`, then `os.replace()`) to prevent corruption on crash.  
A `threading.Lock` guards all reads and writes; the backend runs with a single Uvicorn worker, so this is sufficient.  
If multi-worker deployments are ever needed, a `filelock`-based advisory lock can be added without changing the interface.

### 4.8 Artifact export

1. Execute `tar czf /tmp/yetaos-export.tar.gz -C /workspace .` inside the container via `exec_command`
2. Pull `/tmp/yetaos-export.tar.gz` via `pull_file`
3. Stream bytes to client as `StreamingResponse` with `Content-Disposition: attachment; filename=<name>-workspace.tar.gz`
4. Delete `/tmp/yetaos-export.tar.gz` from container after pull

### 4.9 Authentication

- All `/api/v1/*` routes require `Authorization: Bearer <YETAOS_API_KEY>` header when `YETAOS_API_KEY` is set
- Requests from `127.0.0.1` bypass auth when `YETAOS_API_KEY` is unset (local-only mode)
- Implemented as a FastAPI dependency `verify_api_key(request, settings)` — not middleware, so it can be opt-out per route if needed

### 4.10 Health check

`GET /health` returns:
```json
{
  "status": "ok",
  "lxd": "ok",        // "error: <msg>" if socket unreachable
  "db": "ok",         // "error: <msg>" if DB unreadable
  "version": "0.1.0"
}
```

Returns HTTP 200 always; callers inspect `lxd`/`db` fields.

### 4.11 Logging

- Structured JSON logs via Python's `logging` with `python-json-logger`
- Log level controlled by `YETAOS_LOG_LEVEL`
- Every API request logged with method, path, status code, duration
- Every LXD operation logged with container name, operation, duration

### 4.12 Error handling

- LXD errors mapped to HTTP status codes:
  - Container not found → 404
  - Container already exists → 409
  - LXD socket unreachable → 503
  - Invalid profile string → 422
- All unhandled exceptions caught by a FastAPI exception handler; logged and returned as `{"detail": "Internal error", "request_id": "..."}` (no stack traces to client)

---

## 5. Frontend Web UI

### 5.1 Technology decision
- **HTMX 2.x** + **Alpine.js 3.x** — no build step, served as static files from the backend
- **CSS**: Pico.css (minimal classless CSS framework) — single CDN link
- Templates rendered server-side by FastAPI's Jinja2 integration
- No separate frontend build pipeline; static assets served from `backend/app/static/`

### 5.2 Template layout

```
backend/app/
├─ templates/
│  ├─ base.html           # Layout: nav, flash messages
│  ├─ index.html          # Dashboard (container list)
│  ├─ create.html         # Create environment form
│  └─ container.html      # Container detail
└─ static/
   ├─ htmx.min.js
   └─ alpine.min.js
```

HTMX routes replace page fragments without full navigation:
- `hx-get="/fragments/containers"` to refresh container list
- `hx-post="/api/v1/containers"` to submit create form

### 5.3 Pages

**Dashboard (`/`)**
- Polled every 10 seconds via `hx-trigger="every 10s"` to refresh container status
- Container cards show: name, environment type, status badge, last-used time
- Action buttons: Start / Stop / Delete / Open Shell / Open VS Code / Export
- "New environment" button → navigates to create form

**Create environment (`/create`)**
- Profile-string builder:
  - Use-case dropdown (dev / model / genai)
  - Tool multi-select (populated from `GET /api/v1/profiles?category=tool`)
  - Agent multi-select (populated from `GET /api/v1/profiles?category=agent`)
  - Service multi-select (populated from `GET /api/v1/profiles?category=service`)
  - Resolved profile string shown live as user selects (computed client-side by Alpine.js)
- Container name field (validated: `[a-z0-9-]+`, max 63 chars)
- Ephemeral toggle
- CPU / memory sliders (within configurable limits)
- Secrets section: key-value pairs injected at container start (not persisted)
- Submit → `hx-post` → shows creation progress via SSE log stream

**Container detail (`/containers/{name}`)**
- Live status badge
- Log stream panel (SSE from `GET /api/v1/containers/{name}/logs`)
- "Open Shell" button → opens `/containers/{name}/shell` in new tab (proxied ttyd)
- "Open VS Code" button → opens `/containers/{name}/code` in new tab (proxied code-server)
- "Export workspace" button → triggers download via `GET /api/v1/containers/{name}/export`
- Snapshots section: list + create + restore
- Danger zone: Stop / Delete

### 5.4 Reverse proxy (Caddy)

`Caddyfile` committed to `deploy/Caddyfile`:

```caddy
dev-orchestrator.local {
    # TLS via ACME (or self-signed for .local)
    tls internal

    # Backend API + UI
    reverse_proxy /api/* localhost:8000
    reverse_proxy /health localhost:8000
    handle /* {
        reverse_proxy localhost:8000
    }

    # Per-container shell (ttyd on port 7681)
    @shell path_regexp /containers/([^/]+)/shell.*
    handle @shell {
        reverse_proxy {re.1}.lxd:7681
    }

    # Per-container VS Code Server (code-server on port 8080)
    @code path_regexp /containers/([^/]+)/code.*
    handle @code {
        reverse_proxy {re.1}.lxd:8080
    }
}
```

Notes:
- LXD containers are reachable by hostname `<name>.lxd` via `lxdbr0` DNS
- `tls internal` generates a self-signed cert; for LAN access, use a wildcard cert or mkcert

---

## 6. Container Lifecycle Logic

### 6.1 Create flow
1. Validate name (`[a-z][a-z0-9-]*`, max 63 chars, unique in DB)
2. Parse and resolve profile string → ordered profile list
3. Build merged cloud-init `user-data` YAML from fragments
4. Compute LXD config: merge all `lxd.config` keys from resolved profiles; last write wins
5. Compute LXD devices: merge all `lxd.devices` dicts
6. Write workspace dir: `mkdir -p /srv/yetaos/workspaces/<name>`
7. Write secrets file: `/srv/yetaos/secrets/<name>.env` (if secrets provided)
8. Call `pylxd` to create and start the container with the merged config and user-data
9. Write container record to DB (`status = "starting"`)
10. Return `ContainerResponse`; client polls `/api/v1/containers/{name}` for status

### 6.2 Start flow
1. Look up container in DB; verify it exists in LXD
2. Inject secrets (write to `/run/secrets/` via exec)
3. Call `container.start(wait=True)`
4. Update `last_used` in DB

### 6.3 Stop flow
1. Call `container.stop(wait=True)`
2. If `ephemeral=True`: delete container from LXD, remove workspace dir, remove from DB
3. If `ephemeral=False`: update status in DB to `"stopped"`

### 6.4 Delete flow
1. Stop container if running
2. Call `container.delete()`
3. Remove workspace dir: `rm -rf /srv/yetaos/workspaces/<name>`
4. Remove secrets file: `rm -f /srv/yetaos/secrets/<name>.env`
5. Remove from DB

### 6.5 Snapshot flow
- `POST /api/v1/containers/{name}/snapshots` body `{"snapshot_name": "snap0"}`
- Calls `container.snapshots.create("snap0", stateful=False)`
- Stateful snapshots not supported initially (require CRIU)

### 6.6 Idle shutdown (alpha feature)
- Background task runs every 5 minutes
- For each running, non-ephemeral container: query CPU stats via LXD API
- If CPU < 1% for 30 consecutive minutes: call stop flow
- Idle timeout configurable per container (default: disabled)

---

## 7. Testing Strategy

### 7.1 Unit tests (`backend/tests/`)
- `test_resolver.py` — dependency resolution on mock profile trees; cycle detection
- `test_cloud_init.py` — merge of fragments; deduplication; correct ordering
- `test_store.py` — JSON store helpers: upsert, delete, atomic write, concurrent access

### 7.2 Integration tests
- Mock `pylxd` using `unittest.mock` — no real LXD required in CI
- `test_api.py` — all REST endpoints via `TestClient`; covers 200/422/404/409 cases

### 7.3 End-to-end tests (manual, pre-alpha gate)
- Provision a real Ubuntu 24.04 VM with LXD
- Run `scripts/host-setup.sh`
- Start the backend
- Create one container per environment type
- Verify cloud-init completes; verify toolchain works inside container
- Results documented in `docs/e2e-test-results.md`

### 7.4 CI (GitHub Actions)
- Workflow: `.github/workflows/ci.yml`
- Steps: `pip install`, `pytest`, `ruff check`, `mypy`
- Runs on every push and PR
- No LXD in CI (all LXD calls mocked)

---

## 8. Deployment

### 8.1 Installation script (`scripts/install.sh`)
Idempotent script that:
1. Creates `yetaos` system user
2. Creates all host directories
3. Copies `.env.example` to `/etc/yetaos/.env` (skips if already present)
4. Installs Python 3.11 and `uv`
5. Creates virtualenv at `/opt/yetaos/venv`, installs backend dependencies
6. Installs systemd service file
7. Installs Caddy
8. Copies `Caddyfile` to `/etc/caddy/Caddyfile`
9. Enables and starts `yetaos-backend.service` and `caddy.service`

### 8.2 Systemd service (`deploy/yetaos-backend.service`)

```ini
[Unit]
Description=YETAOS Dev Orchestrator Backend
After=network.target lxd.service

[Service]
User=yetaos
Group=yetaos
WorkingDirectory=/opt/yetaos
EnvironmentFile=/etc/yetaos/.env
ExecStart=/opt/yetaos/venv/bin/uvicorn app.main:app \
    --host ${YETAOS_HOST} --port ${YETAOS_PORT} \
    --workers 1 --log-level ${YETAOS_LOG_LEVEL}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 8.3 LXD preseed (`scripts/lxd-init-preseed.yaml`)
Committed to repo; applied via `lxd init --preseed < scripts/lxd-init-preseed.yaml`

---

## 9. Repository Structure

```
.
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ lxd/
│  │  ├─ profiles/
│  │  ├─ store/
│  │  ├─ templates/
│  │  ├─ static/
│  │  ├─ main.py
│  │  ├─ config.py
│  │  └─ schemas.py
│  ├─ tests/
│  ├─ pyproject.toml
│  ├─ .env.example
│  └─ README.md
├─ lxc/
│  ├─ profiles/
│  │  ├─ service/
│  │  │  ├─ base.yaml
│  │  │  ├─ rocm-gpu.yaml
│  │  │  ├─ nvidia-gpu.yaml
│  │  │  ├─ vllm.yaml
│  │  │  ├─ vscode-server.yaml
│  │  │  └─ ttyd.yaml
│  │  ├─ agent/
│  │  │  ├─ claude.yaml
│  │  │  ├─ copilot.yaml
│  │  │  ├─ opencode.yaml
│  │  │  └─ openclaw.yaml
│  │  ├─ tool/
│  │  │  ├─ python.yaml
│  │  │  ├─ python-rocm.yaml
│  │  │  ├─ clang.yaml
│  │  │  ├─ clang-riscv.yaml
│  │  │  ├─ node.yaml
│  │  │  ├─ electron.yaml
│  │  │  ├─ blender.yaml
│  │  │  └─ comfyui.yaml
│  │  └─ use-case/
│  │     ├─ dev.yaml
│  │     ├─ model.yaml
│  │     └─ genai.yaml
│  └─ cloud-init/
│     ├─ service/
│     ├─ tool/
│     └─ agent/
├─ scripts/
│  ├─ host-setup.sh
│  ├─ install.sh
│  └─ lxd-init-preseed.yaml
├─ deploy/
│  ├─ yetaos-backend.service
│  └─ Caddyfile
├─ docs/
│  ├─ plan.md             (this file)
│  ├─ architecture.md
│  ├─ profiles.md
│  ├─ user-guide.md
│  ├─ versions.md         (pinned dependency versions)
│  └─ e2e-test-results.md
├─ .github/
│  └─ workflows/
│     └─ ci.yml
├─ AGENTS.md
└─ README.md
```

---

## 10. Milestones

### Milestone 1 — Host scaffolding and LXC profiles
- [ ] `scripts/lxd-init-preseed.yaml` — LXD initialization preseed
- [ ] `scripts/host-setup.sh` — idempotent host directory and user setup
- [ ] `lxc/profiles/service/base.yaml` and `lxc/cloud-init/service/base.sh`
- [ ] `lxc/profiles/service/rocm-gpu.yaml` (AMD GPU passthrough)
- [ ] `lxc/profiles/use-case/dev.yaml` + `tool/python.yaml` + `tool/python-rocm.yaml`
- [ ] Manual E2E: launch a Python+ROCm container and run `rocminfo` inside it

### Milestone 2 — Backend MVP
- [ ] `backend/pyproject.toml` with all dependencies pinned
- [ ] `app/config.py` — Pydantic Settings from `.env`
- [ ] `app/store/` — Pydantic `ContainerRecord` model + atomic JSON store helpers
- [ ] `app/lxd/client.py` — pylxd singleton
- [ ] `app/lxd/containers.py` — create/start/stop/delete/exec/pull
- [ ] `app/profiles/registry.py` — load profiles from disk
- [ ] `app/profiles/resolver.py` — topological sort with cycle detection
- [ ] `app/lxd/cloud_init.py` — merge fragments → user-data YAML
- [ ] `app/api/containers.py` — CRUD + start/stop/delete endpoints
- [ ] `app/api/health.py` — health check
- [ ] Unit tests: resolver, cloud-init merge, JSON store
- [ ] Integration tests: all container CRUD API routes (mocked pylxd)

### Milestone 3 — Frontend MVP
- [ ] `app/templates/base.html`, `index.html` — dashboard with container list
- [ ] `app/templates/create.html` — create form with live profile-string preview
- [ ] HTMX polling for container status refresh
- [ ] SSE log stream endpoint + frontend log panel
- [ ] `app/api/profiles.py` — profiles list endpoint (populates create form dropdowns)

### Milestone 4 — Container detail + shell + VS Code
- [ ] `app/templates/container.html` — full detail page
- [ ] `lxc/profiles/service/ttyd.yaml` + cloud-init fragment
- [ ] `lxc/profiles/service/vscode-server.yaml` + cloud-init fragment
- [ ] Caddy config for shell and code-server proxying
- [ ] Export endpoint + frontend download button
- [ ] Snapshot create/list/restore API + frontend UI

### Milestone 5 — All environment templates + secrets
- [ ] All remaining profiles and cloud-init fragments (clang:riscv, node, electron, blender, comfyui)
- [ ] Agent profiles: claude, copilot, opencode, openclaw
- [ ] vLLM service profile
- [ ] Per-container secret injection at start
- [ ] `PUT /api/v1/containers/{name}/secrets` endpoint + UI

### Milestone 6 — Deployment + ops
- [ ] `scripts/install.sh`
- [ ] `deploy/yetaos-backend.service`
- [ ] `deploy/Caddyfile`
- [ ] Structured JSON logging
- [ ] Idle shutdown background task
- [ ] `docs/versions.md` — all pinned dependency versions
- [ ] `docs/user-guide.md` — installation and usage instructions
- [ ] CI workflow: lint (ruff), type-check (mypy), unit + integration tests

### Milestone 7 — Alpha release gate
- [ ] All Milestone 1–6 items complete
- [ ] E2E tests documented in `docs/e2e-test-results.md` for all 5 environment types
- [ ] README updated with working quick-start instructions
- [ ] No known P0/P1 bugs
- [ ] API versioned at `v1`; marked stable in docs

---

## 11. Security considerations

- LXD Unix socket accessible only by `yetaos` user (group `lxd`); backend runs as `yetaos`
- API key required for all mutating endpoints; stored in `/etc/yetaos/.env` (mode 0600)
- Secrets never written to container image, cloud-init, DB, or logs; written to tmpfs at container start
- Container AppArmor profiles enforced (LXD default); GPU profiles add minimal allow rules only
- Caddy TLS for all external traffic; `tls internal` for `.local` dev setups
- No container gets `security.privileged = true` unless explicitly documented and justified
- Profile YAML files are read-only at runtime; no user-supplied profile YAML accepted via API

---

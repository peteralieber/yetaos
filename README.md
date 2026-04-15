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
  - Linux (Ubuntu recommended)
  - LXC/LXD
  - ROCm and/or NVIDIA GPU drivers
  - Reverse proxy (nginx or Caddy)

- **Backend**
  - FastAPI (Python) or Go HTTP service
  - Talks to LXD via Unix socket or `pylxd`
  - Exposes REST API for container lifecycle and artifact export
  - Stores container metadata in SQLite or a small JSON/YAML file

- **Frontend**
  - Minimal web UI (React/Svelte/Vue or HTMX)
  - Environment creation form
  - Container list and actions
  - Links to web shell / VS Code Server

- **LXC**
  - Profiles for each environment type
  - Cloud-init scripts for deterministic provisioning
  - Optional GPU passthrough and shared model mounts

---

## Getting started

### Prerequisites

- Ubuntu Server 22.04 or 24.04
- LXD installed and initialized (`lxd init`)
- GPU drivers installed and working (ROCm and/or NVIDIA)
- Python 3.11+ (if using FastAPI backend) or Go (if using Go backend)
- Node.js (if building a JS frontend)

### Quick setup (high-level)

1. **Clone the repo**

   ```bash
   git clone https://github.com/<your-username>/dev-env-orchestrator.git
   cd dev-env-orchestrator

2. **Configure LXC profiles**
   - Create base profiles and environment-specific profiles under lxc/profiles/.
   - Apply cloud-init user-data from lxc/cloud-init/.
5. **Run the backend**
   - Configure environment variables (LXD socket path, DB path, etc.).
   - Start the FastAPI/Go backend (see backend/README.md for details).
6. **Run the frontend**
   - Build and serve the web UI (see frontend/README.md).
   - Optionally place it behind nginx/Caddy with TLS.
7. **Open the launchpad**
   - Visit the configured URL (e.g., https://dev-orchestrator.local).
   - Create your first environment and start hacking.

## Repository layout (proposed)

```
├─ backend/
│  ├─ app/               # FastAPI/Go source
│  ├─ tests/
│  └─ README.md
├─ frontend/
│  ├─ src/
│  ├─ public/
│  └─ README.md
├─ lxc/
│  ├─ profiles/          # LXC profile YAMLs
│  └─ cloud-init/        # Cloud-init scripts per environment
├─ docs/
│  ├─ architecture.md
│  ├─ user-guide.md
│  └─ environments.md
├─ .github/
│  └─ copilot-instructions.md
└─ README.md
```

## Roadmap

[ ] Implement core container lifecycle API
[ ] Add environment registry and versioning
[ ] Build minimal web UI
[ ] Add GPU-aware profiles for ROCm and NVIDIA
[ ] Integrate web shell and VS Code Server
[ ] Add metrics and basic observability
[ ] Publish example environment definitions

## Contributing

Issues and PRs are welcome. The guiding principles are:

* Deterministic, reproducible behavior
* Explicit configuration
* Minimal, understandable abstractions

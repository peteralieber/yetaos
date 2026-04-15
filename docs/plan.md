# Implementation Plan

This document outlines the complete, end‑to‑end implementation plan for the Dev Environment Orchestrator using LXC/LXD, FastAPI/Go backend, and a lightweight web UI.

---

## 1. Host System Setup

### 1.1 Install and initialize LXD
- Install LXD via snap or apt.
- Run `lxd init` with:
  - `lxdbr0` bridge
  - ZFS or BTRFS storage pool
  - IPv4 NAT enabled
  - IPv6 optional
- Verify with:
  \`\`\`
  lxc list
  \`\`\`

### 1.2 Install GPU drivers
- **ROCm** for AMD GPUs:
  - Install ROCm packages
  - Add user to `video` and `render` groups
  - Validate with `rocminfo` and `clinfo`
- **NVIDIA** (optional):
  - Install NVIDIA drivers
  - Enable `nvidia-container-runtime` style passthrough

### 1.3 Create shared host directories
- `/srv/dev-orchestrator/models` (read‑only model cache)
- `/srv/dev-orchestrator/data` (optional shared data)
- `/srv/dev-orchestrator/containers` (persistent workspaces)

---

## 2. LXC Profiles (Environment Templates)

Profiles declaratively describe the use-case, environment, tools, AI agents, and basic container configuration. The profile details are stored in the yaml file.  There is a short-hand syntax for a CLI interface to YETOS:

`/_{use-case}_/_{tools}_/_{agents}_/_{services}_/`

where each tool, agent, and service is of the form `{profile}[:{subprofile}]` and more than one can be present, contatinated with `+`.

Each use-case has a base profile to start, built on top of the "baseline" profile below. Each tool, agent, and service has its own yaml profile describing what it adds. They also can have dependencies on other tools, agents, or services. Each profile can have subprofiles that further describe what is to be included.

For example, a dev environment with clang setup for producing RISCV binaries and a qemu riscv simulator with claude enabled and a local llm (gemma4) served with vllm would yield a profile string of:

`/dev/clang:riscv+qemu:riscv/claude/vllm:gemma4/`

### 2.1 Baseline profile
Create `profiles/base.yaml`:
- Ubuntu 22.04 or 24.04
- Networking via `lxdbr0`
- CPU/RAM limits
- Cloud-init support

### 2.2 Services Profiles
- `service/rocm-gpu.yaml`
  - Map `/dev/kfd`, `/dev/dri/*`
  - Add required AppArmor allowances
- `service/nvidia-gpu.yaml`
  - Map `/dev/nvidia*`
- `service/vllm.yaml`
  - Map `/dev/models`
  - Add required dependencies
- `services/vscode-server.yaml`
  - Map `/dev/workspace`
 
### 2.3 Agent Profiles

- `agent/claude`
- `agent/copilot`
- `agent/opencode`
- `agent/openclaw`

### 2.3 Tool Profiles

- `dev/python`
- `dev/clang:riscv`
- `dev/node`
- `dev/electron` ➡️ depends on `dev/node`
- `genai/comfyui`
- `model/blender`

Each profile includes:
- Required Base profile
- Cloud-init user-data file
- Storage mounts:
  - `/workspace`
  - `/models` (read-only)
  - `/data` (optional)

Constructing a profile string triggers dependency analysis and any ordering needed (initialization is done from right to left (services->agents->tools). This leaves the cloud initialization script on responsible for calling the scripts in order.
---

## 3. Cloud-Init Scripts

### 3.1 Structure
Each profile gets a script under `lxc/cloud-init/<profile-path>.yaml`:
- Update system packages
- Install required toolchains
- Install AI CLIs:
  - Claude CLI
  - Copilot CLI
- Install VS Code Server (optional)
- Create `/workspace`
- Write metadata to `/etc/dev-orchestrator/metadata.json`
- Etc
The main cloud init script merges all profiles in the profile string, eliminates duplicates, and runs from right to left (services->agents->tools).

### 3.2 Example tasks
- Python env:
  - Install Python 3.11, uv, venv
  - Install PyTorch ROCm wheels
- RISC-V env:
  - Install Clang 18
  - Install RISC-V GNU toolchain
  - Install vLLM
- Node env:
  - Install Node LTS + pnpm
  - Install Electron builder
- Blender env:
  - Install Blender CLI
- ComfyUI env:
  - Clone ComfyUI repo
  - Install dependencies

---

## 4. Backend Service (FastAPI or Go)

### 4.1 API Endpoints
- `POST /containers/create`
- `POST /containers/start`
- `POST /containers/stop`
- `POST /containers/delete`
- `GET /containers/list`
- `GET /containers/<name>/logs`
- `POST /containers/<name>/export`

### 4.2 LXD Integration Layer
- Use Unix socket `/var/snap/lxd/common/lxd/unix.socket`
- Implement:
  - Launch container with profiles
  - Attach cloud-init user-data
  - Query container state
  - Execute commands inside container
  - Pull files from container

### 4.3 Metadata Store
- SQLite or YAML/JSON file:
  - container name
  - environment type
  - ephemeral flag
  - GPU flag
  - created_at
  - last_used
  - status

### 4.4 Artifact Export
- Tar `/workspace` inside container:
  \`\`\`
  tar czf /tmp/export.tar.gz /workspace
  \`\`\`
- Stream file to client

### 4.5 Authentication (optional)
- Local-only mode
- Or simple user accounts with JWT

---

## 5. Frontend Web UI

### 5.1 Pages
- **Dashboard**
  - List containers
  - Status indicators
  - Action buttons
- **Create Environment**
  - Environment type dropdown
  - Container name field
  - Ephemeral toggle
  - GPU toggle
- **Container Detail**
  - Logs
  - Open Shell (ttyd/wetty)
  - Open VS Code Server
  - Export artifacts

### 5.2 Tech Options
- React, Svelte, Vue, or HTMX
- Minimal state management
- REST API calls to backend

### 5.3 Reverse Proxy
- nginx or Caddy
- TLS termination
- Routes:
  - `/api/*` → backend
  - `/containers/<name>/code` → VS Code Server
  - `/containers/<name>/shell` → ttyd

---

## 6. Container Lifecycle Logic

### 6.1 Create
- Validate name
- Select profiles
- Inject cloud-init
- Launch container
- Track metadata

### 6.2 Ephemeral behavior
- Use `--ephemeral` flag
- Auto-delete on stop

### 6.3 Persistent behavior
- Create named volume for `/workspace`
- Allow snapshots

### 6.4 Stop/Delete
- Stop container via LXD
- If ephemeral → auto-delete
- If persistent → delete only on user request

---

## 7. Optional Enhancements

### 7.1 Template versioning
- `profiles/dev-python-rocm/v1`
- `profiles/dev-python-rocm/v2`

### 7.2 Idle shutdown
- Monitor CPU/network usage
- Auto-stop after N minutes idle

### 7.3 Per-container secrets
- Inject Claude/Copilot tokens via:
  - LXC config keys
  - Secret store

### 7.4 Metrics
- Container CPU/RAM usage
- GPU utilization
- Export Prometheus metrics

---

## 8. Repository Structure

\`\`\`
.
├─ backend/
│  ├─ app/
│  ├─ tests/
│  └─ README.md
├─ frontend/
│  ├─ src/
│  ├─ public/
│  └─ README.md
├─ lxc/
│  ├─ profiles/
│  └─ cloud-init/
├─ docs/
│  ├─ architecture.md
│  ├─ user-guide.md
│  └─ profiles.md
|  └─ plan.md
├─ AGENTS.md
└─ README.md
\`\`\`

---

## 9. Milestones

### Milestone 1 — Core LXC setup
- Base profiles
- GPU profiles
- One environment template working

### Milestone 2 — Backend MVP
- Create/list/start/stop/delete
- Metadata store

### Milestone 3 — Frontend MVP
- Dashboard
- Create environment form

### Milestone 4 — Artifact export + VS Code Server

### Milestone 5 — Additional environments + polish

---

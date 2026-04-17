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

**DECISION: Use FastAPI (Python)** for alpha release
- Faster development cycle
- Better LXD Python library support (`pylxd`)
- Easier cloud-init YAML manipulation
- Go can be considered for v2 if performance is an issue

### 4.1 API Endpoints
- `POST /api/v1/containers/create`
  - Body: `{ "name": str, "profile_string": str, "ephemeral": bool, "gpu": bool, "secrets": dict }`
  - Returns: `{ "id": str, "name": str, "status": str }`
- `POST /api/v1/containers/{name}/start`
- `POST /api/v1/containers/{name}/stop`
- `DELETE /api/v1/containers/{name}`
- `GET /api/v1/containers`
  - Query params: `?status=running|stopped&type=ephemeral|persistent`
- `GET /api/v1/containers/{name}`
  - Returns full container details, status, metadata
- `GET /api/v1/containers/{name}/logs`
  - Query params: `?lines=100&follow=true`
- `POST /api/v1/containers/{name}/export`
  - Returns streaming tar.gz
- `GET /api/v1/containers/{name}/exec`
  - WebSocket endpoint for shell access
- `GET /api/v1/profiles`
  - List available profile strings and their descriptions
- `POST /api/v1/containers/{name}/snapshot`
  - Create snapshot for persistent containers
- `GET /api/v1/containers/{name}/snapshots`
  - List snapshots
- `POST /api/v1/containers/{name}/restore/{snapshot}`
  - Restore from snapshot

### 4.2 LXD Integration Layer
- Use `pylxd` library
- Connect to Unix socket `/var/snap/lxd/common/lxd/unix.socket`
- Implement wrapper class `LXDManager`:
  - `create_container(name, profiles, config, devices, ephemeral)`
  - `start_container(name)`
  - `stop_container(name)`
  - `delete_container(name)`
  - `get_container_state(name)`
  - `exec_command(name, command, environment)`
  - `get_file(name, path)` → pull file from container
  - `put_file(name, path, content)` → push file to container
  - `attach_cloudinit(name, user_data, meta_data)`
  - `create_snapshot(name, snapshot_name)`
  - `restore_snapshot(name, snapshot_name)`

### 4.3 Profile Processing Engine
- `ProfileParser` class:
  - Parse profile string (e.g., `/dev/python+rocm/claude+copilot/vllm/`)
  - Load profile YAML files from `lxc/profiles/`
  - Resolve dependencies recursively
  - Detect circular dependencies
  - Order profiles: services → agents → tools → use-case
- `CloudInitMerger` class:
  - Load cloud-init YAML for each profile
  - Merge package lists (deduplicate)
  - Merge runcmd lists (preserve order, right to left)
  - Merge write_files sections
  - Generate final cloud-init user-data

### 4.4 Metadata Store
**DECISION: Use JSON file-based storage** for simplicity and transparency

Rationale:
- Home server use case: typically <50 containers, not thousands
- JSON is human-readable, easy to debug and backup
- No database setup/migration complexity
- Can grep/edit files directly if needed
- Atomic writes prevent corruption
- Performance is more than adequate for this scale (<1ms reads at 100 containers)
- If scale becomes an issue (>1000 containers), migrate to SQLite later

File structure:
```
/var/lib/dev-orchestrator/
├── containers.json        # Main container registry
├── secrets.json          # Encrypted secrets (separate file for security)
└── backups/              # Automatic backups on changes
    ├── containers.json.backup-20260417-120000
    └── secrets.json.backup-20260417-120000
```

**containers.json** format:
```json
{
  "containers": {
    "pytorch-lab-1": {
      "id": "c9f3a8b2-...",
      "name": "pytorch-lab-1",
      "profile_string": "/dev/python+rocm/claude/",
      "ephemeral": false,
      "gpu_enabled": true,
      "status": "running",
      "created_at": "2026-04-15T10:30:00Z",
      "last_used": "2026-04-17T08:15:00Z",
      "metadata": {
        "environment_type": "dev",
        "tools": ["python", "rocm"],
        "agents": ["claude"],
        "services": []
      },
      "snapshots": [
        {
          "id": "snap-1",
          "name": "before-upgrade",
          "created_at": "2026-04-16T14:20:00Z"
        }
      ]
    }
  }
}
```

**secrets.json** format (Fernet-encrypted values):
```json
{
  "secrets": {
    "pytorch-lab-1": {
      "CLAUDE_API_KEY": "gAAAAABh...",  // encrypted
      "GITHUB_TOKEN": "gAAAAABh..."     // encrypted
    }
  }
}
```

Implementation:
- Use Python's `json` module with atomic writes (write to temp, then rename)
- Lock file during writes to prevent concurrent modification
- Auto-backup before every write
- Keep last 10 backups, rotate older ones
- Validate JSON schema on load

Migration path if needed:
- At >500 containers or if query performance degrades, switch to SQLite
- Provide migration script: `python -m app.db.migrate_from_json`

### 4.5 Artifact Export
- Execute inside container:
  ```bash
  tar czf /tmp/workspace-export.tar.gz -C / workspace
  ```
- Use LXD `get_file` API to stream tar.gz
- Set appropriate HTTP headers:
  - `Content-Type: application/gzip`
  - `Content-Disposition: attachment; filename="{container_name}-workspace.tar.gz"`

### 4.6 Secret Management
- Store encrypted secrets in SQLite
- Use `cryptography.fernet` for encryption
- Master key stored in environment variable `ORCHESTRATOR_SECRET_KEY`
- Inject secrets into containers via:
  - LXC config keys: `lxc config set <container> environment.CLAUDE_API_KEY <value>`
  - Or write to files during creation: `/home/ubuntu/.config/claude/config.json`

### 4.7 Authentication & Authorization
**DECISION for Alpha: Local-only mode**
- No authentication required
- Bind to `127.0.0.1` or LAN IP only
- Add warning if exposed publicly
- Document: Use reverse proxy (nginx/Caddy) with basic auth if needed
- **Post-alpha**: Add JWT-based user accounts

### 4.8 Error Handling
- Centralized error handler middleware
- Return consistent error format:
  ```json
  {
    "error": "error_code",
    "message": "Human readable message",
    "details": {}
  }
  ```
- Log all errors with context (container name, operation, timestamp)
- Graceful degradation: if LXD unavailable, return 503

### 4.9 Logging & Monitoring
- Use Python `logging` module
- Log levels: DEBUG, INFO, WARNING, ERROR
- Log format: `timestamp | level | module | message | context`
- Log to:
  - stdout (for systemd journal)
  - `/var/log/dev-orchestrator/backend.log` (rotating)
- Track metrics:
  - Container creation time
  - Container count by status
  - API request latency
  - LXD operation success/failure rates

---

## 5. Frontend Web UI

**DECISION: Use HTMX + Alpine.js** for alpha release
- Minimal JavaScript bundle
- Server-side rendering where possible
- Progressive enhancement
- Fast development
- Can migrate to React/Svelte later if needed

### 5.1 Pages & Components

#### 5.1.1 Dashboard (`/`)
- **Container List Table**
  - Columns: Name, Profile, Status, Uptime, Actions
  - Filter by: Status (all/running/stopped), Type (all/ephemeral/persistent)
  - Sort by: Name, Created date, Last used
  - Refresh button (auto-refresh every 5s optional)
- **Actions per container**:
  - Start (if stopped)
  - Stop (if running)
  - Delete (with confirmation modal)
  - View Details
  - Export Workspace
  - Open Shell
  - Open VS Code (if available)
- **Summary Stats** (top of page):
  - Total containers
  - Running containers
  - GPU-enabled containers
  - Disk usage

#### 5.1.2 Create Environment Page (`/create`)
- **Profile Selection**
  - Dropdown or radio buttons grouped by category:
    - Development: `/dev/python+rocm`, `/dev/clang:riscv`, `/dev/node+electron`
    - Gen AI: `/genai/comfyui`
    - Modeling: `/model/blender`
  - Display description and installed tools for selected profile
  - Advanced: Custom profile string input
- **Configuration**
  - Container name (validation: lowercase, alphanumeric, dashes)
  - Ephemeral vs Persistent toggle
  - GPU enable/disable toggle
  - Resource limits (optional): CPU cores, RAM GB
- **Secrets (optional)**
  - Claude API Key
  - GitHub Token for Copilot
  - Other custom secrets
- **Create Button**
  - Shows progress indicator
  - Redirects to container detail page on success

#### 5.1.3 Container Detail Page (`/containers/{name}`)
- **Status Section**
  - Status badge (running/stopped/creating/error)
  - Uptime
  - Resource usage (CPU%, RAM%, GPU% if available)
  - IP address
- **Info Section**
  - Profile string
  - Created date
  - Last accessed
  - Ephemeral/Persistent flag
- **Actions**
  - Start/Stop/Delete buttons
  - Export workspace (downloads tar.gz)
  - Create snapshot (if persistent)
  - Restore from snapshot (if snapshots exist)
- **Terminal Section**
  - Embedded terminal (ttyd iframe or xterm.js + WebSocket)
  - Full-screen toggle
- **Logs Section**
  - Real-time container logs
  - Filter by log level
  - Download logs

#### 5.1.4 Snapshots Page (`/containers/{name}/snapshots`)
- List snapshots with creation date
- Restore button (with confirmation)
- Delete snapshot button

### 5.2 Tech Stack Details
- **Framework**: HTMX + Alpine.js + TailwindCSS
- **Icons**: Heroicons or Lucide
- **Terminal**: xterm.js + WebSocket to backend exec endpoint
- **Notifications**: Alpine.js toast notifications
- **State management**: Minimal, use Alpine.js stores for global state
- **Build**: Vite for dev server, bundling TailwindCSS

### 5.3 Reverse Proxy
**DECISION: Use Caddy** for simplicity and automatic HTTPS
- Caddyfile configuration:
  ```
  dev-orchestrator.local {
    reverse_proxy /api/* localhost:8000
    reverse_proxy /ws/* localhost:8000
    reverse_proxy /* localhost:5173  # frontend dev server or build

    # Optional: basic auth for alpha
    basicauth /api/* {
      admin $2a$14$...  # bcrypt hash
    }
  }
  ```
- TLS: Automatic via Let's Encrypt or self-signed for local
- Routes:
  - `/api/*` → FastAPI backend
  - `/ws/*` → WebSocket endpoints (shell, logs)
  - `/*` → Frontend static files
- Alternative nginx config provided in docs for users who prefer it

### 5.4 Responsive Design
- Mobile-friendly (stack layout on small screens)
- Desktop-optimized table view
- Touch-friendly buttons and toggles

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

## 8. Testing Strategy

### 8.1 Backend Testing
- **Unit Tests** (pytest)
  - Profile parser logic
  - Cloud-init merger
  - Secret encryption/decryption
  - Database operations
  - Coverage target: >80%
- **Integration Tests**
  - LXD API interactions (mock LXD or test instance)
  - Full container lifecycle (create → start → stop → delete)
  - Profile dependency resolution
  - Cloud-init generation
- **API Tests**
  - FastAPI TestClient for all endpoints
  - Auth/authz tests (if implemented)
  - Error handling tests
  - WebSocket connection tests

### 8.2 Frontend Testing
- **Component Tests** (not critical for alpha)
  - HTMX interactions
  - Form validation
- **E2E Tests** (Playwright or Cypress)
  - Create container flow
  - Start/stop/delete flow
  - Export artifact flow
  - Terminal interaction

### 8.3 Manual Testing Checklist
- [ ] Create ephemeral container → verify auto-delete on stop
- [ ] Create persistent container → stop → start → verify state preserved
- [ ] GPU passthrough works (ROCm and NVIDIA)
- [ ] Export workspace creates valid tar.gz
- [ ] Snapshot creation and restoration
- [ ] Profile dependency resolution (complex profile string)
- [ ] Secret injection into container
- [ ] Terminal session works in browser
- [ ] Multiple concurrent containers
- [ ] Resource limits enforced

---

## 9. Configuration Management

### 9.1 Backend Configuration
File: `backend/config.yaml`
```yaml
server:
  host: 127.0.0.1
  port: 8000
  debug: false

lxd:
  socket: /var/snap/lxd/common/lxd/unix.socket
  default_image: ubuntu:22.04
  default_profile: baseline

metadata:
  containers_file: /var/lib/dev-orchestrator/containers.json
  secrets_file: /var/lib/dev-orchestrator/secrets.json
  backup_dir: /var/lib/dev-orchestrator/backups
  max_backups: 10

profiles:
  path: ../lxc/profiles
  cloudinit_path: ../lxc/cloud-init

storage:
  workspace_base: /srv/dev-orchestrator/containers
  models_path: /srv/dev-orchestrator/models
  data_path: /srv/dev-orchestrator/data

security:
  secret_key_env: ORCHESTRATOR_SECRET_KEY
  allow_public_access: false

logging:
  level: INFO
  file: /var/log/dev-orchestrator/backend.log
  max_bytes: 10485760  # 10 MB
  backup_count: 5
```

### 9.2 Environment Variables
- `ORCHESTRATOR_SECRET_KEY`: Master key for secret encryption (required)
- `ORCHESTRATOR_CONFIG`: Path to config.yaml (optional, default: `./config.yaml`)
- `LXD_SOCKET`: Override LXD socket path (optional)
- `LOG_LEVEL`: Override log level (optional)

### 9.3 Profile YAML Format
Example: `lxc/profiles/base/baseline.yaml`
```yaml
metadata:
  name: baseline
  description: "Base Ubuntu 22.04 profile"
  category: base
  version: 1.0

dependencies: []

lxc_profile:
  config:
    limits.cpu: "4"
    limits.memory: "8GB"
  devices:
    eth0:
      name: eth0
      nictype: bridged
      parent: lxdbr0
      type: nic
    root:
      path: /
      pool: default
      type: disk

cloudinit_file: base/baseline.yaml
```

Example with dependencies: `lxc/profiles/dev/python.yaml`
```yaml
metadata:
  name: python
  description: "Python development environment"
  category: dev
  version: 1.0
  tags: [python, development]

dependencies:
  - base/baseline

lxc_profile:
  config:
    limits.cpu: "8"
    limits.memory: "16GB"

cloudinit_file: dev/python.yaml
```

### 9.4 Cloud-Init YAML Format
Example: `lxc/cloud-init/dev/python.yaml`
```yaml
#cloud-config
package_update: true
packages:
  - python3.11
  - python3-pip
  - python3-venv
  - build-essential
  - git
  - curl

runcmd:
  - curl -LsSf https://astral.sh/uv/install.sh | sh
  - mkdir -p /workspace
  - chown ubuntu:ubuntu /workspace
  - echo "export PATH=\"$HOME/.cargo/bin:$PATH\"" >> /home/ubuntu/.bashrc

write_files:
  - path: /etc/dev-orchestrator/metadata.json
    content: |
      {
        "environment": "python",
        "version": "1.0"
      }
```

---

## 10. Deployment & Installation

### 10.1 Host Prerequisites
- Ubuntu Server 22.04 or 24.04
- Minimum 16GB RAM, 100GB storage
- LXD installed: `sudo snap install lxd`
- LXD initialized: `sudo lxd init` (use defaults or ZFS storage)
- GPU drivers installed (if using GPU):
  - ROCm: Follow AMD installation guide
  - NVIDIA: Install drivers + nvidia-container-toolkit
- Caddy or nginx installed

### 10.2 Install Script
Provide `install.sh`:
```bash
#!/bin/bash
set -e

# Create directories
sudo mkdir -p /srv/dev-orchestrator/{models,data,containers}
sudo mkdir -p /var/lib/dev-orchestrator/backups
sudo mkdir -p /var/log/dev-orchestrator

# Install backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create systemd service
sudo cp systemd/dev-orchestrator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dev-orchestrator

# Initialize metadata files
python -m app.metadata.init

# Set secret key (user must provide)
echo "ORCHESTRATOR_SECRET_KEY=$(openssl rand -hex 32)" | sudo tee -a /etc/environment

# Install frontend
cd ../frontend
npm install
npm run build

# Configure Caddy (user must edit)
sudo cp Caddyfile.example /etc/caddy/Caddyfile
echo "Edit /etc/caddy/Caddyfile with your domain"
echo "Then: sudo systemctl restart caddy"
```

### 10.3 Systemd Service
File: `backend/systemd/dev-orchestrator.service`
```ini
[Unit]
Description=Dev Environment Orchestrator Backend
After=network.target snap.lxd.daemon.service
Requires=snap.lxd.daemon.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/dev-orchestrator/backend
Environment="PATH=/opt/dev-orchestrator/backend/venv/bin"
EnvironmentFile=/etc/dev-orchestrator/env
ExecStart=/opt/dev-orchestrator/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 10.4 Upgrade Path
- Version profiles under `lxc/profiles/{name}/v{X}`
- Allow container creation with specific version
- Document migration steps for breaking changes
- JSON schema versioning in metadata files
- If migrating to SQLite: Provide migration script `python -m app.db.migrate_from_json`

---

## 11. Documentation Requirements

### 11.1 User Documentation
- [x] `docs/architecture.md` — High-level design
- [x] `docs/user-guide.md` — How to use the system
- [ ] `docs/profiles.md` — Available profiles and how to create new ones
- [ ] `docs/installation.md` — Step-by-step setup guide
- [ ] `docs/troubleshooting.md` — Common issues and solutions
- [ ] `docs/api.md` — API reference (auto-generated from OpenAPI)

### 11.2 Developer Documentation
- [ ] `backend/README.md` — Backend development setup
- [ ] `frontend/README.md` — Frontend development setup
- [ ] `CONTRIBUTING.md` — How to contribute
- [ ] `lxc/profiles/README.md` — How to create custom profiles
- [ ] `lxc/cloud-init/README.md` — Cloud-init script guidelines

---

## 12. Alpha Feature Completeness Criteria

### 12.1 Core Features (Must Have)
- [x] LXD profiles for baseline + 2 environments (e.g., Python+ROCm, Node)
- [ ] Cloud-init scripts for profiles
- [ ] Backend API endpoints (create, list, start, stop, delete)
- [ ] Profile parser and dependency resolution
- [ ] Cloud-init merger
- [ ] JSON metadata store with atomic writes
- [ ] Frontend dashboard with container list
- [ ] Frontend create environment page
- [ ] Container lifecycle working end-to-end
- [ ] Export workspace functionality
- [ ] Secret injection (Claude/Copilot API keys)
- [ ] WebSocket-based terminal access

### 12.2 Nice to Have (for Alpha)
- [ ] GPU passthrough (ROCm or NVIDIA)
- [ ] Snapshot creation/restoration
- [ ] Auto-refresh dashboard
- [ ] Container resource usage display
- [ ] VS Code Server integration
- [ ] Idle container auto-stop

### 12.3 Post-Alpha
- Multi-user support with authentication
- Per-user resource quotas
- Advanced monitoring and metrics (Prometheus)
- Template versioning UI
- Container migration between hosts
- Backup/restore workflows
- CLI tool for power users

---

## 13. Implementation Order & Dependencies

### Phase 1: Foundation (Weeks 1-2)
1. **Host setup documentation**
   - LXD init guide
   - GPU driver installation
   - Create shared directories
2. **LXC baseline profile**
   - `lxc/profiles/base/baseline.yaml`
   - Basic cloud-init script
   - Test manual container creation
3. **Backend scaffolding**
   - FastAPI project structure
   - JSON metadata store initialization
   - Configuration loader
   - Basic logging

### Phase 2: Profile System (Week 3)
4. **Profile parser**
   - Parse profile string syntax
   - Load profile YAMLs
   - Dependency resolution algorithm
   - Unit tests
5. **Cloud-init merger**
   - Merge multiple cloud-init files
   - Deduplicate packages
   - Preserve runcmd order
   - Unit tests
6. **2-3 example profiles**
   - `/dev/python+rocm` with cloud-init
   - `/dev/node` with cloud-init
   - `/agent/claude` profile (adds Claude CLI)

### Phase 3: Backend Core (Weeks 4-5)
7. **LXD integration layer**
   - `LXDManager` class using `pylxd`
   - Container CRUD operations
   - Cloud-init attachment
   - Integration tests
8. **API endpoints**
   - Container create, list, start, stop, delete
   - Profile listing
   - Error handling middleware
9. **Secret management**
   - Encryption/decryption functions
   - Secret injection into containers

### Phase 4: Frontend (Week 6)
10. **Frontend scaffolding**
    - Vite + HTMX + Alpine + Tailwind setup
    - Layout and navigation
11. **Dashboard page**
    - Container list table
    - Status indicators
    - Action buttons
12. **Create environment page**
    - Profile selection
    - Form validation
    - API integration

### Phase 5: Integration (Week 7)
13. **WebSocket terminal**
    - xterm.js setup
    - Backend WebSocket endpoint
    - Connect to container exec
14. **Export workflow**
    - Backend: tar workspace, stream file
    - Frontend: download trigger
15. **Reverse proxy**
    - Caddyfile configuration
    - Test end-to-end HTTPS access

### Phase 6: Polish & Testing (Week 8)
16. **Testing**
    - Write unit tests (backend)
    - Manual testing checklist
    - Fix bugs
17. **Documentation**
    - Complete installation guide
    - Write profiles.md
    - API documentation
18. **Deployment**
    - Install script
    - Systemd service
    - Test fresh installation

### Phase 7: Alpha Release
19. **Alpha features verification**
    - Check all "must have" items
    - Test on clean Ubuntu 22.04 install
    - Document known limitations
20. **Release**
    - Tag v0.1.0-alpha
    - GitHub release notes
    - Announce to testers

---

## 14. Known Limitations & Future Work

### Alpha Limitations
- Single-user only (no authentication)
- No resource quotas or admission control
- Limited to local network access
- Manual profile creation (no UI)
- Basic error messages
- No container migration
- No multi-host support

### Future Enhancements (Post-Alpha)
- **v0.2.0**: Authentication, multi-user, quotas
- **v0.3.0**: Monitoring & metrics, Prometheus exporter
- **v0.4.0**: Profile versioning UI, template marketplace
---

## 15. Repository Structure

```
.
├─ backend/
│  ├─ app/
│  │  ├─ main.py              # FastAPI app entry point
│  │  ├─ config.py            # Configuration loader
│  │  ├─ api/
│  │  │  ├─ containers.py     # Container endpoints
│  │  │  ├─ profiles.py       # Profile endpoints
│  │  │  └─ websocket.py      # WebSocket endpoints
│  │  ├─ core/
│  │  │  ├─ lxd_manager.py    # LXD integration
│  │  │  ├─ profile_parser.py # Profile parsing & dependencies
│  │  │  ├─ cloudinit_merger.py  # Cloud-init merging
│  │  │  └─ secrets.py        # Secret management
│  │  ├─ metadata/
│  │  │  ├─ init.py           # Metadata store initialization
│  │  │  ├─ store.py          # JSON file operations
│  │  │  └─ models.py         # Pydantic models for validation
│  │  └─ schemas/
│  │     └─ container.py      # Pydantic schemas
│  ├─ tests/
│  │  ├─ unit/
│  │  ├─ integration/
│  │  └─ conftest.py
│  ├─ systemd/
│  │  └─ dev-orchestrator.service
│  ├─ requirements.txt
│  ├─ config.yaml.example
│  └─ README.md
├─ frontend/
│  ├─ src/
│  │  ├─ index.html
│  │  ├─ main.js
│  │  ├─ styles/
│  │  │  └─ main.css
│  │  ├─ components/
│  │  │  ├─ container-list.html
│  │  │  ├─ create-form.html
│  │  │  └─ terminal.html
│  │  └─ lib/
│  │     └─ api.js
│  ├─ public/
│  ├─ package.json
│  ├─ vite.config.js
│  └─ README.md
├─ lxc/
│  ├─ profiles/
│  │  ├─ README.md
│  │  ├─ base/
│  │  │  └─ baseline.yaml
│  │  ├─ dev/
│  │  │  ├─ python.yaml
│  │  │  ├─ node.yaml
│  │  │  └─ clang.yaml
│  │  ├─ agent/
│  │  │  ├─ claude.yaml
│  │  │  └─ copilot.yaml
│  │  └─ service/
│  │     ├─ rocm-gpu.yaml
│  │     ├─ nvidia-gpu.yaml
│  │     └─ vllm.yaml
│  └─ cloud-init/
│     ├─ README.md
│     ├─ base/
│     │  └─ baseline.yaml
│     ├─ dev/
│     │  ├─ python.yaml
│     │  ├─ node.yaml
│     │  └─ clang.yaml
│     ├─ agent/
│     │  ├─ claude.yaml
│     │  └─ copilot.yaml
│     └─ service/
│        ├─ rocm-gpu.yaml
│        ├─ nvidia-gpu.yaml
│        └─ vllm.yaml
├─ docs/
│  ├─ architecture.md
│  ├─ user-guide.md
│  ├─ profiles.md
│  ├─ installation.md
│  ├─ troubleshooting.md
│  ├─ api.md
│  └─ plan.md
├─ scripts/
│  ├─ install.sh
│  └─ test-lxd-setup.sh
├─ .github/
│  └─ workflows/
│     ├─ test.yml
│     └─ lint.yml
├─ AGENTS.md
├─ CONTRIBUTING.md
├─ LICENSE
├─ README.md
└─ Caddyfile.example
```

---

## 16. Milestones (Revised)

### Milestone 1 — Foundation & Profiles (2 weeks)
**Goal**: Host ready, baseline profile working, profile system designed

Deliverables:
- [ ] Host setup documentation complete
- [ ] LXD initialized with baseline profile
- [ ] Manual container creation tested
- [ ] Backend project scaffolding (FastAPI + JSON metadata store)
- [ ] Profile YAML format defined
- [ ] Cloud-init YAML format defined
- [ ] 2-3 profile YAMLs created (baseline, python, claude agent)
- [ ] 2-3 cloud-init scripts written

### Milestone 2 — Backend Core (2 weeks)
**Goal**: Backend API functional, profile parsing works

Deliverables:
- [ ] Profile parser with dependency resolution
- [ ] Cloud-init merger implementation
- [ ] LXD integration layer (`LXDManager`)
- [ ] JSON metadata store with atomic writes and backups
- [ ] API endpoints: create, list, start, stop, delete
- [ ] Secret management implemented
- [ ] Unit tests for core logic (>80% coverage)
- [ ] Integration tests for LXD operations

### Milestone 3 — Frontend MVP (2 weeks)
**Goal**: Basic web UI for container management

Deliverables:
- [ ] Frontend project setup (Vite + HTMX + Alpine + Tailwind)
- [ ] Dashboard page with container list
- [ ] Create environment page
- [ ] Container detail page
- [ ] API integration working
- [ ] Basic responsive design

### Milestone 4 — Integration & Terminal (1 week)
**Goal**: End-to-end workflow functional

Deliverables:
- [ ] WebSocket terminal working (xterm.js)
- [ ] Export workspace feature
- [ ] Reverse proxy configured (Caddy)
- [ ] HTTPS working end-to-end
- [ ] Manual testing checklist completed

### Milestone 5 — Polish, Docs, & Alpha Release (1 week)
**Goal**: Alpha-ready release

Deliverables:
- [ ] Installation guide written
- [ ] Profiles documentation
- [ ] API documentation (OpenAPI)
- [ ] Install script tested
- [ ] Systemd service working
- [ ] Fresh Ubuntu install tested
- [ ] Known limitations documented
- [ ] Tag v0.1.0-alpha release

### Milestone 6 (Post-Alpha) — Advanced Features
- Snapshot/restore
- GPU passthrough tested
- VS Code Server integration
- Resource usage monitoring
- Idle auto-stop

### Milestone 7 (Post-Alpha) — Multi-User & Production
- Authentication & authorization
- User quotas
- Metrics & monitoring
- High availability setup

---

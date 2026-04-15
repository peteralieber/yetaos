# Project Architecture

## High-level components

### Home server

* Host OS: Linux (e.g., Ubuntu Server)
* Virtualization layer: LXC/LXD
* GPU stack: ROCm and/or NVIDIA drivers on host
* Reverse proxy: nginx or Caddy (TLS, routing to web backend)
* Service supervisor: systemd units or docker-compose (for the web app only)

### Orchestrator service

* Backend API: FastAPI (Python) or Go HTTP service
* Responsibilities:
  * Manage LXC profiles and containers
  * Expose REST API for container lifecycle
  * Track metadata (env type, owner, ephemeral flag, created_at, etc.)
  * Handle artifact export (tarball creation + download)
  * Provide logs/status for containers
* State storage:
  * Lightweight DB (SQLite) or just a JSON/YAML registry for container metadata
  * No secrets in DB—use environment variables or host secret store

### Web UI

* Frontend: Minimal HTMX, justify anything more like Alpine
* Responsibilities:
  * Environment selection and configuration
  * Container list (running, stopped, ephemeral, persistent)
  * Actions: create, start, stop, delete, export artifacts
* Links to:
  * Web shell (e.g., wetty/ttyd) or
  * VS Code Server / code-server endpoint inside container

### LXC layer

* Images:
  * Base images: ubuntu:22.04 or ubuntu:24.04
* Declarative Profiles: /{use-case}/{tools}/{agents}/
* Profiles Examples:
  * /dev/python+rocm/copilot/
  * /dev/clang:riscv+vllm/claude/
  * /dev/node+electron/claude/
  * /genai/comfyui//
  * /model/blender//
* Profile responsibilities:
  * Resource limits (CPU, RAM)
  * GPU passthrough (ROCm/NVIDIA)
  * Network config (bridged or NAT)
  * Storage config:
    * Root filesystem
    * Optional shared /models mount
    * Optional shared /data mount
  * Cloud-init user-data for deterministic provisioning

### Per-container layout

Inside each container:
* /workspace — primary working directory (mounted volume or container-local)
* /opt/tools — installed dev tools and CLIs
* /models — optional shared read-only model cache from host
* /etc/dev-orchestrator/metadata.json — environment metadata (env type, version, etc.)

### GPU passthrough

* ROCm:
  * Host: ROCm drivers installed
  * LXC: devices section mapping GPU devices
  * Profiles: rocm-gpu profile that can be combined with others
* NVIDIA:
  * Host: NVIDIA drivers + nvidia-container-runtime style setup
  * LXC: nvidia.runtime config or explicit device mappings

### Networking

* LXD bridge (e.g., lxdbr0) for containers
* Orchestrator backend can:
  * Talk to LXD via Unix socket
  * Expose container services via:
  * Reverse proxy routes (e.g., /containers/<name>/code)
  * Or port-forwarding from host to container

### Security boundaries

* LXC isolation (namespaces, cgroups, AppArmor)
* No host filesystem mounts by default except:
  * Optional read-only /models
  * Optional read-only /data
* API auth:
  * Local-only access (home LAN/VPN)
  * Optional user accounts with JWT or simple session auth
* No secrets baked into images; injected at runtime via:
  * Environment variables
  * LXC config keys

Orchestrator secret store

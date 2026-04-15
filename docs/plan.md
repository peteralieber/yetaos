# Implementation Plan

This plan defines the decisions, scope, and step-by-step work needed to reach a **full alpha** for the Dev Environment Orchestrator (LXC/LXD + FastAPI backend + lightweight web UI). It favors explicit, declarative configuration and deterministic behavior.

---

## 1) Alpha Goals & Exit Criteria
- One-click creation of curated environments via declarative profile strings.
- Working profiles for: baseline, `dev/python`, `dev/clang:riscv`, `dev/node`, `dev/electron`, `genai/comfyui`, `model/blender`, GPU services (`rocm-gpu`, `nvidia-gpu`), `vllm`, VS Code Server, Claude, Copilot.
- Cloud-init merging that is idempotent and deterministic (no interactive prompts; pinned package versions where available).
- Backend API (FastAPI) exposing lifecycle (create/list/start/stop/delete), export, logs, metadata; talks to LXD via unix socket.
- Metadata persisted in SQLite with schema migrations and pruning for deleted containers.
- Frontend usable for dashboard, create form, container detail with actions (logs, shell link, VS Code link, export).
- Reverse proxy wiring (`/api`, `/containers/<name>/code`, `/containers/<name>/shell`).
- Basic auth (local-only optional bypass), secrets injection for AI CLIs, and audit/metrics endpoints.
- Automated tests: backend unit + integration (mock LXD), profile parser tests, cloud-init merge dry-run, and frontend smoke tests.

---

## 2) Host System Setup
- **LXD**: Install via snap; `lxd init` non-interactive with `lxdbr0`, ZFS (or BTRFS) pool, IPv4 NAT enabled, IPv6 optional. Store config in `docs/host-setup.md` with exact commands and answers.
- **GPU**: ROCm (default) instructions pinned to specific release; NVIDIA optional with `nvidia-container-runtime` style passthrough. Validate with `rocminfo`, `clinfo`, `nvidia-smi` where applicable.
- **Shared dirs** (created by orchestrator installer script):
  - `/srv/dev-orchestrator/models` (ro)
  - `/srv/dev-orchestrator/data` (rw optional)
  - `/srv/dev-orchestrator/containers` (persistent workspaces)
- **System users & groups**: ensure orchestrator service user is in `lxd`, `video`, `render` (for ROCm), and `docker` if needed.
- **Package pinning**: document apt preferences for critical deps (clang, ROCm, node, python) to avoid drift.

---

## 3) Repository Structure (target)
```
.
├─ backend/            # FastAPI app
│  ├─ app/
│  │  ├─ api/         # Routers
│  │  ├─ core/        # settings, logging
│  │  ├─ lxd/         # LXD client, profile builder
│  │  ├─ models/      # Pydantic schemas
│  │  ├─ persistence/ # SQLite access layer
│  │  ├─ services/    # orchestration logic
│  │  └─ tests/
│  └─ README.md
├─ frontend/          # SvelteKit (Vite) UI
│  ├─ src/
│  ├─ static/
│  ├─ tests/
│  └─ README.md
├─ lxc/
│  ├─ profiles/       # YAML profiles (baseline, services, agents, tools)
│  └─ cloud-init/     # cloud-init fragments per profile
├─ docs/
│  ├─ architecture.md
│  ├─ user-guide.md
│  ├─ profiles.md
│  └─ plan.md
├─ scripts/           # install, lxd init, dev helpers (idempotent)
├─ AGENTS.md
└─ README.md
```

---

## 4) Profiles & Template System
- **Profile string format**: `/use-case/tools/agents/services/` where each segment is `item[:sub]` joined with `+`. Parser validates order and unknown items.
- **Profiles directory**: `lxc/profiles/<category>/<name>.yaml` with metadata (description, version, dependencies, mounts, devices, limits, required cloud-init fragments).
- **Dependencies**: Directed acyclic graph resolved right-to-left (services → agents → tools → use-case). Implement resolver with deterministic ordering; fail on cycles.
- **Baseline profile** (`profiles/base.yaml`): Ubuntu 22.04 LTS, `lxdbr0`, CPU/RAM defaults, cloud-init enabled, workspace mounts.
- **Services**: `service/rocm-gpu.yaml`, `service/nvidia-gpu.yaml`, `service/vllm.yaml`, `service/vscode-server.yaml` (mount `/workspace`, `/models`, AppArmor allowances, GPU device mappings, ulimits if needed).
- **Agents**: `agent/claude.yaml`, `agent/copilot.yaml`, `agent/opencode.yaml`, `agent/openclaw.yaml` with required CLI binaries and config paths.
- **Tools**: `dev/python.yaml`, `dev/clang:riscv.yaml`, `dev/node.yaml`, `dev/electron.yaml` (depends on node), `genai/comfyui.yaml`, `model/blender.yaml`.
- **Validation**: schema check for every profile (YAML validation), ensure every profile references a cloud-init fragment and declares mounts/devices explicitly.
- **Command-line helper**: `scripts/profile-string` to render resolved profile list for debugging (no side effects).

---

## 5) Cloud-Init Assembly
- **Fragments**: `lxc/cloud-init/<category>/<name>.yaml` with idempotent tasks; no interactive prompts; apt with pinned versions or explicit channels.
- **Merge engine**: backend builds a combined cloud-init by concatenating fragments in dependency order, deduping packages and ensuring filesystem prep (`/workspace`, `/models`, `/data`).
- **Common tasks**: update packages, create service user, install AI CLIs (Claude, Copilot), install VS Code Server (optional), write `/etc/dev-orchestrator/metadata.json`, configure locale/timezone.
- **Per-tool specifics**: Python (3.11 + uv + venv + PyTorch ROCm); RISC-V (Clang 18 + riscv-gnu toolchain + qemu-riscv); Node (LTS + pnpm); Electron (builder); Blender CLI; ComfyUI (clone + deps); vLLM (pinned version).
- **Caching**: allow optional host-mounted package cache to speed installs (`/srv/dev-orchestrator/cache`).
- **Verification**: `scripts/validate-cloud-init` dry-run to ensure merge produces valid YAML.

---

## 6) Backend Service (FastAPI)
- **Tech choice**: FastAPI + uvicorn; Pydantic v2 schemas; httpx for outbound calls if needed; dependency injection via FastAPI Depends.
- **Config**: `Settings` object from env vars (.env support) for LXD socket path, DB path, mount roots, auth mode, feature flags (GPU enabled, VS Code enabled, secret injection enabled).
- **Modules**:
  - `api` routers for containers, profiles, logs, export, health, metrics.
  - `lxd` client wrapper (unix socket via pylxd or custom requests) with retry/backoff.
  - `services` orchestration (build profile list, assemble cloud-init, call LXD, update metadata store).
  - `persistence` SQLite (SQLModel/SQLAlchemy) with migrations (Alembic) and repo layer.
  - `models` Pydantic schemas for requests/responses.
- **Endpoints**:
  - `POST /containers/create` (body: name, profileString, ephemeral, gpu, env vars/secrets flags)
  - `POST /containers/start|stop|delete`
  - `GET /containers` (list with status from LXD + metadata)
  - `GET /containers/{name}` (details + resolved profiles)
  - `GET /containers/{name}/logs` (LXD logs tail)
  - `POST /containers/{name}/export` (stream tar.gz)
  - `GET /profiles` (return available profile definitions)
  - `GET /health`, `GET /metrics` (Prometheus text)
- **Error handling**: map LXD errors to 4xx/5xx, include correlation id; structured logging (JSON) with request id middleware.

---

## 7) LXD Integration
- Communicate via `/var/snap/lxd/common/lxd/unix.socket` with least privileges (service user in `lxd`).
- Implement functions: launch with profiles + cloud-init, start/stop/delete, get state, exec (for diagnostics), pull files.
- Enforce mounts: `/workspace` (persistent if non-ephemeral), `/models` (ro), `/data` optional.
- GPU: add devices per profile, verify presence before launch; fail fast if GPU requested but unavailable.
- Artifact export: use `lxc exec` tar stream; throttle/limit size; clean temp files.
- Logging: surface LXD task output to `/containers/{name}/logs` endpoint.

---

## 8) Persistence / Metadata Store
- SQLite database file in `/var/lib/dev-orchestrator/state.db` (configurable).
- Tables: `containers` (name, profile_string, resolved_profiles, ephemeral, gpu, created_at, last_used, status, workspace_volume, secrets_present), `events` (audit), `migrations` table via Alembic.
- On delete, mark tombstone; nightly prune job to drop tombstoned + remove unused volumes.
- Backup strategy: optional cron to dump DB to `/srv/dev-orchestrator/backups`.

---

## 9) Frontend Web UI
- **Tech choice**: SvelteKit + Vite (minimal state), TypeScript, Tailwind (utility-first, small theme), fetch REST directly.
- Pages:
  - Dashboard: list containers with status chips and actions (start/stop/delete/export/logs).
  - Create Environment: profile selector (renders available profiles + dependencies), name validation, toggles for ephemeral/GPU/VS Code/agents, preview of cloud-init tasks.
  - Container Detail: status, resolved profiles, logs viewer, links to shell (ttyd) and VS Code Server.
- Components: API client wrapper, badge/pill components, form validation.
- Testing: Playwright smoke (build + basic flows); unit tests for helpers.

---

## 10) Reverse Proxy & Access
- Use **nginx** with explicit config (template in `scripts/nginx.conf`): TLS termination (self-signed or provided certs), proxy `/api/*` to backend, `/containers/<name>/code` to VS Code Server, `/containers/<name>/shell` to ttyd/wetty container endpoints.
- Optional basic auth at proxy; header passthrough for request id.
- CORS: allow LAN origins configurable.

---

## 11) Container Lifecycle Rules
- **Create**: validate name, resolve profile string, ensure mounts exist, generate cloud-init, launch container, persist metadata.
- **Ephemeral**: use `--ephemeral`; hook stop event to auto-delete.
- **Persistent**: create named LXD volume for `/workspace`; snapshots allowed; on delete remove volume unless `retain` flag set.
- **Stop/Delete**: drain running processes politely, timeout -> forced stop; delete handles both ephemeral and persistent paths.
- **Idle shutdown (optional alpha)**: background job checks CPU/net thresholds, auto-stop after configurable idle window.

---

## 12) Observability, Security, Secrets
- Metrics: Prometheus endpoint (container counts, launch latency, LXD errors, export durations, idle shutdown actions).
- Logs: JSON to stdout; request id middleware; audit table for lifecycle actions.
- Secrets: inject Claude/Copilot tokens via LXC config keys or host secret file mounted read-only; never store tokens in DB.
- Hardening: AppArmor allowances only per profile; disable password login in containers; configure ufw on host to expose only needed ports.

---

## 13) Testing & QA
- Backend unit tests: profile resolver, cloud-init merger, API validation.
- Backend integration tests: mock LXD socket responses; sqlite against temp file; artifact export streaming.
- Cloud-init validation: YAML lint + dry-run merge script; idempotency check by rerunning in temp LXD container (CI optional).
- Frontend: lint + type check + Playwright smoke (dashboard render, create form validation).
- Installer scripts: shellcheck + `set -euo pipefail` sanity run in container.

---

## 14) Milestones to Alpha
- **M1 Host & Scaffolding**: host setup docs + scripts; repo structure scaffolding; baseline profile and base cloud-init fragment; CI lint/test pipeline skeleton.
- **M2 Profiles & Cloud-Init**: implement profile definitions, resolver, merge engine; fragments for all listed tools/services/agents; validation script.
- **M3 Backend Core**: FastAPI app with lifecycle endpoints, LXD client wrapper, metadata store, logging/metrics, artifact export, profile listing.
- **M4 Frontend MVP**: SvelteKit UI for dashboard/create/detail; API client; proxy config; Playwright smoke tests.
- **M5 Integrations & Polish**: VS Code Server + ttyd wiring, GPU pass-through validation, secret injection, idle shutdown optional, error surfacing; backup/prune jobs.
- **Alpha Exit**: All goals met, tests passing, docs updated (architecture, user-guide, profiles), and installer script verified on clean host.


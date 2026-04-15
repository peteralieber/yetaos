Agent Project Instructions

This repository contains a **Dev Environment Orchestrator** for a home server using **LXC/LXD**.

The goal is to provide a **deterministic, reproducible, and privacy-respecting** way to launch curated dev environments (Python+ROCm, Clang+RISC-V, Node+Electron, Blender, ComfyUI, etc.) with AI CLIs like **Claude CLI** and **Copilot CLI**.

## Architectural principles

- Prefer **explicit, declarative configuration** over magic.
- All environment behavior should be **reproducible** from:
  - LXC profiles
  - Cloud-init scripts
  - Versioned configuration files
- No hidden state: avoid ad-hoc manual changes inside containers.
- Keep the orchestrator **stateless** where possible; use a small metadata store only for container tracking.

## Code style and expectations

- Backend:
  - If using Python: FastAPI, type hints, Pydantic models, clear separation of:
    - API layer
    - LXD integration layer
    - Persistence layer
  - If using Go: idiomatic Go modules, clear package boundaries.
- Frontend:
  - Keep UI minimal and functional.
  - Prefer simple state management and explicit API calls.
- Scripts:
  - Use **idempotent** cloud-init and provisioning scripts.
  - Avoid interactive prompts; everything should be non-interactive.

## What Copilot should prioritize

- **Clarity over cleverness**:
  - Write code that is easy to read and reason about.
- **Determinism**:
  - Avoid relying on “latest” tags or unpinned dependencies where possible.
- **Composability**:
  - Make it easy to add new environment types by:
    - Adding a new profile
    - Adding a new cloud-init script
    - Registering it in a single configuration file

## Tasks Copilot can help with

- Implementing REST endpoints for:
  - Container lifecycle (create, list, start, stop, delete)
  - Artifact export
- Writing LXD integration helpers:
  - Launching containers with specific profiles
  - Attaching cloud-init user-data
  - Querying container status
- Generating frontend components:
  - Environment creation form
  - Container list with actions
- Writing documentation:
  - Environment template definitions
  - Example workflows

## Things to avoid

- Do not introduce external hosted dependencies that compromise privacy.
- Do not assume public cloud services; everything runs on a **home server**.
- Do not hide important behavior behind complex abstractions.

If in doubt, **prefer explicit configuration and simple, testable code**.

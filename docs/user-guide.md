# Preliminary User Guide

## Overview

This system lets you spin up **on-demand dev environments** on your home server, each isolated in an LXC container and preloaded with specific tools and AI CLIs. You can create ephemeral “scratchpads” or persistent workspaces you can return to later, and export artifacts when you’re done.

## Concepts

- **Environment type:** A predefined template like `/dev/python-rocm`, `/dev/clang-riscv-vllm`, `/dev/node-electron`, `/model/blender`, `/genai/comfyui`.
- **Container:** A running instance of an environment type with its own filesystem and tools.
- **Ephemeral container:** Auto-deleted after it stops.
- **Persistent container:** Stays on disk until you delete it; can be resumed later.
- **Workspace:** `/workspace` inside the container, where you keep your project files.

## Typical workflow

1. **Open the web launchpad**

   - Navigate to the orchestrator URL on your LAN (e.g., `https://dev-orchestrator.local`).
   - Log in if authentication is enabled.

2. **Create a new environment**

   - Click **“New Environment”**.
   - Choose an environment type, for example:
     - `/dev/python + pytorch + rocm/claude+copilot/`
     - `/dev/clang->RISCV + vllm/copilot/`
     - `/dev/node+electron/claude/`
     - `/model/blender//`
     - `/genai/comfyui/copilot/`
   - Enter a **container name** (e.g., `pytorch-lab-1`).
   - Choose:
     - **Ephemeral** or **Persistent**
     - **GPU enabled** (if applicable)
   - Click **Create**.

3. **Wait for provisioning**

   - The UI will show the container status as it boots and runs cloud-init.
   - Once ready, the status changes to **Running** and actions become available.

4. **Open the environment**

   - From the container row, choose:
     - **Open Shell** → launches a browser-based terminal into the container.
     - **Open VS Code** → opens VS Code Server (if enabled for that template).
   - Inside the shell or VS Code:
     - Work under `/workspace`.
     - Use installed tools (e.g., `python`, `uv`, `clang`, `node`, `blender`, `comfyui`, `claude`, `gh copilot`).

5. **Use AI CLIs**

   - Claude CLI:
     - Run commands like `claude chat` or `claude ask` from `/workspace`.
   - Copilot CLI:
     - Use `gh copilot` or `copilot` depending on how it’s installed.
   - Any required API keys are injected by the orchestrator or configured per-user.

6. **Export artifacts**

   - When you’re done with a session, click **Export** for that container.
   - The system will:
     - Tar `/workspace` inside the container.
     - Stream a `.tar.gz` file to your browser.
   - Save it locally or into your own storage.

7. **Stop or delete the container**

   - **Ephemeral containers:**
     - When you click **Stop**, the container is automatically deleted.
   - **Persistent containers:**
     - You can **Stop** to free resources and **Start** later.
     - Use **Delete** to remove it permanently.

## Example use cases

- **Quick experiment with PyTorch + ROCm + Claude/Copilot**
  - Create ephemeral `/dev/python-rocm` container.
  - Prototype a model, ask Claude/Copilot for code suggestions.
  - Export results, stop container → it disappears.

- **Long-running RISC-V toolchain project**
  - Create persistent `/dev/clang-riscv-vllm` container.
  - Keep code in `/workspace`.
  - Take snapshots before major changes.
  - Resume whenever you want.

- **Blender rendering node**
  - Create `/model/blender` container with GPU.
  - Drop scenes into `/workspace`.
  - Render via CLI, export outputs.

# PR #1 vs PR #2 — Design Comparison

This repo currently contains early-stage documentation only; PR #1 and PR #2 are both documentation-only proposals that expand `docs/plan.md` into an “alpha spec”.

This document compares the two proposals with the goal stated in the issue: determine which is the better design, focusing on:

- Simplicity
- Simple implementation
- Testability
- Approachability for a new developer

## What each PR proposes (high-level)

### PR #1 summary

- Backend: FastAPI + `pylxd`
- Frontend: HTMX + Alpine.js (no build step)
- Reverse proxy: Caddy
- Metadata store: JSON (`containers.json`)
- Auth: API key in `.env`
- Logs: SSE
- Shell/code: `ttyd` + `code-server`

### PR #2 summary

- Backend: FastAPI + `pylxd` (same)
- Frontend: HTMX + Alpine.js + Tailwind + Vite (build step)
- Reverse proxy: Caddy
- Metadata store: SQLite (4 tables)
- Auth: local-only for alpha (no auth)
- Logs: includes WebSocket terminal approach, plus more pages/features

## Comparison by criteria

### 1) Simplicity

**PR #1 is simpler.**

- JSON metadata store is conceptually and operationally simpler than SQLite.
- “No build step” frontend keeps the dev loop simple (edit templates → refresh).
- The proposal keeps the “alpha spec” closer to the minimum necessary for an MVP.

PR #2 adds significant surface area in the plan:

- SQLite schema + migrations/upgrade path decisions (even if implied) adds complexity.
- Vite/Tailwind implies node toolchain, dependency installs, build artifacts, and more moving parts.
- More endpoints/pages (snapshots, multi-doc requirements, multi-week timeline) expands scope.

### 2) Simple implementation

**PR #1 is more directly implementable with fewer prerequisites.**

- A JSON store can be implemented with a small amount of standard library code and tested with pure unit tests.
- HTMX + Jinja templates can ship without a frontend build system. That reduces the “tooling tax” when bootstrapping.
- The plan is opinionated enough to start coding, but doesn’t over-specify every component.

PR #2’s implementation burden is higher:

- SQLite adds schema definition, connection lifecycle, concurrency, and migration strategy. Those are solvable, but are additional work before reaching visible value.
- Frontend build pipeline increases time-to-first-contribution for anyone not already familiar with JS tooling.

### 3) Testability

This criterion is closer than it looks:

- **SQLite** can be very testable (in-memory DB, transactional tests), but only once the persistence layer exists and is wired.
- **JSON** can also be very testable (pure functions + temp file store), and it tends to require less scaffolding to get meaningful tests running early.

Given this project’s stated goals (home server scale, deterministic config, minimal hidden state), **PR #1’s JSON store is a better fit** because:

- Most logic can be tested without a DB.
- It’s easier to inspect/repair manually on a home server.
- Atomic writes (`os.replace`) plus a lock are usually sufficient at the expected scale.

If/when the project grows beyond “single-node home server, tens of containers”, moving to SQLite later is plausible.

### 4) Approachability for a new developer

**PR #1 is more approachable.**

- Fewer technologies: Python + FastAPI + HTMX templates + JSON.
- Less setup friction: no node toolchain required for the initial UI.
- Clear and minimal operational model for state (one file to inspect).

PR #2 is still approachable for experienced full-stack developers, but it raises the baseline:

- Developers must be comfortable with Node/Vite/Tailwind plus Python.
- More planned files and components increase “where do I start?” ambiguity.

## Notable design differences (tradeoffs)

### Auth

- PR #1 includes an API key for mutating endpoints.
- PR #2 proposes local-only for alpha (no auth).

For a home-server product, even alpha should assume LAN access (and sometimes VPN). **PR #1’s “simple API key” is a good minimal security baseline** and does not add much complexity.

### Persistence choice (JSON vs SQLite)

- If you want the fastest path to an MVP: prefer **JSON**.
- If you strongly prefer relational data and expect multiple users / many records soon: consider **SQLite**.

Given the issue’s criteria (simplicity/approachability) and the repo’s “stateless where possible” stance, JSON fits better today.

### Frontend toolchain

- PR #1 “no build step” is aligned with minimalism.
- PR #2’s Tailwind/Vite can improve UI iteration once the project grows, but is optional for an MVP.

## Recommendation

**Adopt PR #1’s overall approach as the baseline** (FastAPI + `pylxd`, HTMX/Alpine, JSON metadata store, simple API-key auth).

If you want to incorporate ideas from PR #2, the two highest-value items to cherry-pick later are:

- The more structured endpoint naming (`/api/v1/...`)
- The testing-strategy emphasis (unit/integration split)

But PR #2’s “bigger spec” (SQLite + Vite/Tailwind + expanded pages/timeline) is better treated as a post-MVP roadmap, not the initial design.


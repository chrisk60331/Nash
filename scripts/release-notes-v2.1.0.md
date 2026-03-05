# Nash v2.1.0

**Changes since v2.0.0** — minor release with a dedicated init flow, auth/agents/chat improvements, in-memory caching, and docs.

---

## Init flow (batch bootstrap)

- **New `/api/init` endpoint** — Replaces ~15 individual API calls on first page load. Fetches the user’s config-assistant memories once, partitions them by metadata type (conversations, thread mappings, agents, files, presets, prompt groups, favorites, tags, folders), and returns a single payload so the frontend can hydrate from one request.
- **Frontend Init module** — New `client/src/data-provider/Init/` with React Query hooks that call `/api/init` and expose the bootstrapped data for the app.
- **Root/Root.tsx** — Wires the init query into the app so the initial load uses the batch endpoint instead of many parallel Backboard calls.

## Backend

- **Auth (`api/routes/auth.py`)** — Expanded Google OAuth and JWT handling (92 lines added): refresh flow, error handling, and session behavior.
- **Agents (`api/routes/agents.py`)** — Richer agent CRUD and Backboard integration; background migration for agents missing `bb_assistant_id` so existing agents get a Backboard assistant when needed.
- **Chat (`api/routes/chat.py`)** — Streaming and conversation handling improvements (52 lines added).
- **Config routes (`api/routes/config_routes.py`)** — Small adjustments for compatibility with init and config-assistant usage.
- **Conversations (`api/routes/conversations.py`)** — Tweaks for conversation listing and structure.
- **Conversation service** — Uses init/cache where appropriate and stays consistent with the new init flow.
- **User service** — Updates for config-assistant lookup and user resolution used by init and auth.
- **Memory cache (`api/services/memory_cache.py`)** — New short-lived in-process cache for `get_memories(config_assistant_id)`. Multiple endpoints that previously each called Backboard now share one result within a 5s TTL; concurrent callers for the same assistant wait on the first fetch instead of issuing duplicate requests.
- **App/config** — App factory and config wiring for the new routes and services.

## Frontend

- **SocialButton** — Small fix for Google OAuth button behavior.
- **useResumableSSE** — Resumable SSE hook adjusted for stability.
- **Root** — Init query integration and loading/error handling for the bootstrap step.
- **data-provider** — New Init queries and exports; `api-endpoints` and `data-service` updated for the init endpoint.

## Docs and cleanup

- **README.md** — New project README: quick start, architecture diagram, features, tech stack, project layout, deployment (Docker, Terraform, App Runner).
- **docs/** — Added `logo-dark.svg` and `logo-light.svg` for light/dark README branding.
- **Removed** — `.env.production` and the NIPS PDF from the repo to avoid committed secrets and large binaries.

---

## Summary

| Area        | Change |
|------------|--------|
| **API**    | `/api/init` batch bootstrap; auth, agents, chat, config, conversations improvements; memory cache service |
| **Client** | Init data-provider and Root integration; SocialButton and SSE hook fixes |
| **Docs**   | README and logo assets; repo cleanup |

**Upgrade:** Pull `v2.1.0`, run `./start.sh` (or your usual deploy). No schema or config changes required beyond existing Backboard and env setup.

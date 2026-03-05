<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/logo-light.svg">
    <img alt="Nash" src="docs/logo-light.svg" width="320">
  </picture>
</p>

<p align="center">
  <strong>AI chat for everyone — one interface, every model.</strong>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#architecture">Architecture</a> &bull;
  <a href="#features">Features</a> &bull;
  <a href="#deployment">Deployment</a>
</p>

---

Nash is a full-stack AI chat application that gives users unified access to models from OpenAI, Anthropic, Google, xAI, Cohere, AWS Bedrock, and more — all through a single, polished interface. Built on [Backboard.io](https://backboard.io) for data and AI orchestration, with a React frontend forked from LibreChat.

## Quick Start

**Prerequisites:** Python 3.11+, Node 20+, [uv](https://docs.astral.sh/uv/)

```bash
cp .env.example .env   # configure your keys
./start.sh             # installs deps, builds frontend, starts everything
```

| Service  | URL                     |
|----------|-------------------------|
| App      | http://localhost:3090    |
| API      | http://localhost:3080    |

Logs stream to `/tmp/nash-api.log` and `/tmp/nash-frontend.log`.

## Architecture

```
┌──────────────────────┐        ┌──────────────────────┐
│                      │        │                      │
│   React Frontend     │───────▶│   Flask API          │
│   Vite  · Tailwind   │  REST  │   JWT  · Pydantic    │
│   :3090              │  SSE   │   :3080              │
│                      │        │                      │
└──────────────────────┘        └──────────┬───────────┘
                                           │
                          ┌────────────────┼────────────────┐
                          │                │                │
                          ▼                ▼                ▼
                   ┌────────────┐   ┌────────────┐   ┌───────────┐
                   │ Backboard  │   │   Stripe   │   │  Google   │
                   │ Assistants │   │  Billing   │   │  OAuth    │
                   │ Threads    │   │            │   │           │
                   │ Memories   │   └────────────┘   └───────────┘
                   │ Documents  │
                   └────────────┘
```

**Backend** — Python/Flask API handles auth, chat streaming (SSE), file uploads, billing, and all business logic. Every data operation goes through `backboard-sdk`; there is no separate database.

**Frontend** — React app built with Vite and Tailwind. Communicates with the API over REST and Server-Sent Events for real-time chat streaming.

**Backboard.io** — Serves as both the AI gateway and the data layer. User records, conversations, agent configs, memories, and uploaded documents all live as Backboard resources (assistants, threads, memories, documents).

## Features

**Multi-provider AI** — Access 100+ models across OpenAI, Anthropic, Google, xAI, Cohere, Cerebras, AWS Bedrock, Featherless, and OpenRouter through a single interface.

**Custom Agents** — Create agents with custom instructions that persist across conversations. Each agent's configuration is stored in Backboard.

**File-Aware Chat** — Upload documents and images directly into conversations. Files are indexed in Backboard for retrieval-augmented generation.

**Conversations & Memory** — Full conversation history with folders, tags, search, and shared links. User-level memory that the AI retains across threads.

**Google OAuth** — One-click sign-in with Google. JWT-based session management with refresh tokens.

**Subscription Billing** — Stripe-powered plans with token-based usage limits (Free / Plus / Unlimited). Managed through the API with webhooks.

**Prompts & Presets** — Save and reuse prompt templates and model presets across conversations.

## Tech Stack

| Layer       | Technology                                            |
|-------------|-------------------------------------------------------|
| Backend     | Python 3.12, Flask, Pydantic, backboard-sdk           |
| Frontend    | React 18, Vite, Tailwind CSS, Turborepo               |
| Auth        | Google OAuth, PyJWT, Authlib                          |
| Data & AI   | Backboard.io (assistants, threads, memories, docs)    |
| Billing     | Stripe (subscriptions, webhooks)                      |
| Deploy      | Docker multi-stage, Terraform, AWS App Runner + ECR   |

## Project Structure

```
nash2.0/
├── api/                    # Python backend
│   ├── app.py              #   Flask app factory
│   ├── config.py           #   Pydantic settings
│   ├── middleware/          #   JWT auth
│   ├── routes/             #   All API endpoints
│   └── services/           #   Backboard, billing, users
├── client/                 # React frontend
│   ├── src/                #   App source
│   └── dist/               #   Production build
├── packages/               # Shared monorepo packages
├── scripts/                # Smoke tests
├── terraform/              # AWS infrastructure
├── librechat.yaml          # Model & endpoint config
├── Dockerfile              # Multi-stage production build
├── start.sh                # Local dev startup
├── build.sh                # Build & deploy pipeline
└── pyproject.toml          # Python dependencies (uv)
```

## Deployment

Production builds use a multi-stage Docker image — Node builds the frontend, then Python serves everything via Gunicorn.

```bash
./build.sh <env> <tag>      # terraform + docker + push + deploy
```

The pipeline: Terraform provisions ECR, Docker builds a `linux/amd64` image, pushes to ECR, Terraform applies App Runner config, then triggers a deployment and waits for it to go live.

Infrastructure is managed with Terraform modules for ECR, SSM secrets, and App Runner. All secrets (API keys, JWT secrets, Stripe keys) are stored in AWS SSM Parameter Store.

## License

Proprietary. All rights reserved.

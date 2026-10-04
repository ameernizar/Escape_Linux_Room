# Escape the Terminal

Competition-grade Linux escape room for 20–30 teams, designed for a single LAN server. The control plane is FastAPI + PostgreSQL; every team works inside an unprivileged, network-disabled container. Challenge secrets are generated deterministically on the server and are never sent to the browser.

## Quick start (development)

1. Copy `.env.example` to `.env` and set strong `SECRET_KEY` and `ADMIN_BOOTSTRAP_PASSWORD` values.
2. Run `docker compose up --build`. For an explicitly local, single-machine terminal trial only, add `-f docker-compose.dev.yml`; its Docker socket mount is forbidden for event deployment.
3. Open `http://localhost:8000/docs`; bootstrap the organizer with `POST /api/v1/admin/bootstrap`.

This repository implements the competition control plane and deterministic six-door challenge generator. The terminal proxy is deliberately an integration boundary: it must be connected to a reviewed container-runtime adapter before an event. See [DEPLOYMENT.md](DEPLOYMENT.md) and [SECURITY.md](SECURITY.md).

## Repository map

- `backend/` — API, state machine, scoring and database model.
- `challenges/` — deterministic per-team instance generator.
- `player-image/` — minimal non-root player shell image.
- `docs/ARCHITECTURE.md` — architecture, API and schema reference.
- `scripts/load_test.py` — authenticated API load simulation.

## Status

Milestone 1–5 foundation: architecture, schema, registration/authentication, event state machine, scoring/hints, leaderboard, validation, randomization and container contracts. Before production, implement and independently security-review the runtime adapter and run the event-day checks.

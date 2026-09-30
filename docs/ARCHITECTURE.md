# System architecture and API

```text
Players ─TLS─> reverse proxy ─> FastAPI control plane ─> PostgreSQL
                  │                    │
                  └─ terminal gateway ─┴─> scoped runtime worker ─> team containers
```

The reverse proxy serves the frontend and API. FastAPI owns authentication, competition state, score calculation, hints, validation and audit records. PostgreSQL is the source of truth. The terminal gateway is a separate service: it maps a short-lived, team-bound ticket to exactly one container session. The runtime worker has narrowly scoped container privileges; FastAPI does not.

## Data schema

`competition(id, phase, starts_at, paused_at, paused_seconds)` is the singleton synchronized event state. `teams(id, name, join_code_hash, seed, enabled, score, current_door, completed_at)` holds public state and the secret instance seed. `users(id, username, password_hash, role, team_id)` authorizes organizers and players. `door_completions(team_id, door, completed_at)` and `hint_uses(team_id, door, hint_number, used_at)` have uniqueness constraints for idempotency. `audit_logs(actor, action, team_id, created_at)` supports incident review.

## API contract

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/admin/bootstrap` | One-time organizer creation |
| POST | `/api/v1/auth/login` | JWT session |
| POST | `/api/v1/admin/teams` | Create team and seed |
| POST | `/api/v1/teams/join` | Player joins with team code |
| GET | `/api/v1/game/me` | Player-safe game state |
| GET | `/api/v1/game/doors/{door}` | Current/past door prompt only |
| POST | `/api/v1/game/doors/{door}/hint` | Next progressive hint |
| POST | `/api/v1/game/doors/{door}/validate` | Server-side answer check |
| GET | `/api/v1/leaderboard` | Public safe ranking |

Planned admin controls: state transition, team disable/reset, container restart, emergency hint and results export. Each requires ADMIN role and an audit event. WebSocket endpoints should publish only leaderboard/game-state deltas after authorization; do not broadcast terminal output.

## Challenge design

| Door | Skill | Evidence |
| --- | --- | --- |
| 1 | filesystem investigation | hidden clue found using `find` |
| 2 | hidden files / hex | one valid dotfile among decoys |
| 3 | hex → Base64 | two-stage decode |
| 4 | permissions | restore owner's read bit |
| 5 | forensic text search | production `NEXT` record among logs |
| 6 | timestamp forensics | today's PART-A/B/C records, ordered |

Each seed derives each door’s answer independently with HMAC-SHA256, so a reset reproduces the exact team instance while cross-team answers differ. Filenames and decoy content should use the same per-door RNG stream in the runtime generator.

## Scoring

Doors score 100, 125, 150, 175, 200 and 250 (1,000 total). A hint costs 25 points and 120 seconds by default. Rank by score, completed door count, then completion time. The values are deployment configuration, not browser constants.

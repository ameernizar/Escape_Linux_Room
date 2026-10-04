# Escape the Terminal

A self-hosted Linux escape room with six generated challenges, browser terminals,
an organizer dashboard, hints, scoring and pause-aware timing. FastAPI/PostgreSQL
hold competition state; a host-side Node gateway runs rootless Podman containers
for teams. Participants only need a modern browser.

This is not a frontend-only or single-container deployment. Read the
[release/security review](docs/OPEN_SOURCE_REVIEW.md) before publishing or exposing
it publicly. No external API key is needed for local operation.

## Requirements

- A dedicated Linux PC with systemd and cgroup v2. The current setup uses Linux
  Mint with an Ubuntu 24.04 base. Native Windows/macOS installation is not covered;
  use a Linux VM on those hosts.
- Docker Engine with Compose v2, rootless Podman, Python 3.10+, Git and Node.js 22.
- Each team shell is limited to 256 MiB RAM, 0.5 CPU and 128 processes. Thirty
  shells can consume 7.5 GiB before the OS/API/database; 16 GiB is a starting
  estimate, not a capacity guarantee. Rehearse with the actual team count.

Install Docker and Node using their official distribution instructions. On Mint,
use the Ubuntu base release for Docker's repository. If `docker-compose-plugin`
is unavailable, check the Docker apt repository rather than substituting Compose v1.

```sh
sudo apt update
sudo apt install git python3 python3-venv podman uidmap slirp4netns fuse-overlayfs
docker compose version
node --version
podman info
```

Run Podman as your normal account, **not with sudo**. Verify rootless/cgroup-v2
support and subordinate IDs in `/etc/subuid` and `/etc/subgid`. Docker group
membership grants root-equivalent host access; never grant it to players.

## Setup on a new PC

### 1. Clone and configure

Clone the published repository and enter its root. Commands below assume this
directory unless stated otherwise. Use a path without spaces for service setup.

```sh
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
openssl rand -hex 24
openssl rand -hex 24
```

Edit `.env`: put those three generated values into `SECRET_KEY`,
`ADMIN_BOOTSTRAP_PASSWORD` and `POSTGRES_PASSWORD`, respectively. Replace the
password in `DATABASE_URL` with the same `POSTGRES_PASSWORD`. Keep `db` as the
Compose database hostname. Hex values avoid URL-escaping/shell-quoting issues.

- The API and terminal worker must share the same `SECRET_KEY`; it signs tokens
  and authenticates private provisioning calls.
- `ADMIN_BOOTSTRAP_PASSWORD` becomes the first organizer's login password.
- Never put secrets in frontend source or `VITE_*` variables; browser code is public.
- Changing `.env` does not rotate an existing database user's password or an
  already-created organizer's password. Coordinate those changes separately.
- Container limits are currently fixed in `server-fixed.mjs`; the template's
  `CONTAINER_*` fields do not override them. Some optional config fields are
  placeholders, not implemented features.

### 2. Build the frontend and player image

```sh
npm --prefix frontend ci
npm --prefix terminal-gateway-rootless ci
npm --prefix frontend run build
podman build -t localhost/escape-player:locked player-image
mkdir -p terminal-gateway-rootless/run
```

Keep both npm lockfiles in Git. Dependencies and built frontend assets are ignored
and must be generated on each PC.

### 3. Start the terminal worker

In a separate terminal, from the repository root:

```sh
set -a
. ./.env
set +a
export PYTHONPATH="$PWD"
bash scripts/restore-team-containers.sh
node terminal-gateway-rootless/server-fixed.mjs
```

Only source an `.env` you created and trust: shell sourcing executes its contents.
Leave this terminal running. The worker creates its private provisioning socket
in `terminal-gateway-rootless/run/` and listens on loopback port 8080.

### 4. Start the API, database and website

In another terminal, from the repository root:

```sh
docker compose up -d --build
node scripts/serve-frontend.mjs
```

Leave the frontend process running. Open:

- Team login: `http://localhost:5173/join.html`
- Organizer: `http://localhost:5173/admin.html`
- API documentation on the host: `http://localhost:8000/docs`

The frontend server proxies API and WebSocket traffic. Port 5173 binds all host
interfaces; ports 8000/8080 bind loopback. Keep the host firewall enabled and never
publish PostgreSQL, the Docker daemon or the provisioning socket.

### 5. Create the organizer and teams

In the local API docs, open `POST /api/v1/admin/bootstrap` and select **Try it out**.
Use a username of at least 3 characters and the exact `ADMIN_BOOTSTRAP_PASSWORD`
from `.env` (at least 10 characters). Bootstrap only works before an organizer
exists. Treat the returned token as a secret.

Log into `/admin.html` with those credentials and create teams with unique join
codes. Check that shells are ready; **Prepare shell** retries failed provisioning.
Teams log in through `/join.html`. Logging in again obtains a fresh token; users
do not need to manually paste tokens into the UI.

During LIVE, the first two fullscreen/focus departures cost 25 points each
(score floor zero); the third eliminates the whole team. Player copy/paste is
blocked, while Ctrl+C still interrupts shell commands. These browser rules are
best-effort, not tamper-proof; websites cannot disable OS shortcuts. Team reset
clears progress, score and departure penalties. Rehearse with disposable teams.

## Automatic startup (optional)

`deploy/systemd/*.service` contains examples from the original PC, not portable
installers. Copy `escape-terminal.service` and `escape-frontend.service` into
`~/.config/systemd/user/` (create the directory if needed). Edit the copies:

- Replace `/home/ameer/Documents/Escape_Linux_Room` with your clone's absolute path.
- Replace the pinned Node executable with the output of `command -v node`.
- Adjust worker `PATH`, `PYTHONPATH`, and `EnvironmentFile` for your account.
- Use the same normal user that built the Podman image.

Stop the manually running frontend/worker with Ctrl+C, then run:

```sh
systemctl --user daemon-reload
systemctl --user enable --now escape-terminal.service escape-frontend.service
sudo loginctl enable-linger "$USER"
sudo systemctl enable --now docker
```

Compose services restart automatically once created. Do not enable the public
tunnel example until you intentionally configure public access.

## Access from other PCs

On a participant PC, `localhost` refers to that PC, not the host. Use the host's
LAN address with port 5173. Full functionality outside localhost requires HTTPS,
including the secure browser APIs used by departure reporting. Configure a
trusted TLS reverse proxy or tunnel; do not disable browser security checks.

For a fixed public address, use a named Cloudflare Tunnel with a domain you control,
routing only the app hostname to `http://127.0.0.1:5173`. Quick Tunnel addresses are
temporary. Keep tunnel credentials outside Git. Domain changes require the DNS
administrator's approval and a record backup. Keep the host awake and online;
complete the security hardening in the review before public use.

## Maintenance and troubleshooting

```sh
npm --prefix frontend run build
docker compose up -d --build api
systemctl --user restart escape-terminal.service escape-frontend.service
docker compose ps
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8080/health
journalctl --user -u escape-terminal -u escape-frontend -n 80
```

Without systemd, restart the manual processes instead. For disconnected terminals,
check matching secrets, the player image, `podman ps -a`, worker logs and the
private socket; retry **Prepare shell**. Do not switch to sudo Podman, which uses
different images and containers. Rebuild after frontend edits.

Back up the database before updates. Backups contain sensitive team seeds/hashes:

```sh
mkdir -p backups
chmod 700 backups
umask 077
docker compose exec -T db pg_dump -U escape -d escape -Fc > "backups/escape-$(date +%Y%m%d-%H%M%S).dump"
```

Verify the command succeeds and rehearse restore into a separate database. Do not
run `docker compose down -v` unless you intend to delete competition data.
Scores/times persist in PostgreSQL, but player files in `/escape` and `/tmp` are
RAM-backed and do not survive container shutdown. Empty challenge folders are
regenerated from database seeds. Pause before maintenance: downtime during LIVE
counts toward elapsed time.

## Tests

These tests use isolated fixtures. Never load-test against a real LIVE event.

```sh
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests/test_challenges.py tests/test_runtime_policy.py
docker compose build api
docker compose run --rm --no-deps -T -e DATABASE_URL=sqlite:///:memory: api python - < tests/test_rules.py
docker compose run --rm --no-deps -T -e DATABASE_URL=sqlite:///:memory: api python - < tests/test_timing.py
npm --prefix frontend run build
git diff --check
```

## Repository map

- `backend/` — API, state machine, scoring and database model.
- `challenges/` — deterministic per-team instance generator.
- `player-image/` — minimal non-root player shell image.
- `docs/ARCHITECTURE.md` — architecture, API and schema reference.
- `terminal-gateway-rootless/server-fixed.mjs` — active rootless worker/gateway.
- `scripts/serve-frontend.mjs` — built frontend and API/WebSocket proxy.
- `scripts/load_test.py` — authenticated API load simulation (not for live events).

## Release status

Other gateway folders and older deployment documents describe reference designs;
this README describes the active rootless setup. Do not use `docker-compose.dev.yml`
for events: it exposes the host Docker socket.

Follow [the release checklist](docs/OPEN_SOURCE_REVIEW.md) before publishing.
No license has been selected: add an appropriate license you have the rights to
grant. Making a repository public alone does not grant open-source reuse rights.

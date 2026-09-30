# Deployment guide

Run this on a dedicated, patched Linux server on the event LAN. Do not expose the API or Docker daemon to the public internet.

## Prerequisites

- Docker Engine/Compose, PostgreSQL backups, TLS reverse proxy, and a DNS/LAN name.
- At least 8 vCPU, 16 GB RAM and fast local SSD for the recommended 40-team headroom.
- A separate non-root runtime service account; the backend must not have `/var/run/docker.sock` mounted.

## Bring-up

1. Create a private Docker network for each player container (`--internal`), and an allow-listed terminal gateway network.
2. Build and pin the `player-image` digest. Scan it, then save it locally for offline event recovery.
3. Set `.env` secrets, start Compose, bootstrap one organizer, create teams, and generate their instances through a privileged *separate* runtime worker.
4. Place Caddy/Nginx in front of the API with TLS, request-size limits and rate limits. Permit only LAN CIDRs.
5. Load-test at 40 fake teams, rehearse reset and database restore, then freeze image digests/configuration.

The provided Compose service is control-plane only. A runtime adapter is intentionally not shipped because unsafe Docker socket access would violate the platform threat model.

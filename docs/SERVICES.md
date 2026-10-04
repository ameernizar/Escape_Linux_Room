# Services on this Linux Mint host

The frontend and rootless worker run as user services for ameer. User lingering is enabled, so a desktop login is not required. Docker is enabled at boot; the API and database use restart: unless-stopped.

- Player: http://localhost:5173/
- Organizer: http://localhost:5173/admin.html
- Team join: http://localhost:5173/join.html

## Status and logs

```sh
systemctl --user status escape-terminal escape-frontend
journalctl --user -u escape-terminal -u escape-frontend -n 80
docker compose ps
docker compose logs --tail 80 api
```

## Apply updates

```sh
cd /home/ameer/Documents/Escape_Linux_Room/frontend
npm run build
cd /home/ameer/Documents/Escape_Linux_Room
docker compose up -d --build api
systemctl --user restart escape-terminal escape-frontend
```

The frontend serves frontend/dist, not the Vite development server. Rebuild after UI edits. Service files in deploy/systemd are linked into the user service directory. Run systemctl --user daemon-reload after editing a unit. Their Node path is pinned to the installed Node v22.22.1; update ExecStart if that installation is removed.

## Recovery behavior

The worker starts existing escape-team containers. The API retries provisioning for enabled teams after startup, using the database seeds. Existing challenge files are preserved. Empty RAM-backed /escape folders are regenerated following container shutdown or reboot. Player edits and temporary files in these RAM-backed folders do not survive shutdown; scores and timing records remain in PostgreSQL. This is restart recovery, not persistence of player work.

A host outage during LIVE currently counts toward elapsed time. Pause the competition before planned maintenance. A full machine reboot has not yet been performed as part of verification.

Docker Compose down intentionally removes the API containers; run docker compose up -d to recreate them. It is not a substitute for stopping/restarting the host.

This setup is HTTP-only. HTTPS, network access controls, durable backups, and a full event rehearsal are separate deployment steps.

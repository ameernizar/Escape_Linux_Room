# Security model

Player terminal input is hostile. The browser never submits shell commands to the API; a terminal gateway routes an authenticated WebSocket only to that team’s container. The API validates submitted unlock keys server-side using a per-team HMAC-derived instance.

## Runtime policy

- One ephemeral container per team: non-root user, `read_only`, `cap_drop=ALL`, `no-new-privileges`, `pids-limit=128`, `--memory=256m`, `--cpus=.5`, writable tmpfs quotas.
- `--network=none` or an internal network with no gateway. No host mounts, devices, Docker socket, privileged mode, added capabilities, or host PID/user namespace.
- A narrowly scoped runtime worker is the sole component allowed to create/delete containers. It validates opaque team IDs against the database; it accepts no image, mount, command, or network values from users.
- Enforce WebSocket origin checks, short-lived signed terminal tickets tied to user/team, per-user command and connection rate limits, and gateway-side session termination.

## Application policy

- Store password hashes only; use strong production `SECRET_KEY`; issue short-lived JWTs over HTTPS.
- Authorize every object access by `team_id`; never return seeds, answers, container IDs, or audit details to players.
- Parameterize all database access, cap request sizes, rate-limit auth/validation, and audit organizer actions without recording answers/join codes.
- Keep PostgreSQL off the LAN, rotate credentials after the event, and destroy player volumes/containers once results are exported.

An independent security review of the runtime adapter and a rehearsal in the actual LAN topology are release gates.

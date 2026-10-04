# Scoped runtime worker

This service is intentionally separate from FastAPI. It is the only service permitted to access a Docker-compatible runtime. It accepts requests only over a local Unix socket from the terminal gateway.

Allowed operations are fixed: create a named team container from the pinned player image, start an exec shell for that team, inspect health, and destroy that team. Reject image names, mounts, commands, network settings and raw container IDs supplied by callers.

Create each team container with: a generated `escape-team-<numeric-id>` name, `network_mode=none`, `read_only=True`, `cap_drop=["ALL"]`, `security_opt=["no-new-privileges"]`, `user="player"`, 256 MB memory, 0.5 CPU, 128 PIDs, and bounded tmpfs. The worker must create the filesystem before opening player access.

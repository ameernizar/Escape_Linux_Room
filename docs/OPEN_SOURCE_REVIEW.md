# Open-source release review

Reviewed 2026-10-04. This is a targeted source/configuration review, not a
penetration test or certification that the application is secure.

## Release blockers

1. **Secrets were committed.** `.env` was tracked in two existing commits.
   Removing it from today's index and adding `.gitignore` does not erase history.
   Before publishing, rotate the JWT/worker signing key and organizer password,
   and replace the database's default password. Coordinate API and worker secrets;
   changing the bootstrap setting alone does not change an existing organizer's
   password hash. Rotation invalidates existing tokens and can interrupt play.
   None of these live credentials were rotated by this documentation update.
2. **Do not publish the current history as-is.** Either use a fresh public
   repository containing only the sanitized source snapshot, or deliberately
   purge sensitive files from every branch/tag using a reviewed history-cleanup
   procedure. Re-scan the resulting history. History rewriting/force pushes were
   not performed. If already shared, treat the secrets as exposed even after cleanup.
3. **Choose a license.** There is no root license file. The owner must select a
   license and verify rights to contributed code/assets before release.

## Changes made in this review

- Added a root `.gitignore` for environments, credentials, developer account
  folders, dependencies, generated assets, caches, runtime sockets and backups.
- Removed already-tracked ignored files from the Git index only; working copies
  remain on this PC. Lockfiles and `.env.example` remain publishable.
- Moved the Compose database password to `POSTGRES_PASSWORD` from `.env`; the
  template requires a generated password matching `DATABASE_URL`. The existing
  local password was preserved, not changed in PostgreSQL.
- Added a backend `.dockerignore` and rewrote the README for the active runtime.
- Compared tracked application files with current local secret values and checked
  common credential signatures, without logging the values. This is not an
  exhaustive API-key scan; old history and credentials of unrecognized formats
  still require a dedicated secret scanner before release.

## Remaining code/security findings

- `backend/app/config.py` still has weak fallback signing/bootstrap values.
  Operators must supply strong environment values; startup should eventually
  reject missing/placeholder secrets instead of silently accepting defaults.
- The active gateway lacks an explicit WebSocket Origin allowlist and robust
  per-user connection/rate limits. Authentication/answer endpoints also need
  abuse controls before unrestricted internet exposure. Requirements in
  `SECURITY.md` are not proof those protections are implemented.
- Login tokens are stored in browser localStorage, and terminal tickets travel in
  WebSocket query strings. Protect against XSS and redact query tokens from proxy
  logs. Keep HTTPS enabled; no server secrets belong in frontend bundles.
- The provisioning Unix socket is created with mode 0666 and relies on its shared
  secret for authorization. Use a dedicated host/service account; tighten socket
  group permissions as part of a coordinated container UID/GID deployment change.
- Rootless containers reduce risk but share the host kernel. Do not run hostile
  public workloads alongside personal files or sensitive services. Keep the host
  patched and independently review isolation.
- Fullscreen/clipboard/focus enforcement relies on client reports and can be
  bypassed. It is a competition aid, not a secure examination lockdown system.
- The systemd examples contain original machine paths. Follow the README's
  substitutions before enabling them on another PC. The active entrypoint is
  `server-fixed.mjs`; older gateway implementations are not equivalent.
- Some configuration fields are not wired to the active runtime. Container
  resources remain hard-coded; do not advertise `.env` fields as guaranteed controls.

These findings are documented, not silently presented as fixed. No public
deployment, database reset, secret rotation or unrelated application-code changes
were performed as part of this review.

## Publication checks

```sh
git check-ignore .env .aws/credentials frontend/node_modules/example frontend/dist/index.html
git ls-files .env
git ls-files -ci --exclude-standard
git diff --check
```

The two `git ls-files` checks should print nothing. Review staged removals with
`git diff --cached --stat` (avoid displaying historical `.env` contents). Check
that both npm lockfiles and `.env.example` remain tracked. Run the README tests,
scan dependencies/images, and run a dedicated secret scanner on the exact
snapshot/history that will be published. Ignore rules cannot undo past disclosure.

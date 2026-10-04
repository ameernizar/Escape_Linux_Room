# Terminal gateway

Deploy this as the only externally reachable WebSocket terminal service. It validates a one-minute JWT, derives the only permitted container name from the numeric team claim, and starts exactly one fixed non-root Bash command. It deliberately exposes no REST API, Docker identifiers, runtime options, or arbitrary exec command.

Production hardening still required: run this behind a reverse proxy with origin/rate/connection limits; mount a narrowly scoped runtime proxy rather than Docker's raw socket; deny TCP Docker access; and add one-time ticket storage in Redis/PostgreSQL before multi-user event use.

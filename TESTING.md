# Testing and load plan

Run unit tests for deterministic instance generation and scoring before every release. Exercise 5, 10, 20, 30 and 40 fake teams with joins, hint requests, incorrect/correct validation, leaderboard reads, reconnects and terminal WebSocket sessions.

Record p50/p95 API latency, RAM/CPU, PostgreSQL connections and container start time. Acceptance target: usable p95 API latency at 40 simulated teams and no cross-team authorization failures. Perform a separate container-escape and gateway authorization review; never run attack tests on the college network during the event.

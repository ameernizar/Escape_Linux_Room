# Organizer guide

Create teams and distribute each team’s join code privately. Use `PREPARING → READY → COUNTDOWN → LIVE → FINISHED`; the API must reject answers until LIVE. Pausing must freeze the server-side clock for all teams.

Reset procedure: disable the affected team, preserve its audit trail, destroy only its container and writable volume, regenerate the same instance from its stored seed, start a replacement container, then re-enable the team. Never change a seed mid-event.

## Event-day checklist

- Week before: load-test 40 teams, image scan, restore drill, challenge walkthrough.
- Day before: back up database/images/configuration; test every team reset.
- Hour before: verify database health, gateway authorization, timer, leaderboard, logging and LAN access.
- During: monitor containers/resources; issue only documented hints; record incidents.
- After: export results, back up audit data, destroy player environments and rotate secrets.

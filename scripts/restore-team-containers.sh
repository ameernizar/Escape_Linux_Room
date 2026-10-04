#!/usr/bin/env bash
set -euo pipefail
while IFS= read -r team_container; do
  if [[ "$team_container" =~ ^escape-team-[1-9][0-9]{0,5}$ ]]; then
    /usr/bin/podman start "$team_container"
  fi
done < <(/usr/bin/podman ps -a --format '{{.Names}}')

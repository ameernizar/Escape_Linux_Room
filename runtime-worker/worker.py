"""Reference policy layer for a separately deployed, Unix-socket-only runtime worker.

Do not expose this process on TCP. Its caller sends only validated integer team IDs.
"""
from dataclasses import dataclass
import re

TEAM_ID=re.compile(r"^[1-9][0-9]{0,5}$")
@dataclass(frozen=True)
class ContainerSpec:
    name: str; image: str="escape-player:locked"; memory: str="256m"; nano_cpus: int=500_000_000; pids_limit: int=128
def spec(team_id: str)->ContainerSpec:
    if not TEAM_ID.fullmatch(team_id): raise ValueError("invalid team id")
    return ContainerSpec(name=f"escape-team-{team_id}")
def create_arguments(team_id: str)->dict:
    s=spec(team_id)
    return {"name":s.name,"image":s.image,"network_mode":"none","read_only":True,"user":"player","mem_limit":s.memory,"nano_cpus":s.nano_cpus,"pids_limit":s.pids_limit,"cap_drop":["ALL"],"security_opt":["no-new-privileges:true"],"tmpfs":{"/tmp":"rw,noexec,nosuid,size=32m"},"volumes":{}}

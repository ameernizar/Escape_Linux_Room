from datetime import datetime, timezone

def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def elapsed(comp, now=None):
    if comp.starts_at is None: return 0.0
    end=comp.ended_at or comp.paused_at or now or datetime.now(timezone.utc)
    paused=comp.paused_duration if comp.paused_duration is not None else (comp.paused_seconds or 0)
    return round(max(0.0,(utc(end)-utc(comp.starts_at)).total_seconds()-paused),3)

def team_elapsed(team,comp,now=None):
    # Historical completions without a saved timing snapshot remain unknown.
    return team.elapsed_seconds if team.completed_at is not None or team.eliminated_at is not None else elapsed(comp,now)

def rank_teams(teams):
    def key(team):
        return (-team.score,team.elapsed_seconds if team.completed_at and team.elapsed_seconds is not None else float("inf"))
    ordered=sorted(teams,key=lambda team:(key(team),team.id))
    ranks={};previous=None;rank=0
    for position,team in enumerate(ordered,1):
        if key(team)!=previous: rank=position
        ranks[team.id]=rank
        previous=key(team)
    return ordered,ranks

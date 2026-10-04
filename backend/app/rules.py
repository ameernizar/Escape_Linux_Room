"""Persisted per-team rule enforcement with idempotent browser reports."""
from datetime import datetime, timezone
from sqlalchemy import select
from fastapi import HTTPException
from .models import Team, Competition, Phase, RuleEvent, AuditLog
from .timing import elapsed
EXIT_LIMIT=3
EXIT_PENALTY=25

def playing_team(db,user,lock=False):
    query=select(Team).where(Team.id==user.team_id)
    if lock: query=query.with_for_update()
    team=db.scalar(query)
    if not team or not team.enabled: raise HTTPException(403,"Team unavailable")
    if team.eliminated_at is not None: raise HTTPException(403,"Your team was eliminated after three departures.")
    return team

def policy_state(team):
    return {"exit_count":team.exit_count or 0,"exit_limit":EXIT_LIMIT,"exit_penalty_points":EXIT_PENALTY,"eliminated":team.eliminated_at is not None,"score":team.score}

def record_departure(db,user,event_id,reason):
    comp=db.scalar(select(Competition).where(Competition.id==1).with_for_update())
    team=db.scalar(select(Team).where(Team.id==user.team_id).with_for_update())
    if not team: raise HTTPException(403,"No team")
    previous=db.scalar(select(RuleEvent).where(RuleEvent.team_id==team.id,RuleEvent.event_id==str(event_id)))
    if previous: return {**policy_state(team),"counted":False,"duplicate":True}
    counted=comp.phase==Phase.LIVE and team.enabled and not team.completed_at and team.eliminated_at is None
    deduction=0
    if counted:
        team.exit_count=(team.exit_count or 0)+1
        if team.exit_count>=EXIT_LIMIT:
            team.eliminated_at=datetime.now(timezone.utc)
            team.elapsed_seconds=elapsed(comp,team.eliminated_at)
        else:
            deduction=min(EXIT_PENALTY,team.score)
            team.score-=deduction
        db.add(AuditLog(actor=user.username,action="rules.eliminated" if team.eliminated_at else "rules.exit",team_id=team.id))
    db.add(RuleEvent(team_id=team.id,event_id=str(event_id),reason=reason,counted=counted,penalty_points=deduction))
    db.commit()
    return {**policy_state(team),"counted":counted,"deducted_points":deduction}

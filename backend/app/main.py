from datetime import datetime, timedelta, timezone
import asyncio
import logging
import hashlib, secrets
from typing import Literal
from uuid import UUID
import jwt
from fastapi import Depends, FastAPI, HTTPException, WebSocket, status, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from .rules import playing_team, policy_state, record_departure
from .timing import elapsed, team_elapsed, rank_teams, utc
from .migrations import migrate_timing
from .provisioning import prepare_shell
from .challenges import instance
from .config import settings
from .database import Base, db_session, engine
from .models import AuditLog, Competition, DoorCompletion, HintUse, Phase, Role, Team, User, RuleEvent

app=FastAPI(title="Escape the Terminal API", version="0.1.0")
passwords=CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto"); bearer=HTTPBearer()
POINTS={1:100,2:125,3:150,4:175,5:200,6:250}
class Credentials(BaseModel): username:str=Field(min_length=3,max_length=80); password:str=Field(min_length=10,max_length=128)
class TeamCreate(BaseModel): name:str=Field(min_length=3,max_length=80); join_code:str=Field(min_length=8,max_length=128)
class Answer(BaseModel): answer:str=Field(min_length=1,max_length=128)
class PhaseChange(BaseModel): phase: Phase
class TeamEnabled(BaseModel): enabled: bool
class Departure(BaseModel):
    event_id: UUID
    reason: Literal["fullscreen_exit","window_blur","page_hidden","page_unload"]

@app.on_event("startup")
async def init():
    Base.metadata.create_all(engine)
    migrate_timing(engine)
    with next(db_session()) as db:
        if not db.get(Competition,1): db.add(Competition(id=1)); db.commit()
    app.state.shell_recovery=asyncio.create_task(recover_shells())

async def recover_shells():
    with next(db_session()) as db:
        pending=[(team.id,team.seed) for team in db.scalars(select(Team).where(Team.enabled==True)).all()]
    while pending:
        failed=[]
        for team_id,seed in pending:
            try: await asyncio.to_thread(prepare_shell,team_id,seed)
            except RuntimeError:
                logging.getLogger(__name__).warning("Shell recovery pending for team %s",team_id)
                failed.append((team_id,seed))
        pending=failed
        if pending: await asyncio.sleep(15)

@app.on_event("shutdown")
async def stop_recovery():
    task=getattr(app.state,"shell_recovery",None)
    if task:
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

def token(user:User): return jwt.encode({"sub":str(user.id),"role":user.role.value,"exp":datetime.now(timezone.utc)+timedelta(hours=8)},settings.secret_key,algorithm="HS256")
def current(c:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(db_session)):
    try: data=jwt.decode(c.credentials,settings.secret_key,algorithms=["HS256"]); user=db.get(User,int(data["sub"]))
    except Exception: raise HTTPException(401,"Invalid or expired session")
    if not user: raise HTTPException(401,"Unknown user")
    return user
def admin(user:User=Depends(current)):
    if user.role!=Role.ADMIN: raise HTTPException(403,"Organizer access required")
    return user
def audit(db,actor,action,team_id=None): db.add(AuditLog(actor=actor,action=action,team_id=team_id))

@app.get("/health")
def health(): return {"status":"ok"}
@app.post("/api/v1/admin/bootstrap")
def bootstrap(body:Credentials,db:Session=Depends(db_session)):
    if db.scalar(select(User).where(User.role==Role.ADMIN)): raise HTTPException(409,"Admin already exists")
    if body.password!=settings.admin_bootstrap_password: raise HTTPException(403,"Bootstrap password rejected")
    user=User(username=body.username,password_hash=passwords.hash(body.password),role=Role.ADMIN); db.add(user); db.commit(); return {"access_token":token(user)}
@app.post("/api/v1/auth/login")
def login(body:Credentials,db:Session=Depends(db_session)):
    user=db.scalar(select(User).where(User.username==body.username))
    if not user or not passwords.verify(body.password,user.password_hash): raise HTTPException(401,"Invalid credentials")
    return {"access_token":token(user),"token_type":"bearer"}
@app.post("/api/v1/admin/teams",status_code=201)
def create_team(body:TeamCreate,actor:User=Depends(admin),db:Session=Depends(db_session)):
    if db.scalar(select(Team).where(Team.name==body.name)): raise HTTPException(409,"Team name exists")
    if len(db.scalars(select(Team)).all())>=settings.max_teams: raise HTTPException(409,"Team capacity reached")
    team=Team(name=body.name,join_code_hash=passwords.hash(body.join_code),seed=secrets.token_hex(32)); db.add(team); audit(db,actor.username,"team.created"); db.commit()
    try:
        prepare_shell(team.id, team.seed)
        return {"id":team.id,"name":team.name,"shell_status":"ready"}
    except RuntimeError as error:
        return {"id":team.id,"name":team.name,"shell_status":"unavailable","detail":str(error)}

@app.post("/api/v1/admin/teams/{team_id}/provision")
def provision_team(team_id:int,actor:User=Depends(admin),db:Session=Depends(db_session)):
    team=db.get(Team,team_id)
    if not team: raise HTTPException(404,"Team not found")
    try: prepare_shell(team.id,team.seed)
    except RuntimeError as error: raise HTTPException(503,str(error))
    audit(db,actor.username,"team.shell.ready",team.id); db.commit()
    return {"id":team.id,"shell_status":"ready"}

PHASE_TRANSITIONS={Phase.PREPARING:{Phase.READY},Phase.READY:{Phase.COUNTDOWN,Phase.PREPARING},Phase.COUNTDOWN:{Phase.LIVE,Phase.READY},Phase.LIVE:{Phase.PAUSED,Phase.FINISHED},Phase.PAUSED:{Phase.LIVE,Phase.FINISHED},Phase.FINISHED:set()}

@app.get("/api/v1/admin/competition")
def competition_status(_:User=Depends(admin),db:Session=Depends(db_session)):
    comp=db.get(Competition,1)
    return {"phase":comp.phase,"elapsed_seconds":elapsed(comp),"starts_at":comp.starts_at,"ended_at":comp.ended_at,"allowed_phases":sorted(p.value for p in PHASE_TRANSITIONS[comp.phase])}

@app.post("/api/v1/admin/competition/phase")
def change_phase(body:PhaseChange,actor:User=Depends(admin),db:Session=Depends(db_session)):
    comp=db.scalar(select(Competition).where(Competition.id==1).with_for_update())
    if body.phase not in PHASE_TRANSITIONS[comp.phase]:
        raise HTTPException(409,"Invalid phase transition. Finished results are preserved; a new event requires a separate competition.")
    now=datetime.now(timezone.utc)
    if body.phase==Phase.LIVE and comp.starts_at is None:
        comp.starts_at=now; comp.paused_duration=0; comp.paused_seconds=0
    if comp.phase==Phase.PAUSED and comp.paused_at:
        comp.paused_duration=(comp.paused_duration if comp.paused_duration is not None else comp.paused_seconds)+(now-utc(comp.paused_at)).total_seconds()
        comp.paused_seconds=int(comp.paused_duration)
        comp.paused_at=None
    if body.phase==Phase.PAUSED: comp.paused_at=now
    if body.phase==Phase.FINISHED: comp.ended_at=now
    comp.phase=body.phase
    audit(db,actor.username,"competition.phase."+body.phase.value); db.commit()
    return competition_status(actor,db)

@app.get("/api/v1/admin/teams")
def admin_teams(_:User=Depends(admin),db:Session=Depends(db_session)):
    comp=db.get(Competition,1)
    teams=db.scalars(select(Team).order_by(Team.id)).all()
    _,ranks=rank_teams([team for team in teams if team.enabled and team.eliminated_at is None])
    splits={}
    for row in db.scalars(select(DoorCompletion).order_by(DoorCompletion.door)).all():
        splits.setdefault(row.team_id,[]).append({"door":row.door,"elapsed_seconds":row.elapsed_seconds})
    now=datetime.now(timezone.utc)
    return [{"id":t.id,"name":t.name,"enabled":t.enabled,"score":t.score,"current_door":t.current_door,"completed_at":t.completed_at,"elapsed_seconds":team_elapsed(t,comp,now),"rank":ranks.get(t.id),"door_times":splits.get(t.id,[]),**policy_state(t)} for t in teams]
@app.post("/api/v1/admin/teams/{team_id}/enabled")
def set_team_enabled(team_id:int,body:TeamEnabled,actor:User=Depends(admin),db:Session=Depends(db_session)):
    team=db.get(Team,team_id)
    if not team: raise HTTPException(404,"Team not found")
    if body.enabled and team.eliminated_at is not None: raise HTTPException(409,"Eliminated teams require an organizer progress reset before re-enabling.")
    team.enabled=body.enabled; audit(db,actor.username,"team.enabled" if body.enabled else "team.disabled",team.id); db.commit()
    return {"id":team.id,"enabled":team.enabled}
@app.post("/api/v1/admin/teams/{team_id}/reset")
def reset_team(team_id:int,actor:User=Depends(admin),db:Session=Depends(db_session)):
    """Resets persisted game state. Runtime destruction/rebuild is a worker operation, not an API shell call."""
    team=db.get(Team,team_id)
    if not team: raise HTTPException(404,"Team not found")
    db.execute(delete(DoorCompletion).where(DoorCompletion.team_id==team.id)); db.execute(delete(HintUse).where(HintUse.team_id==team.id))
    db.execute(delete(RuleEvent).where(RuleEvent.team_id==team.id))
    team.exit_count=0; team.eliminated_at=None
    team.score=0; team.current_door=1; team.completed_at=None; team.elapsed_seconds=None; audit(db,actor.username,"team.reset",team.id); db.commit()
    return {"id":team.id,"reset":True,"seed_is_preserved":True}
@app.post("/api/v1/teams/join")
def join_team(body:TeamCreate,db:Session=Depends(db_session)):
    team=db.scalar(select(Team).where(Team.name==body.name))
    if not team or not passwords.verify(body.join_code,team.join_code_hash): raise HTTPException(401,"Invalid team or join code")
    if not team.enabled or team.eliminated_at is not None: raise HTTPException(403,"Team disabled or eliminated. Contact your organizer.")
    username=f"{team.id}-{secrets.token_urlsafe(5)}"; user=User(username=username,password_hash=passwords.hash(secrets.token_urlsafe(24)),team_id=team.id); db.add(user); audit(db,username,"player.joined",team.id); db.commit(); return {"access_token":token(user),"team":team.name}
@app.get("/api/v1/game/me")
def me(user:User=Depends(current),db:Session=Depends(db_session)):
    if not user.team_id: raise HTTPException(400,"No team")
    team=db.get(Team,user.team_id); comp=db.get(Competition,1)
    return {"team":team.name,"score":team.score,"current_door":team.current_door,"phase":comp.phase,"duration_minutes":settings.game_duration_minutes,"elapsed_seconds":team_elapsed(team,comp),"timer_running":comp.phase==Phase.LIVE and team.completed_at is None and team.eliminated_at is None,**policy_state(team)}
@app.post("/api/v1/game/departures")
def departure(body:Departure,user:User=Depends(current),db:Session=Depends(db_session)):
    return record_departure(db,user,body.event_id,body.reason)

@app.get("/api/v1/internal/terminal-access")
def terminal_access(x_worker_key:str=Header(default=""),db:Session=Depends(db_session)):
    if not secrets.compare_digest(x_worker_key.encode(),settings.secret_key.encode()):
        raise HTTPException(403,"Worker authentication required")
    return {"allowed_teams":list(db.scalars(select(Team.id).where(Team.enabled==True,Team.eliminated_at.is_(None))).all())}

@app.post("/api/v1/terminal/ticket")
def terminal_ticket(user:User=Depends(current),db:Session=Depends(db_session)):
    """Short lived, team-bound credential consumed by the terminal gateway only."""
    playing_team(db,user)
    claims={"sub":str(user.id),"team":user.team_id,"scope":"terminal","jti":secrets.token_urlsafe(16),"exp":datetime.now(timezone.utc)+timedelta(minutes=1)}
    return {"ticket":jwt.encode(claims,settings.secret_key,algorithm="HS256"),"expires_in":60}
@app.websocket("/ws/terminal")
async def terminal_unconfigured(ws:WebSocket, ticket:str):
    """Fail closed until the separately deployed terminal gateway takes this route."""
    try:
        claims=jwt.decode(ticket,settings.secret_key,algorithms=["HS256"])
        if claims.get("scope")!="terminal": raise ValueError("wrong scope")
    except Exception:
        await ws.close(code=4401); return
    await ws.accept()
    await ws.send_text("\r\nTerminal gateway is not configured on this server.\r\n")
    await ws.close(code=1011)
@app.get("/api/v1/game/doors/{door}")
def door(door:int,user:User=Depends(current),db:Session=Depends(db_session)):
    if not user.team_id or not 1<=door<=6: raise HTTPException(404,"Door not found")
    team=playing_team(db,user)
    if door>team.current_door: raise HTTPException(403,"Door is locked")
    game=instance(team.seed,door); return {"door":door,"prompt":game.prompt,"unlocked":door==team.current_door}
@app.post("/api/v1/game/doors/{door}/hint")
def hint(door:int,user:User=Depends(current),db:Session=Depends(db_session)):
    team=playing_team(db,user,lock=True); used=len(db.scalars(select(HintUse).where(HintUse.team_id==team.id,HintUse.door==door)).all())
    if door!=team.current_door or used>=3: raise HTTPException(409,"Hint unavailable")
    game=instance(team.seed,door); db.add(HintUse(team_id=team.id,door=door,hint_number=used+1)); team.score=max(0,team.score-settings.hint_penalty_points); audit(db,user.username,"hint.used",team.id); db.commit(); return {"hint_number":used+1,"text":game.hints[used],"penalty_points":settings.hint_penalty_points}
@app.post("/api/v1/game/doors/{door}/validate")
def validate(door:int,body:Answer,user:User=Depends(current),db:Session=Depends(db_session)):
    comp=db.scalar(select(Competition).where(Competition.id==1).with_for_update())
    team=db.scalar(select(Team).where(Team.id==user.team_id).with_for_update())
    if not team or not team.enabled or team.eliminated_at is not None: raise HTTPException(403,"Team disabled or eliminated")
    if comp.phase!=Phase.LIVE: raise HTTPException(409,"Competition is not live")
    if door!=team.current_door: raise HTTPException(409,"Door is not active")
    expected=instance(team.seed,door).expected_answer
    if not secrets.compare_digest(body.answer.strip().upper(),expected): audit(db,user.username,"validation.failed",team.id); db.commit(); raise HTTPException(422,"That key does not unlock this door")
    now=datetime.now(timezone.utc)
    duration=elapsed(comp,now)
    db.add(DoorCompletion(team_id=team.id,door=door,completed_at=now,elapsed_seconds=duration)); team.score+=POINTS[door]; team.current_door=min(7,door+1)
    if door==6: team.completed_at=now; team.elapsed_seconds=duration
    audit(db,user.username,"door.completed",team.id); db.commit(); return {"accepted":True,"score":team.score,"next_door":team.current_door}
@app.get("/api/v1/leaderboard")
def leaderboard(db:Session=Depends(db_session)):
    if not settings.leaderboard_enabled: raise HTTPException(404,"Leaderboard disabled")
    comp=db.get(Competition,1)
    teams,ranks=rank_teams(db.scalars(select(Team).where(Team.enabled==True,Team.eliminated_at.is_(None))).all())
    now=datetime.now(timezone.utc)
    return [{"rank":ranks[t.id],"team":t.name,"score":t.score,"current_door":t.current_door,"status":"FINISHED" if t.completed_at else "ACTIVE","elapsed_seconds":team_elapsed(t,comp,now)} for t in teams]
@app.websocket("/ws/leaderboard")
async def leaderboard_stream(ws:WebSocket):
    """Public, answer-free leaderboard deltas; terminal output is never broadcast."""
    await ws.accept()
    try:
        while True:
            db=next(db_session())
            try:
                await ws.send_json(leaderboard(db))
            finally: db.close()
            await asyncio.sleep(2)
    except Exception: await ws.close()

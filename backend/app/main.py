from datetime import datetime, timedelta, timezone
import hashlib, secrets
import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from .challenges import instance
from .config import settings
from .database import Base, db_session, engine
from .models import AuditLog, Competition, DoorCompletion, HintUse, Phase, Role, Team, User

app=FastAPI(title="Escape the Terminal API", version="0.1.0")
passwords=CryptContext(schemes=["bcrypt"], deprecated="auto"); bearer=HTTPBearer()
POINTS={1:100,2:125,3:150,4:175,5:200,6:250}
class Credentials(BaseModel): username:str=Field(min_length=3,max_length=80); password:str=Field(min_length=10,max_length=128)
class TeamCreate(BaseModel): name:str=Field(min_length=3,max_length=80); join_code:str=Field(min_length=8,max_length=128)
class Answer(BaseModel): answer:str=Field(min_length=1,max_length=128)
class PhaseChange(BaseModel): phase: Phase

@app.on_event("startup")
def init():
    Base.metadata.create_all(engine)
    with next(db_session()) as db:
        if not db.get(Competition,1): db.add(Competition(id=1)); db.commit()
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
    team=Team(name=body.name,join_code_hash=passwords.hash(body.join_code),seed=secrets.token_hex(32)); db.add(team); audit(db,actor.username,"team.created"); db.commit(); return {"id":team.id,"name":team.name}
@app.post("/api/v1/admin/competition/phase")
def change_phase(body:PhaseChange,actor:User=Depends(admin),db:Session=Depends(db_session)):
    comp=db.get(Competition,1)
    allowed={Phase.PREPARING:{Phase.READY},Phase.READY:{Phase.COUNTDOWN,Phase.PREPARING},Phase.COUNTDOWN:{Phase.LIVE,Phase.READY},Phase.LIVE:{Phase.PAUSED,Phase.FINISHED},Phase.PAUSED:{Phase.LIVE,Phase.FINISHED},Phase.FINISHED:{Phase.PREPARING}}
    if body.phase not in allowed[comp.phase]: raise HTTPException(409,f"Cannot move from {comp.phase} to {body.phase}")
    now=datetime.now(timezone.utc)
    if body.phase==Phase.LIVE and comp.starts_at is None: comp.starts_at=now
    if body.phase==Phase.PAUSED: comp.paused_at=now
    if comp.phase==Phase.PAUSED and body.phase==Phase.LIVE and comp.paused_at:
        comp.paused_seconds+=int((now-comp.paused_at).total_seconds()); comp.paused_at=None
    comp.phase=body.phase; audit(db,actor.username,f"competition.phase.{body.phase.value}"); db.commit()
    return {"phase":comp.phase,"starts_at":comp.starts_at}
@app.post("/api/v1/teams/join")
def join_team(body:TeamCreate,db:Session=Depends(db_session)):
    team=db.scalar(select(Team).where(Team.name==body.name))
    if not team or not passwords.verify(body.join_code,team.join_code_hash): raise HTTPException(401,"Invalid team or join code")
    username=f"{team.id}-{secrets.token_urlsafe(5)}"; user=User(username=username,password_hash=passwords.hash(secrets.token_urlsafe(24)),team_id=team.id); db.add(user); audit(db,username,"player.joined",team.id); db.commit(); return {"access_token":token(user),"team":team.name}
@app.get("/api/v1/game/me")
def me(user:User=Depends(current),db:Session=Depends(db_session)):
    if not user.team_id: raise HTTPException(400,"No team")
    team=db.get(Team,user.team_id); comp=db.get(Competition,1)
    return {"team":team.name,"score":team.score,"current_door":team.current_door,"phase":comp.phase,"duration_minutes":settings.game_duration_minutes}
@app.get("/api/v1/game/doors/{door}")
def door(door:int,user:User=Depends(current),db:Session=Depends(db_session)):
    if not user.team_id or not 1<=door<=6: raise HTTPException(404,"Door not found")
    team=db.get(Team,user.team_id)
    if door>team.current_door: raise HTTPException(403,"Door is locked")
    game=instance(team.seed,door); return {"door":door,"prompt":game.prompt,"unlocked":door==team.current_door}
@app.post("/api/v1/game/doors/{door}/hint")
def hint(door:int,user:User=Depends(current),db:Session=Depends(db_session)):
    team=db.get(Team,user.team_id); used=len(db.scalars(select(HintUse).where(HintUse.team_id==team.id,HintUse.door==door)).all())
    if door!=team.current_door or used>=3: raise HTTPException(409,"Hint unavailable")
    game=instance(team.seed,door); db.add(HintUse(team_id=team.id,door=door,hint_number=used+1)); team.score=max(0,team.score-settings.hint_penalty_points); audit(db,user.username,"hint.used",team.id); db.commit(); return {"hint_number":used+1,"text":game.hints[used],"penalty_points":settings.hint_penalty_points}
@app.post("/api/v1/game/doors/{door}/validate")
def validate(door:int,body:Answer,user:User=Depends(current),db:Session=Depends(db_session)):
    team=db.get(Team,user.team_id); comp=db.get(Competition,1)
    if comp.phase!=Phase.LIVE: raise HTTPException(409,"Competition is not live")
    if door!=team.current_door: raise HTTPException(409,"Door is not active")
    expected=instance(team.seed,door).expected_answer
    if not secrets.compare_digest(body.answer.strip().upper(),expected): audit(db,user.username,"validation.failed",team.id); db.commit(); raise HTTPException(422,"That key does not unlock this door")
    db.add(DoorCompletion(team_id=team.id,door=door)); team.score+=POINTS[door]; team.current_door=min(7,door+1)
    if door==6: team.completed_at=datetime.now(timezone.utc)
    audit(db,user.username,"door.completed",team.id); db.commit(); return {"accepted":True,"score":team.score,"next_door":team.current_door}
@app.get("/api/v1/leaderboard")
def leaderboard(db:Session=Depends(db_session)):
    if not settings.leaderboard_enabled: raise HTTPException(404,"Leaderboard disabled")
    teams=db.scalars(select(Team).where(Team.enabled==True).order_by(Team.score.desc(),Team.current_door.desc(),Team.completed_at.asc())).all()
    return [{"rank":i,"team":t.name,"score":t.score,"current_door":t.current_door,"status":"FINISHED" if t.completed_at else "ACTIVE"} for i,t in enumerate(teams,1)]

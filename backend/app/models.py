import enum
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class Phase(str, enum.Enum): PREPARING="PREPARING"; READY="READY"; COUNTDOWN="COUNTDOWN"; LIVE="LIVE"; PAUSED="PAUSED"; FINISHED="FINISHED"
class Role(str, enum.Enum): PLAYER="PLAYER"; ADMIN="ADMIN"

class Competition(Base):
    __tablename__="competition"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    phase: Mapped[Phase] = mapped_column(Enum(Phase), default=Phase.PREPARING)
    starts_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_seconds: Mapped[int] = mapped_column(Integer, default=0)

    ended_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_duration: Mapped[float|None] = mapped_column(Float, nullable=True)

class Team(Base):
    __tablename__="teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    join_code_hash: Mapped[str] = mapped_column(String(255))
    seed: Mapped[str] = mapped_column(String(64), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    exit_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    eliminated_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    current_door: Mapped[int] = mapped_column(Integer, default=1)
    completed_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    elapsed_seconds: Mapped[float|None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class User(Base):
    __tablename__="users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.PLAYER)
    team_id: Mapped[int|None] = mapped_column(ForeignKey("teams.id"), nullable=True)

class DoorCompletion(Base):
    __tablename__="door_completions"; __table_args__=(UniqueConstraint("team_id","door"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    door: Mapped[int] = mapped_column(Integer)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    elapsed_seconds: Mapped[float|None] = mapped_column(Float, nullable=True)

class HintUse(Base):
    __tablename__="hint_uses"; __table_args__=(UniqueConstraint("team_id","door","hint_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id")); door: Mapped[int] = mapped_column(Integer); hint_number: Mapped[int] = mapped_column(Integer)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class AuditLog(Base):
    __tablename__="audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True); actor: Mapped[str] = mapped_column(String(80)); action: Mapped[str] = mapped_column(String(100)); team_id: Mapped[int|None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class RuleEvent(Base):
    __tablename__="rule_events"
    __table_args__=(UniqueConstraint("team_id","event_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    event_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str] = mapped_column(String(40))
    counted: Mapped[bool] = mapped_column(Boolean)
    penalty_points: Mapped[int] = mapped_column(Integer,default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=datetime.utcnow)

"""Run with: docker compose exec -T api python - < tests/test_timing.py"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from app.database import Base
from app.models import Competition, Team, User, Role, Phase, DoorCompletion
from app.timing import elapsed, team_elapsed, rank_teams
from app.migrations import migrate_timing
from app import main

class Clock(datetime):
    instant=datetime(2026,1,1,tzinfo=timezone.utc)
    @classmethod
    def now(cls,tz=None): return cls.instant

class TimingTests(unittest.TestCase):
    def test_pause_resume_finish_and_frozen_team_time(self):
        engine=create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        with Session(engine) as db, patch.object(main,"datetime",Clock):
            comp=Competition(id=1,phase=Phase.COUNTDOWN)
            team=Team(id=1,name="Test",join_code_hash="unused",seed="1"*64,current_door=6)
            db.add_all([comp,team]);db.commit()
            admin=User(username="organizer",role=Role.ADMIN)
            player=User(username="player",team_id=1)
            def phase(value,seconds):
                Clock.instant=start+timedelta(seconds=seconds)
                return main.change_phase(main.PhaseChange(phase=value),admin,db)
            phase(Phase.LIVE,0)
            self.assertEqual(elapsed(comp,start+timedelta(seconds=5)),5)
            phase(Phase.PAUSED,10.25)
            self.assertEqual(elapsed(comp,start+timedelta(seconds=19)),10.25)
            phase(Phase.LIVE,20.75)
            Clock.instant=start+timedelta(seconds=30.5)
            answer=main.instance(team.seed,6).expected_answer
            main.validate(6,main.Answer(answer=answer),player,db)
            self.assertEqual(team.elapsed_seconds,20)
            self.assertEqual(db.scalar(select(DoorCompletion)).elapsed_seconds,20)
            phase(Phase.PAUSED,31.5)
            phase(Phase.FINISHED,100)
            self.assertEqual(elapsed(comp,start+timedelta(seconds=500)),21)
            self.assertEqual(team_elapsed(team,comp,start+timedelta(seconds=500)),20)
            self.assertEqual(comp.paused_duration,79)
            with self.assertRaises(main.HTTPException):
                phase(Phase.PREPARING,110)

    def test_prestart_naive_utc_and_legacy_unknown(self):
        comp=Competition(paused_seconds=0)
        self.assertEqual(elapsed(comp),0)
        comp.starts_at=datetime(2026,1,1)
        comp.paused_at=datetime(2026,1,1,0,0,20)
        comp.paused_duration=5.125
        self.assertEqual(elapsed(comp),14.875)
        team=Team(completed_at=datetime(2026,1,1),elapsed_seconds=None)
        self.assertIsNone(team_elapsed(team,comp))

    def test_rank_score_then_finish_time_with_shared_ties(self):
        now=datetime.now(timezone.utc)
        teams=[Team(id=1,score=100,completed_at=now,elapsed_seconds=30),
               Team(id=2,score=100,completed_at=now,elapsed_seconds=20),
               Team(id=3,score=200,completed_at=None),
               Team(id=4,score=100,completed_at=now,elapsed_seconds=20),
               Team(id=5,score=100,completed_at=None)]
        ordered,ranks=rank_teams(teams)
        self.assertEqual([team.id for team in ordered],[3,2,4,1,5])
        self.assertEqual(ranks,{3:1,2:2,4:2,1:4,5:5})

    def test_additive_migration_is_repeatable(self):
        engine=create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE competition(id INTEGER PRIMARY KEY, phase TEXT, paused_seconds INTEGER)"))
            connection.execute(text("CREATE TABLE teams(id INTEGER PRIMARY KEY, name TEXT)"))
            connection.execute(text("CREATE TABLE door_completions(id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE audit_logs(action TEXT, created_at DATETIME)"))
            connection.execute(text("INSERT INTO competition VALUES (1,'LIVE',17)"))
            connection.execute(text("INSERT INTO teams VALUES (1,'Keep this team')"))
        migrate_timing(engine);migrate_timing(engine)
        with engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT paused_duration FROM competition")).scalar(),17)
            self.assertEqual(connection.execute(text("SELECT name FROM teams")).scalar(),"Keep this team")
            self.assertIsNone(connection.execute(text("SELECT elapsed_seconds FROM teams")).scalar())

if __name__=="__main__": unittest.main()

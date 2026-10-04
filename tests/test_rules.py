import unittest
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.database import Base
from app.models import Competition,Team,User,Role,Phase,RuleEvent
from app.rules import record_departure
from app import main

class RuleTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db=Session(self.engine)
        self.comp=Competition(id=1,phase=Phase.LIVE,starts_at=datetime.now(timezone.utc))
        self.team=Team(id=1,name="Rules fixture",seed="1"*64,join_code_hash=main.passwords.hash("test-join-code"),score=100)
        self.db.add_all([self.comp,self.team]);self.db.commit()
        self.player=User(username="fixture-player",team_id=1)
        self.admin=User(username="fixture-admin",role=Role.ADMIN)
    def tearDown(self):
        self.db.close();self.engine.dispose()
    def report(self,event=None):
        return record_departure(self.db,self.player,event or uuid4(),"fullscreen_exit")
    def test_two_penalties_then_team_elimination(self):
        self.assertEqual(self.report()["score"],75)
        self.assertEqual(self.report()["score"],50)
        state=self.report()
        self.assertTrue(state["eliminated"])
        self.assertEqual(state["exit_count"],3)
        self.assertEqual(state["score"],50)
        self.assertEqual(self.report()["exit_count"],3)
        self.db.expire_all()
        self.assertTrue(main.me(self.player,self.db)["eliminated"])
        self.assertFalse(main.me(self.player,self.db)["timer_running"])
        self.assertEqual(main.leaderboard(self.db),[])
    def test_duplicate_report_is_idempotent(self):
        event=uuid4()
        self.report(event)
        result=record_departure(self.db,self.player,event,"window_blur")
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["score"],75)
        self.assertEqual(result["exit_count"],1)
        self.assertEqual(len(self.db.scalars(select(RuleEvent)).all()),1)
    def test_no_penalties_outside_live_or_after_completion(self):
        self.comp.phase=Phase.PAUSED;self.db.commit()
        event=uuid4()
        self.assertFalse(self.report(event)["counted"])
        self.comp.phase=Phase.LIVE;self.db.commit()
        self.assertTrue(self.report(event)["duplicate"])
        self.team.completed_at=datetime.now(timezone.utc);self.db.commit()
        self.assertFalse(self.report()["counted"])
        self.assertEqual(self.team.score,100)
    def test_score_never_negative(self):
        self.team.score=10;self.db.commit()
        self.assertEqual(self.report()["deducted_points"],10)
        self.assertEqual(self.report()["score"],0)
    def test_elimination_blocks_all_game_access_and_relogin(self):
        for _ in range(3):self.report()
        actions=[lambda:main.terminal_ticket(self.player,self.db),
                 lambda:main.door(1,self.player,self.db),
                 lambda:main.hint(1,self.player,self.db),
                 lambda:main.validate(1,main.Answer(answer="wrong"),self.player,self.db),
                 lambda:main.join_team(main.TeamCreate(name="Rules fixture",join_code="test-join-code"),self.db)]
        for action in actions:
            with self.assertRaises(HTTPException) as result:action()
            self.assertEqual(result.exception.status_code,403)
        self.assertEqual(main.terminal_access(main.settings.secret_key,self.db)["allowed_teams"],[])
        with self.assertRaises(HTTPException):main.terminal_access("wrong",self.db)
    def test_organizer_reset_clears_elimination(self):
        for _ in range(3):self.report()
        main.reset_team(1,self.admin,self.db)
        self.assertEqual(self.team.exit_count,0)
        self.assertIsNone(self.team.eliminated_at)
        self.assertEqual(self.db.scalars(select(RuleEvent)).all(),[])
        self.assertIn("ticket",main.terminal_ticket(self.player,self.db))

if __name__=="__main__":unittest.main()

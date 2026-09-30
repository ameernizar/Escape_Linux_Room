import sys
sys.path.insert(0,"backend")
from app.challenges import instance

def test_team_instances_are_deterministic_and_private():
    assert instance("a",6)==instance("a",6)
    assert instance("a",6).expected_answer != instance("b",6).expected_answer
def test_all_doors_have_three_progressive_hints():
    assert all(len(instance("team",door).hints)==3 for door in range(1,7))

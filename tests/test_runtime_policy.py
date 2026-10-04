import sys
sys.path.insert(0,"runtime-worker")
from worker import create_arguments, spec
def test_runtime_container_has_no_network_or_privileges():
    args=create_arguments("17")
    assert args["network_mode"]=="none"
    assert args["read_only"] and args["user"]=="player"
    assert args["cap_drop"]==["ALL"] and args["volumes"]=={}
def test_team_identifier_is_not_a_container_argument():
    try: spec("1;rm -rf /")
    except ValueError: pass
    else: assert False

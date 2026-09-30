#!/usr/bin/env python3
"""Generate a team filesystem. Invoke only from the container-manager worker."""
import argparse, pathlib, shutil
from backend.app.challenges import instance

def put(path, text, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text); path.chmod(mode)
def main():
    a=argparse.ArgumentParser(); a.add_argument("seed"); a.add_argument("--root",default="/escape"); ns=a.parse_args()
    root=pathlib.Path(ns.root)
    if root.exists(): shutil.rmtree(root)
    root.mkdir()
    for door in range(1,7):
        game=instance(ns.seed,door); room=root/f"room{door}"
        put(room/"README.txt",game.prompt+"\n")
        if door==1: put(room/"sector-c"/"clue.txt",f"DOOR-1-KEY={game.expected_answer}\n")
        elif door==2: put(room/".cache","Nothing useful here.\n"); put(room/".secret_message",f"KEY={game.expected_answer.encode().hex()}\n")
        elif door==3:
            import base64
            put(room/"evidence.hex",base64.b64encode(game.expected_answer.encode()).hex()+"\n")
        elif door==4: put(room/"password.txt",f"KEY={game.expected_answer}\n",0o200)
        elif door==5: put(room/"logs"/"production.log",f"NEXT={game.expected_answer}\n")
        else:
            for label,part in zip("ABC",game.expected_answer.split("-")): put(room/"activity"/f"evidence-{label}",f"PART-{label}={part}\n")
if __name__=="__main__": main()

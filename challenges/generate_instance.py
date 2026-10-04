#!/usr/bin/env python3
"""Generate a reproducible, lightweight team filesystem inside an already-isolated container."""
import argparse, hashlib, hmac, os, pathlib, random, shutil, time
from backend.app.challenges import instance

def put(path, text, mode=0o644, mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text); path.chmod(mode)
    if mtime: os.utime(path,(mtime,mtime))
def rng_for(seed, label): return random.Random(hmac.new(seed.encode(),label.encode(),hashlib.sha256).digest())
def main():
    a=argparse.ArgumentParser(); a.add_argument("seed"); a.add_argument("--root",default="/escape"); ns=a.parse_args()
    root=pathlib.Path(ns.root).resolve()
    if root == pathlib.Path("/"): raise SystemExit("refusing filesystem root")
    if root.exists(): shutil.rmtree(root)
    root.mkdir()
    r=rng_for(ns.seed,"filesystem")
    names=["atlas","birch","cinder","delta","ember","frost","grove","harbor","iris","juniper"]
    for door in range(1,7):
        game=instance(ns.seed,door); room=root/f"room{door}"
        put(room/"README.txt",game.prompt+"\n")
        if door==1:
            target=room/r.choice(names)/r.choice(names)/"clue.txt"
            for n in names[:6]: put(room/n/"README.txt",f"Archive {n}: no exit information.\n")
            put(target,f"DOOR-1-KEY={game.expected_answer}\n")
        elif door==2:
            for name,text in {".cache":"Cache corruption detected.\n",".config":"Use ls -la before trusting hidden files.\n",".room":"Not every dotfile is evidence.\n",".secret":"4e4f545f54484953\n"}.items(): put(room/name,text)
            put(room/".secret_message",game.expected_answer.encode().hex()+"\n")
        elif door==3:
            import base64
            put(room/"evidence.hex",base64.b64encode(game.expected_answer.encode()).hex()+"\n")
            put(room/"readme.txt","This output has been encoded twice.\n")
        elif door==4:
            put(room/"readme.txt","The owner needs a read bit to inspect protected evidence.\n")
            put(room/"backup.txt","KEY=NOT-THE-KEY\n")
            put(room/"password.txt",f"KEY={game.expected_answer}\n",0o200)
        elif door==5:
            # 750 tiny files give realistic search pressure without excessive container cost.
            roots=["archive/2024","backup","old","temp","corrupted","reports","logs/development"]
            for i in range(750):
                place=room/r.choice(roots)/f"{r.choice(names)}_{i:03d}.{r.choice(['txt','log','dat'])}"
                marker=r.choice(["NEXT=IGNORE","NEXT=DECOY","STATUS=OK","checksum=invalid","NEXT=WRONG"])
                put(place,marker+"\n")
            put(room/"logs/production"/f"system_{r.randrange(100,999)}.log",f"service=escape\nNEXT={game.expected_answer}\n")
        else:
            old=time.time()-3*86400
            for i in range(24): put(room/"activity"/f"old-{i:02d}",f"PART-{r.choice('ABC')}=DECOY\n",mtime=old)
            parts=dict(zip("ABC",game.expected_answer.split("-")))
            for label in "CAB": put(room/"activity"/f"event-{r.choice(names)}-{label}",f"PART-{label}={parts[label]}\n")
if __name__=="__main__": main()

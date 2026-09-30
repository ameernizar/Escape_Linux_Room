"""Server-only deterministic answers. Never expose expected_answer in public responses."""
import base64, hashlib, hmac, random
from dataclasses import dataclass

@dataclass(frozen=True)
class Instance: door: int; prompt: str; expected_answer: str; hints: tuple[str, str, str]

WORDS=("ORBIT","NEXUS","VECTOR","EMBER","CIPHER","QUARTZ","RAVEN","SOLACE")
def instance(seed: str, door: int) -> Instance:
    rng=random.Random(hmac.new(seed.encode(), f"door:{door}".encode(), hashlib.sha256).digest())
    answer="-".join(rng.choice(WORDS) for _ in range(2)) + f"-{rng.randrange(100,999)}"
    if door==1: return Instance(1,"Find the real clue in /escape. It names the next sector.",answer,("Explore directories before guessing.","`find` can locate files by name.","Try `find /escape -type f -name '*.txt'`."))
    if door==2: return Instance(2,"Inspect the hidden files in the sector. Decode the valid hex message.",answer,("Some names begin with a dot.","List all entries, including hidden ones.","Use `ls -la`, then inspect candidate files."))
    if door==3: return Instance(3,"The evidence has two encodings: hexadecimal, then Base64.",answer,("The first text is not the final message.","Turn hexadecimal back into text first.","Try `xxd -r -p`, then pipe to `base64 -d`."))
    if door==4: return Instance(4,"One file is protected. Read the permission bits and restore its owner's read access.",answer,("Permissions are shown by `ls -l`.","The first three permission positions are for the owner.","Use `chmod u+r` on the protected clue."))
    if door==5: return Instance(5,"The production log contains the correct NEXT marker. Decoys are elsewhere.",answer,("The answer is inside a file.","Search text recursively.","Search only the production log tree with `grep -R`."))
    return Instance(6,"Only today's evidence matters. Find PART-A, PART-B and PART-C, then combine in order.",answer,("File timestamps are evidence.","`find` can filter files changed today.","Use `find . -type f -mtime 0`, then grep the PART records."))

"""Terminal-only gateway. It accepts a signed team ticket and starts a fixed shell only."""
import asyncio, os, re
import docker, jwt
from fastapi import FastAPI, WebSocket

app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
SECRET=os.environ["SECRET_KEY"]; TEAM=re.compile(r"^[1-9][0-9]{0,5}$")
client=docker.from_env()
def container_for(ticket:str):
    data=jwt.decode(ticket,SECRET,algorithms=["HS256"],options={"require":["exp","sub"]})
    if data.get("scope")!="terminal" or not TEAM.fullmatch(str(data.get("team",""))): raise ValueError("invalid ticket")
    c=client.containers.get(f"escape-team-{data['team']}")
    if c.status!="running": raise ValueError("team environment unavailable")
    return c
@app.websocket("/ws/terminal")
async def terminal(ws:WebSocket, ticket:str):
    try: container=container_for(ticket)
    except Exception: await ws.close(code=4401); return
    await ws.accept()
    # Fixed command; no caller-controlled command/image/container/mount input exists.
    result=container.exec_run(["/bin/bash","--noprofile","--norc"],stdin=True,stdout=True,stderr=True,tty=True,socket=True,user="player",workdir="/home/player")
    sock=result.output
    async def pump_out():
        while True:
            data=await asyncio.to_thread(sock.recv,4096)
            if not data: break
            await ws.send_bytes(data)
    outgoing=asyncio.create_task(pump_out())
    try:
        while True:
            message=await ws.receive()
            if message["type"]=="websocket.disconnect": break
            data=message.get("bytes")
            if data is None: data=(message.get("text") or "").encode()
            await asyncio.to_thread(sock.sendall,data)
    except Exception: pass
    finally:
        outgoing.cancel(); sock.close()

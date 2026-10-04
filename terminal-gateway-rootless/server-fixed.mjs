import {allowedTeams} from "./access.mjs";
import http from "node:http";import crypto from "node:crypto";import{spawn,execFileSync}from"node:child_process";import{mkdtemp,rm}from"node:fs/promises";import os from"node:os";import path from"node:path";import{fileURLToPath}from"node:url";import{WebSocketServer,WebSocket}from"ws";
const secret=process.env.SECRET_KEY,port=Number(process.env.TERMINAL_PORT||8080);if(!secret||secret.length<32)throw Error("Set a strong SECRET_KEY");const here=path.dirname(fileURLToPath(import.meta.url)),project=path.resolve(here,".."),teamRe=/^[1-9][0-9]{0,5}$/;
function ticket(token){const[a,b,c]=String(token||"").split("."),sig=crypto.createHmac("sha256",secret).update(`${a}.${b}`).digest(),got=Buffer.from(c||"","base64url");if(!a||!b||got.length!==sig.length||!crypto.timingSafeEqual(got,sig))throw Error("invalid ticket");const x=JSON.parse(Buffer.from(b,"base64url"));if(x.scope!=="terminal"||!teamRe.test(String(x.team))||x.exp<Date.now()/1000)throw Error("expired ticket");return x}
function run(args,options={}){return execFileSync("podman",args,{encoding:"utf8",timeout:60000,maxBuffer:8*1024*1024,...options})}const name=id=>{if(!teamRe.test(String(id)))throw Error("invalid team");return`escape-team-${id}`};
async function populate(id,seed){const n=name(id);const tmp=await mkdtemp(path.join(os.tmpdir(),"escape-team-"));try{const root=path.join(tmp,"escape"),g=spawn("python3",[path.join(project,"challenges/generate_instance.py"),seed,"--root",root],{stdio:"inherit"});await new Promise((ok,no)=>{g.on("error",no);g.on("close",c=>c===0?ok():no(Error(`generator exit ${c}`)))});execFileSync("chmod",["-R","u+rX",root]);const data=execFileSync("tar",["--owner=100","--group=101","--numeric-owner","-C",root,"-cf","-","."],{maxBuffer:8*1024*1024});run(["exec","-i","--user","player",n,"tar","-C","/escape","-xf","-"],{input:data,stdio:["pipe","ignore","pipe"]});run(["exec","--user","player",n,"chmod","200","/escape/room4/password.txt"])}finally{await rm(tmp,{recursive:true,force:true})}return{team_id:Number(id),status:"ready"}}
async function provision(id,seed){const n=name(id);if(!/^[a-f0-9]{64}$/.test(seed))throw Error("invalid seed");run(["run","-d","--name",n,"--network","none","--read-only","--user","player","--memory","256m","--cpus","0.5","--pids-limit","128","--cap-drop","all","--security-opt","no-new-privileges","--tmpfs","/tmp:rw,noexec,nosuid,size=32m","--tmpfs","/escape:rw,nosuid,nodev,size=64m,mode=0777","localhost/escape-player:locked","sleep","2147483"]);try{return await populate(id,seed)}catch(error){try{run(["rm","-f","--time","0",n],{stdio:"ignore"})}catch{}throw error}}
// Coalesce retries and never replace an existing team's filesystem.
const pending = new Map();
async function ensureProvisioned(id, seed) {
 if (!/^[a-f0-9]{64}$/.test(seed)) throw Error("invalid seed");
 const n = name(id);
 if (pending.has(n)) return pending.get(n);
 const job = (async () => {
  let exists = true;
  try { run(["container", "exists", n]); }
  catch (error) { if (error.status === 1) exists = false; else throw error; }
  if (exists) {
   const state = run(["inspect", "--format", "{{.State.Running}}", n]).trim();
   if (state !== "true") run(["start", n]);
   try { run(["exec", "--user", "player", n, "test", "-f", "/escape/room6/README.txt"]); }
   catch {
    const entries=run(["exec","--user","player",n,"find","/escape","-mindepth","1","-maxdepth","1","-print"]).trim();
    if(entries)throw Error("Incomplete challenge folder; refusing to overwrite player files");
    return populate(id,seed);
   }
   return {team_id:Number(id), status:"ready"};
  }
  return provision(id, seed);
 })();
 pending.set(n, job);
 try { return await job; } finally { pending.delete(n); }
}
const server=http.createServer(async(req,res)=>{if(req.url==="/health"){res.writeHead(200,{"content-type":"application/json"});return res.end('{"status":"ok","runtime":"rootless-podman"}')}const m=req.url?.match(/^\/internal\/teams\/([1-9][0-9]{0,5})\/provision$/);if(req.method!=="POST"||!m){res.writeHead(404);return res.end()}const k=Buffer.from(String(req.headers["x-worker-key"]||"")),s=Buffer.from(secret);if(k.length!==s.length||!crypto.timingSafeEqual(k,s)){res.writeHead(403);return res.end()}let raw="";for await(const q of req)raw+=q;if(raw.length>4096){res.writeHead(413);return res.end()}try{const result=await ensureProvisioned(m[1],JSON.parse(raw).seed);res.writeHead(200,{"content-type":"application/json"});res.end(JSON.stringify(result))}catch(e){console.error("provision failed",e.message);res.writeHead(503);res.end('{"detail":"Provisioning failed"}')}});
const wss=new WebSocketServer({noServer:true,maxPayload:4096});
let accessRequest;
const access=()=>{
 if(!accessRequest)accessRequest=allowedTeams(process.env.TERMINAL_API_URL||"http://127.0.0.1:8000",secret).finally(()=>{accessRequest=undefined});
 return accessRequest;
};
server.on("upgrade",async(req,sock,head)=>{
 try{
  const u=new URL(req.url,"http://localhost");
  if(u.pathname!=="/ws/terminal")throw Error("Invalid route");
  const claims=ticket(u.searchParams.get("ticket"));
  if(!(await access()).has(Number(claims.team)))throw Error("Team unavailable");
  if(!sock.destroyed)wss.handleUpgrade(req,sock,head,ws=>wss.emit("connection",ws,req));
 }catch{if(!sock.destroyed){sock.write("HTTP/1.1 403 Forbidden\r\n\r\n");sock.destroy()}}
});
let checking=false;
setInterval(async()=>{
 if(checking||wss.clients.size===0)return;
 checking=true;
 try{
  const allowed=await access();
  for(const ws of wss.clients)if(!allowed.has(ws.teamId)){ws.authorized=false;ws.close(4403,"Team disabled or eliminated")}
 }catch{
  for(const ws of wss.clients){ws.authorized=false;ws.close(1013,"Authorization unavailable; reconnect")}
 }finally{checking=false}
},2000).unref();
wss.on("connection",(ws,req)=>{let c;try{c=ticket(new URL(req.url,"http://localhost").searchParams.get("ticket"))}catch{ws.close(4401);return}ws.teamId=Number(c.team);ws.authorized=true;const child=spawn("podman",["exec","-i","-t","--user","player","--workdir","/home/player",name(c.team),"/bin/bash","--noprofile","--norc"],{stdio:["pipe","pipe","pipe"]});child.stdout.on("data",d=>ws.readyState===WebSocket.OPEN&&ws.send(d));child.stderr.on("data",d=>ws.readyState===WebSocket.OPEN&&ws.send(d));child.on("error",()=>ws.close(1011,"shell unavailable"));child.on("close",()=>ws.readyState===WebSocket.OPEN&&ws.close(1011,"shell ended"));ws.on("message",d=>ws.authorized&&child.stdin.writable&&child.stdin.write(d));ws.on("close",()=>child.kill("SIGTERM"))});server.listen(port,"127.0.0.1",()=>console.log(`Rootless terminal worker listening on ${port}`));

const {mkdirSync,existsSync,lstatSync,unlinkSync,chmodSync} = await import("node:fs");
const {createConnection} = await import("node:net");
const socketPath = process.env.TERMINAL_SOCKET_PATH||path.join(here,"run","worker.sock");
mkdirSync(path.dirname(socketPath),{recursive:true});
if (existsSync(socketPath)) {
 if (!lstatSync(socketPath).isSocket()) throw Error("Worker socket path is not a socket");
 const active = await new Promise((resolve,reject)=>{
  const probe=createConnection(socketPath);
  probe.on("connect",()=>{probe.destroy();resolve(true)});
  probe.on("error",error=>{if(error.code==="ECONNREFUSED"||error.code==="ENOENT")resolve(false);else reject(error)});
  probe.setTimeout(2000,()=>{probe.destroy();reject(Error("Socket probe timed out"))});
 });
 if(active)throw Error("Worker socket already active");
 unlinkSync(socketPath);
}
const privateServer=http.createServer((req,res)=>server.emit("request",req,res));
privateServer.listen(socketPath,()=>{chmodSync(socketPath,0o666);console.log("Private provisioning socket ready")});

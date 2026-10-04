import {createRoot} from "react-dom/client";
import {useEffect,useState} from "react";
import {ApiError,request} from "./api";
import "./style.css";
import {ElapsedTime,formatTime} from "./ElapsedTime";
type Team={exit_count:number;eliminated:boolean;id:number;name:string;enabled:boolean;score:number;current_door:number;completed_at:string|null;elapsed_seconds:number|null;rank:number|null;door_times:{door:number;elapsed_seconds:number|null}[]};
function Admin(){
 const [token,setToken]=useState(localStorage.adminToken||"");
 const [username,setUsername]=useState("");const [password,setPassword]=useState("");
 const [name,setName]=useState("");const [code,setCode]=useState("");
 const [teams,setTeams]=useState<Team[]>([]);const [message,setMessage]=useState("");
 const [competition,setCompetition]=useState<{phase:string;elapsed_seconds:number;allowed_phases:string[]}|null>(null);
 const [busy,setBusy]=useState(false);const [loaded,setLoaded]=useState(false);
 const signOut=()=>{localStorage.removeItem("adminToken");setToken("");setTeams([]);setLoaded(false);setCompetition(null)};
 const fail=(error:unknown)=>{if(error instanceof ApiError&&(error.status===401||error.status===403))signOut();setMessage((error as Error).message)};
 const refresh=async()=>{const [data,state]=await Promise.all([request("/api/v1/admin/teams",token),request("/api/v1/admin/competition",token)]);setTeams(data);setCompetition(state);setLoaded(true)};
 useEffect(()=>{
  if(!token)return;
  let active=true;
  const update=async()=>{try{const [data,state]=await Promise.all([request("/api/v1/admin/teams",token),request("/api/v1/admin/competition",token)]);if(active){setTeams(data);setCompetition(state);setLoaded(true)}}catch(error){if(active)fail(error)}};
  void update();const timer=setInterval(update,5000);return()=>{active=false;clearInterval(timer)};
 },[token]);
 const act=async(path:string,body?:object)=>{
  setBusy(true);setMessage("");
  try{await request(path,token,{method:"POST",body:body?JSON.stringify(body):undefined});setMessage(path.endsWith("/provision")?"Team shell is ready.":"Updated successfully.");await refresh()}catch(error){fail(error)}finally{setBusy(false)}
 };
 if(!token)return <main className="login"><h1>🐧 Organizer Console</h1><p>Sign in to create teams and manage the competition.</p>
 <form onSubmit={async e=>{e.preventDefault();setBusy(true);setMessage("");try{const data=await request("/api/v1/auth/login","",{method:"POST",body:JSON.stringify({username:username.trim(),password})});await request("/api/v1/admin/teams",data.access_token);localStorage.adminToken=data.access_token;setToken(data.access_token);setPassword("")}catch(error){fail(error)}finally{setBusy(false)}}}>
 <label>Username<input required autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)}/></label>
 <label>Password<input required type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)}/></label>
 <button disabled={busy}>{busy?"Signing in…":"Sign in"}</button></form>
 {message&&<p className="notice" role="alert">{message}</p>}<a href="/join.html">Team login</a></main>;
 return <main><header><h1>🐧 Organizer Console</h1><a href="/join.html">Team login</a><button onClick={signOut}>Sign out</button></header>
 <section className="stats"><div><small>REGISTERED</small><b>{teams.length}</b></div><div><small>ENABLED</small><b>{teams.filter(t=>t.enabled).length}</b></div><div><small>FINISHED</small><b>{teams.filter(t=>t.completed_at).length}</b></div></section>
 {message&&<div className="notice" role="status">{message}</div>}
 <section className="panel"><h2>Create team</h2><form className="form-row" onSubmit={async e=>{e.preventDefault();setBusy(true);setMessage("");try{const created=await request("/api/v1/admin/teams",token,{method:"POST",body:JSON.stringify({name:name.trim(),join_code:code})});setName("");setCode("");setMessage(created.shell_status==="ready"?"Team created and shell ready. Share its name and join code privately.":"Team registered, but shell setup failed. Use Prepare shell next to this team to retry.");await refresh()}catch(error){fail(error)}finally{setBusy(false)}}}>
 <label>Team name<input required minLength={3} maxLength={80} value={name} onChange={e=>setName(e.target.value)}/></label>
 <label>Private join code<input required minLength={8} maxLength={128} value={code} onChange={e=>setCode(e.target.value)} autoComplete="off"/></label>
 <button disabled={busy}>{busy?"Working…":"Create team"}</button></form><p className="muted">Use at least 8 characters for the join code. Players sign in at /join.html.</p></section>
 <section className="panel"><h2>Competition controls</h2><p>Phase: {competition?.phase||"Loading…"} · Elapsed: <ElapsedTime seconds={competition?.elapsed_seconds} running={competition?.phase==="LIVE"}/></p><p className="muted">Start in order: Ready → Countdown → Live. Pause or finish a live game.</p>
 <div className="actions">{["PREPARING","READY","COUNTDOWN","LIVE","PAUSED","FINISHED"].map(phase=><button key={phase} disabled={busy||!competition?.allowed_phases.includes(phase)} onClick={()=>{if(phase==="FINISHED"&&!confirm("Finish the competition? Answer submissions will stop."))return;void act("/api/v1/admin/competition/phase",{phase})}}>{phase}</button>)}</div></section>
 <section className="panel"><div className="section-heading"><h2>Team monitoring</h2><button disabled={busy} onClick={()=>void refresh().catch(fail)}>Refresh</button></div><p className="muted">Ranked by score, then shortest recorded completion time. Exact ties share a rank. Door times are cumulative from LIVE, excluding pauses. Updates every 5 seconds.</p>
 {!loaded?<p>Loading teams…</p>:teams.length===0?<p>No teams yet. Create the first team above.</p>:<div className="table-scroll"><table><thead><tr><th>Rank</th><th>Team</th><th>Progress</th><th>Score</th><th>Elapsed / final time</th><th>Door times</th><th>Status</th><th>Departures</th><th>Actions</th></tr></thead><tbody>{teams.map(t=><tr key={t.id}><td>{t.rank??"—"}</td><td>{t.name}</td><td>{t.current_door>6?"Escaped":"Door "+t.current_door+" / 6"}</td><td>{t.score}</td><td><ElapsedTime seconds={t.elapsed_seconds} running={competition?.phase==="LIVE"&&!t.completed_at}/></td><td><details><summary>{t.door_times?.length||0} solved</summary>{t.door_times?.map(split=><p key={split.door}>Door {split.door}: {formatTime(split.elapsed_seconds)}</p>)}</details></td><td>{t.eliminated?"Eliminated":!t.enabled?"Disabled":t.completed_at?"Finished":"Enabled"}</td><td>{t.exit_count}/3</td><td><button disabled={busy} onClick={()=>void act("/api/v1/admin/teams/"+t.id+"/provision")}>Prepare shell</button><button disabled={busy||t.eliminated} onClick={()=>void act("/api/v1/admin/teams/"+t.id+"/enabled",{enabled:!t.enabled})}>{t.enabled?"Disable":"Enable"}</button><button disabled={busy} onClick={()=>{if(confirm("Reset "+t.name+"? Score, solved doors, departures, and elimination will be cleared."))void act("/api/v1/admin/teams/"+t.id+"/reset")}}>Reset progress</button></td></tr>)}</tbody></table></div>}</section></main>
}
createRoot(document.getElementById("root")!).render(<Admin/>);

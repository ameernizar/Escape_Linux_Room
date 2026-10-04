import {useEffect, useRef, useState} from "react";
import {createRoot} from "react-dom/client";
import {Terminal} from "@xterm/xterm";
import {FitAddon} from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import "./style.css";
import {ElapsedTime} from "./ElapsedTime";

import {ApiError,request as api} from "./api";
import {JoinForm} from "./JoinForm";
import {FullscreenPrompt,useFullscreenMode} from "./FullscreenMode";
import {useClipboardGuard} from "./useClipboardGuard";
import {useDepartureReports} from "./useDepartureReports";

function App(){
 const [token,setToken]=useState(localStorage.escapeToken||""); const [team,setTeam]=useState<any>(); const [board,setBoard]=useState<any[]>([]); const [notice,setNotice]=useState("");
 const [prompt,setPrompt]=useState(""); const [answer,setAnswer]=useState(""); const [busy,setBusy]=useState(false);
 const terminal=useRef<HTMLDivElement>(null);
 const reports=useDepartureReports(token,state=>setTeam((previous:any)=>({...previous,...state})));
 const fullscreen=useFullscreenMode(Boolean(token)&&!team?.eliminated&&team?.phase!=="FINISHED"&&!(team?.current_door>6),{chargeExits:team?.phase==="LIVE",onExit:reports.report,onResume:reports.flush,exitCount:team?.exit_count||0});
 const playAllowed=useRef(false);playAllowed.current=!fullscreen.blocked&&!team?.eliminated;
 useClipboardGuard(Boolean(token)&&team?.phase!=="FINISHED"&&!(team?.current_door>6));
 const leave=()=>{localStorage.removeItem("escapeToken");setToken("");setTeam(undefined);setPrompt("");setNotice("");if(document.fullscreenElement)void document.exitFullscreen().catch(()=>{})};
 const requestLeave=()=>{if(confirm("Leave your team? The competition clock will keep running."))leave()};
 useEffect(()=>{
  if(!token)return;
  let active=true;
  const update=async()=>{
   try{const data=await api("/api/v1/game/me",token);if(!active)return;setTeam(data)}
   catch(error){if(!active)return;if(error instanceof ApiError&&(error.status===401||error.status===403))leave();else setNotice((error as Error).message)}
   try{const data=await api("/api/v1/leaderboard",token);if(active)setBoard(data)}catch{/* Leaderboard may be disabled. */}
  };
  void update();const timer=setInterval(update,5000);
  return()=>{active=false;clearInterval(timer)};
 },[token]);
 useEffect(()=>{
  setPrompt("");setAnswer("");
  if(!token||!team||team.current_door>6)return;
  const controller=new AbortController();
  api("/api/v1/game/doors/"+team.current_door,token,{signal:controller.signal}).then(data=>setPrompt(data.prompt)).catch(error=>{if(!controller.signal.aborted)setNotice(error.message)});
  return()=>controller.abort();
 },[token,team?.current_door]);

 useEffect(()=>{
  if(!token||!terminal.current||team?.eliminated)return;
  const container=terminal.current;
  const term=new Terminal({theme:{background:"#07130f",foreground:"#d5f7da",cursor:"#79ff9c"},fontFamily:"ui-monospace, monospace",fontSize:14,cursorBlink:true});
  const fit=new FitAddon();
  const controller=new AbortController();
  let disposed=false;
  let socket:WebSocket|undefined;
  term.loadAddon(fit);
  term.open(container);
  fit.fit();
  const focusTerminal=()=>term.focus();
  container.addEventListener("click",focusTerminal);
  if(playAllowed.current)term.focus();
  const resizeObserver=new ResizeObserver(()=>{if(!disposed)fit.fit()});
  resizeObserver.observe(container);
  term.writeln("\x1b[1;32mESCAPE THE TERMINAL\x1b[0m");
  term.writeln("Connecting to your isolated shell…");
  const input=term.onData(data=>{if(playAllowed.current&&socket?.readyState===WebSocket.OPEN)socket.send(data)});
  api("/api/v1/terminal/ticket",token,{method:"POST",signal:controller.signal}).then(({ticket})=>{
   if(disposed)return;
   const ws=socket=new WebSocket(`${location.protocol==="https:"?"wss":"ws"}://${location.host}/ws/terminal?ticket=${encodeURIComponent(ticket)}`);
   ws.binaryType="arraybuffer";
   ws.onopen=()=>{if(disposed)return;term.writeln("\x1b[32mConnected. Click here to type.\x1b[0m");if(playAllowed.current)term.focus()};
   ws.onmessage=e=>{if(!disposed)term.write(typeof e.data==="string"?e.data:new Uint8Array(e.data))};
   ws.onerror=()=>{if(!disposed)term.writeln("\r\n\x1b[31mTerminal connection failed. Refresh to retry.\x1b[0m")};
   ws.onclose=()=>{if(!disposed)term.writeln("\r\n\x1b[31mTerminal disconnected. Refresh to reconnect.\x1b[0m")};
  }).catch(e=>{if(!disposed)term.writeln(`\x1b[31m${e.message}\x1b[0m`)});
  return()=>{
   disposed=true;
   controller.abort();
   resizeObserver.disconnect();
   container.removeEventListener("click",focusTerminal);
   input.dispose();
   socket?.close();
   term.dispose();
  };
 },[token,Boolean(team?.eliminated)]);
 if(!token)return <JoinForm onJoin={setToken}/>;
 if(team?.eliminated)return <main className="login"><h1>Team eliminated</h1><p>Your team reached three departures during LIVE play. Answers and terminal access are blocked for every team member.</p><p>Score: {team.score} · Departures: {team.exit_count}/3</p><p>Contact the organizer if you believe this was an error.</p><button onClick={leave}>Leave team</button></main>;
 return <><div ref={fullscreen.contentRef} aria-hidden={fullscreen.blocked||undefined}><main><header><h1>🐧 Escape the Terminal</h1><span className="live">{team?.phase||"Loading…"}</span><span>Departures: {team?.exit_count||0}/3</span><button onClick={requestLeave}>Leave team</button></header>
 <section className="stats"><div><small>TEAM</small><b>{team?.team||"Loading…"}</b></div><div><small>SCORE</small><b>{team?.score??"—"}</b></div><div><small>ACTIVE DOOR</small><b>{team?team.current_door>6?"ESCAPED":"Door "+team.current_door+" / 6":"—"}</b></div><div><small>ELAPSED TIME</small><b><ElapsedTime seconds={team?.elapsed_seconds} running={team?.timer_running}/></b></div></section>
 <section className="doors" aria-label="Door progress">{[1,2,3,4,5,6].map(n=><span key={n} className={n<(team?.current_door||1)?"done":n===team?.current_door?"active":"locked"}>{n===6?"FINAL":"DOOR "+n}</span>)}</section>
 {notice&&<div className="notice" role="status">{notice}</div>}
 <section className="panel"><h2>{team?.current_door>6?"Escape complete":"Current challenge"}</h2>
 {team?.current_door>6?<p>Congratulations! Your team has completed all six doors.</p>:<><p className="challenge-prompt">{prompt||"Loading challenge…"}</p>
 <form className="form-row" onSubmit={async e=>{e.preventDefault();if(!team||!playAllowed.current)return;setBusy(true);try{await api("/api/v1/game/doors/"+team.current_door+"/validate",token,{method:"POST",body:JSON.stringify({answer})});setAnswer("");setNotice("Door unlocked!");setTeam(await api("/api/v1/game/me",token))}catch(error){setNotice((error as Error).message)}finally{setBusy(false)}}}>
 <label>Door key<input required maxLength={128} value={answer} onChange={e=>setAnswer(e.target.value)} placeholder="Enter the key you found"/></label><button disabled={busy||!team||team.phase!=="LIVE"}>Unlock door</button>
 <button type="button" disabled={busy||!team} onClick={async()=>{if(!team||!playAllowed.current)return;setBusy(true);try{const h=await api("/api/v1/game/doors/"+team.current_door+"/hint",token,{method:"POST"});setNotice(h.text);setTeam(await api("/api/v1/game/me",token))}catch(error){setNotice((error as Error).message)}finally{setBusy(false)}}}>Get hint (−25 points)</button></form>
 {team&&team.phase!=="LIVE"&&<p className="muted">Answer submissions open when the organizer sets the game to LIVE.</p>}</>}</section>
 <div className="grid"><section className="panel"><h2>Terminal</h2><div className="terminal" ref={terminal}/></section><aside className="panel"><h2>Leaderboard</h2><p className="muted">Updates every 5 seconds.</p>{board.length?board.map(x=><p key={x.team} className={x.team===team?.team?"own-team":""}><b>#{x.rank}</b><span>{x.team}</span><em>{x.score} pts<br/><ElapsedTime seconds={x.elapsed_seconds}/></em></p>):<p>No leaderboard available yet.</p>}</aside></div></main></div><FullscreenPrompt mode={fullscreen} onLeave={requestLeave}/></>
}
createRoot(document.getElementById("root")!).render(<App/>);

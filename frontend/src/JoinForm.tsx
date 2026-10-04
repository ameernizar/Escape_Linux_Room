import {useState} from "react";
import {request} from "./api";
export function JoinForm({onJoin}:{onJoin:(token:string)=>void}){
 const [name,setName]=useState("");const [code,setCode]=useState("");const [message,setMessage]=useState("");const [busy,setBusy]=useState(false);
 return <main className="login"><h1>🐧 Escape the Terminal</h1><p>Join using the details supplied by your organizer.</p>
 <form onSubmit={async e=>{e.preventDefault();setBusy(true);setMessage("");try{const data=await request("/api/v1/teams/join","",{method:"POST",body:JSON.stringify({name:name.trim(),join_code:code})});localStorage.escapeToken=data.access_token;onJoin(data.access_token)}catch(error){setMessage((error as Error).message)}finally{setBusy(false)}}}>
 <label>Team name<input required minLength={3} maxLength={80} autoComplete="organization" value={name} onChange={e=>setName(e.target.value)}/></label>
 <label>Join code<input required minLength={8} maxLength={128} type="password" autoComplete="current-password" value={code} onChange={e=>setCode(e.target.value)}/></label>
 <button disabled={busy}>{busy?"Joining…":"Join game"}</button></form>
 {message&&<p className="notice" role="alert">{message}</p>}<a href="/admin.html">Organizer sign in</a></main>
}

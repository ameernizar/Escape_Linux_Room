import {useEffect,useLayoutEffect,useRef,useState} from "react";
type Options={chargeExits:boolean;onExit:(reason:string)=>Promise<boolean>;onResume:()=>Promise<boolean>;exitCount:number};

export function useFullscreenMode(active:boolean,options:Options){
 const contentRef=useRef<HTMLDivElement>(null),resumeRef=useRef<HTMLButtonElement>(null);
 const latest=useRef(options);latest.current=options;
 const armed=useRef(false);
 const [fullscreen,setFullscreen]=useState(Boolean(document.fullscreenElement));
 const [away,setAway]=useState(document.hidden),[needsResume,setNeedsResume]=useState(false);
 const [message,setMessage]=useState(""),[syncing,setSyncing]=useState(false);
 const blocked=active&&(!fullscreen||away||needsResume||syncing);
 const permitted=useRef(!blocked);permitted.current=!blocked;

 useEffect(()=>{
  if(!active){armed.current=false;setNeedsResume(false);setMessage("");return}
  const depart=(reason:string)=>{
   permitted.current=false;setNeedsResume(true);
   setMessage("You left the game. Return to fullscreen to continue.");
   // Blur, visibility and fullscreen events from one departure count only once.
   if(!armed.current)return;
   armed.current=false;
   if(latest.current.chargeExits){
    setSyncing(true);
    void latest.current.onExit(reason).catch(()=>setMessage("Could not sync this departure. Reconnect, then resume; the report is saved for retry.")).finally(()=>setSyncing(false));
   }
  };
  const fullscreenChanged=()=>{const inside=Boolean(document.fullscreenElement);setFullscreen(inside);if(!inside)depart("fullscreen_exit")};
  const blurred=()=>{setAway(true);depart("window_blur")};
  const visibility=()=>{setAway(document.hidden);if(document.hidden)depart("page_hidden")};
  const focused=()=>setAway(document.hidden);
  const pagehide=()=>depart("page_unload");
  const beforeUnload=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue=""};
  document.addEventListener("fullscreenchange",fullscreenChanged);
  document.addEventListener("visibilitychange",visibility);
  window.addEventListener("blur",blurred);window.addEventListener("focus",focused);
  window.addEventListener("pagehide",pagehide);window.addEventListener("beforeunload",beforeUnload);
  return()=>{
   document.removeEventListener("fullscreenchange",fullscreenChanged);
   document.removeEventListener("visibilitychange",visibility);
   window.removeEventListener("blur",blurred);window.removeEventListener("focus",focused);
   window.removeEventListener("pagehide",pagehide);window.removeEventListener("beforeunload",beforeUnload);
  };
 },[active]);
 useLayoutEffect(()=>{
  const content=contentRef.current;
  if(blocked){content?.setAttribute("inert","");resumeRef.current?.focus()}
  else content?.removeAttribute("inert");
  return()=>content?.removeAttribute("inert");
 },[blocked]);

 const enter=async()=>{
  if(syncing)return;
  setMessage("");
  if(!document.fullscreenEnabled||!document.documentElement.requestFullscreen){
   setMessage("Fullscreen is unavailable. Use a supported browser or contact your organizer.");return;
  }
  try{
   // Fullscreen must be requested directly from a click, before awaiting network I/O.
   if(!document.fullscreenElement)await document.documentElement.requestFullscreen();
   setFullscreen(Boolean(document.fullscreenElement));
   setSyncing(true);
   const allowed=await latest.current.onResume();
   if(!allowed){setMessage("Your team has been eliminated.");return}
   if(document.hidden||!document.hasFocus()){setAway(true);setNeedsResume(true);return}
   setAway(false);setNeedsResume(false);armed.current=true;
   requestAnimationFrame(()=>{if(!document.hidden)(document.querySelector(".xterm-helper-textarea") as HTMLElement|null)?.focus()});
  }catch{setNeedsResume(true);setMessage("Could not resume. Check your connection and allow fullscreen, then retry.")}
  finally{setSyncing(false)}
 };
 return {blocked,permitted,contentRef,resumeRef,enter,message,syncing,exitCount:options.exitCount};
}

export function FullscreenPrompt({mode,onLeave}:{mode:ReturnType<typeof useFullscreenMode>;onLeave:()=>void}){
 if(!mode.blocked)return null;
 return <div className="fullscreen-overlay"><section className="fullscreen-card" role="dialog" aria-modal="true" aria-labelledby="fullscreen-title">
 <h1 id="fullscreen-title">Fullscreen required</h1>
 <p>Copy, cut, paste and text drops are disabled during the game.</p>
 <p>During LIVE play, the first and second departures deduct 25 points each (minimum score 0). The third departure eliminates your entire team.</p>
 <p><strong>Team departures: {mode.exitCount} / 3</strong></p>
 <p>Leaving fullscreen or switching tabs/apps counts as a departure. The clock keeps running. Browser and OS shortcuts cannot be disabled by this page.</p>
 {mode.message&&<p role="alert" className="notice">{mode.message}</p>}
 <div className="actions"><button ref={mode.resumeRef} disabled={mode.syncing} onClick={()=>void mode.enter()}>{mode.syncing?"Saving…":"Enter fullscreen / resume"}</button><button onClick={onLeave}>Leave team</button></div>
 </section></div>
}

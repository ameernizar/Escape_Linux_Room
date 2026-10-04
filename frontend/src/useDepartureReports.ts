import {useRef} from "react";
import {request} from "./api";
type Incident={event_id:string;reason:string};
export function useDepartureReports(token:string,onState:(state:any)=>void){
 const current=useRef({token,onState});current.current={token,onState};
 const inFlight=useRef<Promise<boolean>|null>(null);
 const key="escapePendingDeparture:"+token;
 const pending=():Incident[]=>{try{return JSON.parse(localStorage.getItem(key)||"[]")}catch{return []}};
 const flush=():Promise<boolean>=>{
  if(inFlight.current)return inFlight.current;
  const task=(async()=>{
   let allowed=true;
   for(const incident of pending()){
    const state=await request("/api/v1/game/departures",token,{method:"POST",body:JSON.stringify(incident),keepalive:true});
    localStorage.setItem(key,JSON.stringify(pending().filter(item=>item.event_id!==incident.event_id)));
    if(current.current.token===token)current.current.onState(state);
    if(state.eliminated)allowed=false;
   }
   return allowed;
  })();
  inFlight.current=task;
  task.finally(()=>{if(inFlight.current===task)inFlight.current=null}).catch(()=>{});
  return task;
 };
 const report=(reason:string)=>{
  const list=pending();
  list.push({event_id:crypto.randomUUID(),reason});
  localStorage.setItem(key,JSON.stringify(list));
  return flush();
 };
 return {report,flush};
}

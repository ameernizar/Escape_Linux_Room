import {useEffect,useState} from "react";
export function formatTime(seconds:number|null|undefined){
 if(seconds==null)return "Not recorded";
 const total=Math.max(0,Math.round(seconds*1000));
 const hours=Math.floor(total/3600000),minutes=Math.floor(total/60000)%60,secs=Math.floor(total/1000)%60;
 return [hours,minutes,secs].map(value=>String(value).padStart(2,"0")).join(":")+"."+String(total%1000).padStart(3,"0");
}
export function ElapsedTime({seconds,running=false}:{seconds:number|null|undefined;running?:boolean}){
 const [extra,setExtra]=useState(0);
 useEffect(()=>{setExtra(0);if(!running)return;const start=performance.now();const timer=setInterval(()=>setExtra((performance.now()-start)/1000),1000);return()=>clearInterval(timer)},[seconds,running]);
 return <span>{formatTime(seconds==null?seconds:seconds+extra)}</span>;
}

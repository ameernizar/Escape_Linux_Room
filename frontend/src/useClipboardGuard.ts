import {useEffect} from "react";

// UI restriction only: browser tools and external applications remain outside our control.
export function useClipboardGuard(active:boolean){
 useEffect(()=>{
  if(!active)return;
  const block=(event:Event)=>{event.preventDefault();event.stopImmediatePropagation()};
  const beforeInput=(event:Event)=>{
   if(["insertFromPaste","insertFromPasteAsQuotation","insertFromDrop"].includes((event as InputEvent).inputType))block(event);
  };
  const shortcuts=(event:KeyboardEvent)=>{
   const key=event.key.toLowerCase();
   const modifier=event.ctrlKey||event.metaKey;
   if((modifier&&key==="v")||(event.shiftKey&&key==="insert")||(modifier&&key==="insert")||(modifier&&event.shiftKey&&(key==="c"||key==="x")))block(event);
   // Plain Ctrl+C must still reach the shell as its interrupt command.
  };
  const events=["copy","cut","paste","drop","dragover"];
  events.forEach(name=>document.addEventListener(name,block,true));
  document.addEventListener("beforeinput",beforeInput,true);
  document.addEventListener("keydown",shortcuts,true);
  return()=>{
   events.forEach(name=>document.removeEventListener(name,block,true));
   document.removeEventListener("beforeinput",beforeInput,true);
   document.removeEventListener("keydown",shortcuts,true);
  };
 },[active]);
}

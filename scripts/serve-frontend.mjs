import http from "node:http";
import {createReadStream} from "node:fs";
import {stat} from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"../frontend/dist");
const port=Number(process.env.FRONTEND_PORT||5173);
const types={".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",".css":"text/css; charset=utf-8",".svg":"image/svg+xml",".png":"image/png",".ico":"image/x-icon",".woff2":"font/woff2"};
const server=http.createServer(async(req,res)=>{
 if(req.url?.startsWith("/api/")){
  const proxy=http.request({hostname:"127.0.0.1",port:8000,path:req.url,method:req.method,headers:{...req.headers,host:"127.0.0.1:8000"}},upstream=>{
   res.writeHead(upstream.statusCode||502,upstream.headers);upstream.pipe(res);
  });
  proxy.setTimeout(120000,()=>proxy.destroy(Error("API timeout")));
  proxy.on("error",()=>{if(!res.headersSent)res.writeHead(502,{"content-type":"application/json"});res.end('{"detail":"API unavailable; retry shortly."}')});
  req.on("aborted",()=>proxy.destroy());req.pipe(proxy);return;
 }
 if(req.method!=="GET"&&req.method!=="HEAD"){res.writeHead(405,{Allow:"GET, HEAD"});res.end();return}
 try{
  const pathname=decodeURIComponent(new URL(req.url,"http://localhost").pathname);
  const file=path.resolve(root,"."+ (pathname==="/"?"/index.html":pathname));
  if(!file.startsWith(root+path.sep)||pathname.includes("\0")){res.writeHead(403);res.end();return}
  const info=await stat(file);if(!info.isFile())throw Error("Not a file");
  res.writeHead(200,{"Content-Type":types[path.extname(file)]||"application/octet-stream","Content-Length":info.size,"Cache-Control":pathname.startsWith("/assets/")?"public, max-age=31536000, immutable":"no-cache","X-Content-Type-Options":"nosniff"});
  if(req.method==="HEAD"){res.end();return}
  const stream=createReadStream(file);stream.on("error",()=>res.destroy());stream.pipe(res);
 }catch{res.writeHead(404);res.end("Not found")}
});
server.on("upgrade",(req,socket,head)=>{
 let pathname;try{pathname=new URL(req.url,"http://localhost").pathname}catch{socket.destroy();return}
 const target=pathname==="/ws/terminal"?8080:pathname==="/ws/leaderboard"?8000:null;
 if(!target){socket.destroy();return}
 const proxy=http.request({hostname:"127.0.0.1",port:target,path:req.url,method:"GET",headers:{...req.headers,host:"127.0.0.1:"+target}});
 proxy.on("upgrade",(response,upstream,upstreamHead)=>{
  socket.write("HTTP/1.1 101 Switching Protocols\r\n"+Object.entries(response.headers).map(([key,value])=>key+": "+value+"\r\n").join("")+"\r\n");
  if(upstreamHead.length)socket.write(upstreamHead);
  if(head.length)upstream.write(head);
  socket.on("error",()=>upstream.destroy());upstream.on("error",()=>socket.destroy());
  socket.on("close",()=>upstream.destroy());upstream.on("close",()=>socket.destroy());
  socket.pipe(upstream).pipe(socket);
 });
 proxy.on("response",response=>{response.resume();socket.end("HTTP/1.1 "+response.statusCode+" Rejected\r\nConnection: close\r\nContent-Length: 0\r\n\r\n")});
 proxy.on("error",()=>socket.destroy());
 socket.on("error",()=>proxy.destroy());proxy.end();
});
server.listen(port,"0.0.0.0",()=>console.log("Built frontend listening on "+port));

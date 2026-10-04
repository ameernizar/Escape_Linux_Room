export class ApiError extends Error {
 constructor(message:string, public status:number){super(message)}
}
export async function request(path:string,token="",init:RequestInit={}){
 const response=await fetch(path,{...init,headers:{"Content-Type":"application/json",...(token?{Authorization:"Bearer "+token}:{}),...init.headers}});
 const data=await response.json().catch(()=>({detail:response.statusText}));
 if(!response.ok){
  const detail=data.detail;
  throw new ApiError(Array.isArray(detail)?detail.map((item:{msg:string})=>item.msg).join("; "):typeof detail==="string"?detail:"Request failed",response.status);
 }
 return data;
}

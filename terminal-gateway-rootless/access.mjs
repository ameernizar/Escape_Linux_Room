export async function allowedTeams(base,secret){
 const response=await fetch(base+"/api/v1/internal/terminal-access",{headers:{"X-Worker-Key":secret},signal:AbortSignal.timeout(3000)});
 if(!response.ok)throw Error("Terminal authorization unavailable");
 const data=await response.json();
 if(!Array.isArray(data.allowed_teams)||!data.allowed_teams.every(id=>Number.isInteger(id)&&id>0))throw Error("Invalid terminal authorization response");
 return new Set(data.allowed_teams);
}

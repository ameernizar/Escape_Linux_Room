import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
export default defineConfig({
 plugins:[react()],
 build:{rollupOptions:{input:Object.fromEntries(["index","admin","organize","join","play"].map(name=>[name,resolve(__dirname,name+".html")]))}},
 server:{proxy:{
  "/api":"http://localhost:8000",
  "/ws/leaderboard":{target:"ws://localhost:8000",ws:true},
  "/ws/terminal":{target:"ws://localhost:8080",ws:true}
 }}
});

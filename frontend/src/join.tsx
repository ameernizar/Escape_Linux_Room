import {createRoot} from "react-dom/client";
import {JoinForm} from "./JoinForm";
import "./style.css";
createRoot(document.getElementById("root")!).render(<JoinForm onJoin={()=>location.assign("/")}/>);

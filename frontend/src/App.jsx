import HomePage from "./pages/HomePage";
import SessionPage from "./pages/SessionPage";
import ResultPage from "./pages/ResultPage";
import { useState, useEffect } from "react";


export default function App() {
const [path, setPath] = useState(window.location.pathname);
useEffect(() => {
const pop = () => setPath(window.location.pathname);
window.addEventListener("popstate", pop);
return () => window.removeEventListener("popstate", pop);
}, []);


function navigate(to, newWindow = false) {
if (newWindow) window.open(to, "_blank");
else {
window.history.pushState({}, "", to);
window.dispatchEvent(new Event("popstate"));
}
}
const parts = path.split("/").filter(Boolean);
if (parts.length === 0) return <HomePage navigate={navigate} />;
if (parts[0] === "session" && parts[1]) return <SessionPage id={parts[1]} navigate={navigate} />;
if (parts[0] === "result" && parts[1]) return <ResultPage id={parts[1]} navigate={navigate} />;
return <HomePage navigate={navigate} />;
}
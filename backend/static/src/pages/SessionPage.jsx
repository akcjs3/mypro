import { useEffect, useState } from "react";
import { api } from "../api/mockApi";
import Card from "../components/Card";


export default function SessionPage({ id, navigate }) {
const [remaining, setRemaining] = useState(null);
const [status, setStatus] = useState("running");


useEffect(() => {
const timer = setInterval(async () => {
const res = await api.getStatus(id);
setRemaining(res.remainingMs);
setStatus(res.status);
if (res.status === "finished") navigate(`/result/${id}`, true);
}, 1000);
return () => clearInterval(timer);
}, [id]);


async function stopNow() {
await api.stopSession({ sessionId: id });
navigate(`/result/${id}`, true);
}


function fmtMs(ms) {
const sec = Math.floor(ms / 1000);
const m = Math.floor(sec / 60).toString().padStart(2, "0");
const s = (sec % 60).toString().padStart(2, "0");
return `${m}:${s}`;
}
return (
<div className="grid md:grid-cols-2 gap-6 items-start">
<Card>
<h2 className="text-xl font-semibold mb-3">세션 진행 중</h2>
<div className="text-6xl font-bold tabular-nums">{remaining ? fmtMs(remaining) : "--:--"}</div>
<button onClick={stopNow} className="mt-6 px-5 py-2.5 rounded-xl border border-gray-900 hover:bg-gray-900 hover:text-white">종료</button>
</Card>


<Card>
<div className="text-sm text-gray-600">상태: {status}</div>
</Card>
</div>
);
}
import { useState } from "react";
import { api } from "../api/mockApi";
import { LABELS, COLORS, labelHuman } from "../utils/constants";
import Card from "../components/Card";
import Pill from "../components/Pill";
export default function HomePage({ navigate }) {
const [duration, setDuration] = useState(30);
const [loading, setLoading] = useState(false);


async function onStart() {
setLoading(true);
const { sessionId } = await api.startSession({ durationMin: duration });
navigate(`/session/${sessionId}`);
setLoading(false);
}
return (
<div className="grid md:grid-cols-2 gap-6 items-start">
<Card>
<h2 className="text-xl font-semibold mb-3">분석 시간 선택</h2>
<div className="flex gap-2">
{[30, 60, 120].map((m) => (
<button
key={m}
onClick={() => setDuration(m)}
className={`px-4 py-2 rounded-xl border ${duration === m ? "border-gray-900" : "border-gray-300 hover:border-gray-500"}`}
>
{m}분
</button>
))}
</div>
<div className="mt-6">
<button onClick={onStart} disabled={loading} className="px-5 py-2.5 rounded-xl bg-gray-900 text-white">
{loading ? "시작 중..." : "분석 시작"}
</button>
</div>
</Card>


<Card>
<h3 className="font-semibold mb-2">라벨 & 색상</h3>
<div className="flex flex-wrap gap-2">
{LABELS.map((k) => (
<Pill key={k} color={COLORS[k]} label={`${labelHuman(k)} (${k})`} />
))}
</div>
</Card>
</div>
);
}
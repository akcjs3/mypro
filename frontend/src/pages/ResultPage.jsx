import { useEffect, useState } from "react";
import { api } from "../api/mockApi";
import { LABELS, COLORS, labelHuman } from "../utils/constants";
import Card from "../components/Card";
import TimelineChips from "../components/TimelineChips";
import Pill from "../components/Pill";


export default function ResultPage({ id, navigate }) {
const [data, setData] = useState(null);


useEffect(() => {
api.getResult(id).then(setData);
}, [id]);


if (!data) return <Card>결과 로딩 중...</Card>;
const pie = Object.entries(data.overall.probs).map(([k, v]) => ({ label: labelHuman(k), value: v }));


return (
<div className="grid gap-6">
<Card>
<h2 className="text-xl font-semibold mb-3">Overall 결과</h2>
<div className="flex flex-wrap gap-2">
{pie.map((p) => (
<Pill key={p.label} color={COLORS[LABELS.find((k) => labelHuman(k) === p.label)]} label={`${p.label}: ${(p.value * 100).toFixed(1)}%`} />
))}
</div>
</Card>
<Card>
<h2 className="text-xl font-semibold mb-3">Timeline</h2>
<TimelineChips items={data.timeline} />
</Card>


<Card>
<button onClick={() => navigate("/", false)} className="px-4 py-2 rounded-xl border">새 세션 시작</button>
</Card>
</div>
);
}
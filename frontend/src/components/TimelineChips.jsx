import { COLORS, labelHuman } from "../utils/constants";


export default function TimelineChips({ items }) {
return (
<div className="space-y-2">
<div className="grid gap-1" style={{ gridTemplateColumns: `repeat(30, minmax(0, 1fr))` }}>
{items.map((it, i) => (
<div key={i} className="group relative h-5 rounded" style={{ background: `${COLORS[it.argmax]}66` }}>
<span className="absolute -top-7 left-1/2 -translate-x-1/2 text-[10px] bg-black text-white px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 whitespace-nowrap">
{`${Math.floor(it.window_start / 60)}:${(it.window_start % 60).toString().padStart(2, "0")} ~ ${Math.floor(it.window_end / 60)}:${(it.window_end % 60).toString().padStart(2, "0")}`} · {labelHuman(it.argmax)}
</span>
</div>
))}
</div>
</div>
);
}
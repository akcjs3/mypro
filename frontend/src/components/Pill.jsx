export default function Pill({ color, label, compact = false }) {
return (
<span
className={`inline-flex items-center ${compact ? "px-1.5 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs"} rounded-full border`}
style={{ background: `${color}12`, borderColor: `${color}33`, color }}
>
{label}
</span>
);
}
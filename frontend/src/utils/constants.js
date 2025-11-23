
export const LABELS = [
"game",
"youtube_entertain",
"youtube_music",
"study",
"sns",
"webtoon",
"other",
];


export const COLORS = {
game: "#7c4dff",
youtube_entertain: "#ff6b6b",
youtube_music: "#ffd166",
study: "#06d6a0",
sns: "#4da3ff",
webtoon: "#f78c6b",
other: "#a0aec0",
};


export function labelHuman(k) {
switch (k) {
case "game": return "게임";
case "youtube_entertain": return "유튜브(오락)";
case "youtube_music": return "유튜브/음악";
case "study": return "공부";
case "sns": return "SNS";
case "webtoon": return "웹툰";
default: return "기타";
}
}
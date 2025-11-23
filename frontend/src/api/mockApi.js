import { LABELS } from "../utils/constants";


function randId() {
return Math.random().toString(36).slice(2, 10);
}


function loadSessions() {
const raw = localStorage.getItem("ms_sessions");
return raw ? JSON.parse(raw) : {};
}
function saveSessions(s) {
localStorage.setItem("ms_sessions", JSON.stringify(s));
}
export const api = {
async startSession({ durationMin }) {
const id = randId();
const store = loadSessions();
store[id] = {
startedAt: Date.now(),
durationMs: durationMin * 60 * 1000,
status: "running",
};
saveSessions(store);
return { sessionId: id };
},


async getStatus(sessionId) {
const store = loadSessions();
const s = store[sessionId];
if (!s) return { status: "finished", remainingMs: 0 };


if (s.status === "finished") return { status: "finished", remainingMs: 0 };


const elapsed = Date.now() - s.startedAt;
const remaining = s.durationMs - elapsed;
if (remaining <= 0) {
s.status = "finished";
saveSessions(store);
return { status: "finished", remainingMs: 0 };
}
return { status: "running", remainingMs: remaining };
},
async stopSession({ sessionId }) {
const store = loadSessions();
if (store[sessionId]) {
store[sessionId].status = "finished";
saveSessions(store);
}
return { ok: true };
},


async getResult(sessionId) {
const store = loadSessions();
if (!store[sessionId]) {
return {
overall: { probs: { study: 0.3, youtube_entertain: 0.4, other: 0.3 }, predicted_activity: "youtube_entertain" },
timeline: [],
meta: { window_sec: 30, windows: 60 },
};
}
// 더미 데이터 생성
const probs = {
game: 0.12,
youtube_entertain: 0.28,
youtube_music: 0.18,
study: 0.24,
sns: 0.08,
webtoon: 0.04,
other: 0.06,
};
return {
overall: { probs, predicted_activity: "youtube_entertain" },
timeline: Array.from({ length: 20 }, (_, i) => ({
window_start: i * 30,
window_end: (i + 1) * 30,
probs,
argmax: "study",
})),
meta: { window_sec: 30, windows: 20 },
};
},
};
document.addEventListener("DOMContentLoaded", async () => {
  const today = new Date();
  document.getElementById("ranking-date").textContent =
    `${today.getFullYear()}-${today.getMonth() + 1}-${today.getDate()}`;

  const user = getCurrentUser();

  try {
    const res = await fetch("/api/ranking/today");
    const data = await res.json();
    if (!res.ok || !data.ok) return;

    const list = data.ranking || [];

    // podium
    document.getElementById("rank-1").textContent = list[0]?.user || "-";
    document.getElementById("rank-2").textContent = list[1]?.user || "-";
    document.getElementById("rank-3").textContent = list[2]?.user || "-";

    // 내 랭킹 계산 (수정 적용)
    if (user) {
      const myIdx = list.findIndex(v => v.user_id == user.userId);
      document.getElementById("my-rank").textContent =
        myIdx >= 0 ? `${myIdx + 1}위` : "순위 없음";
    }
  } catch (err) {
    console.error(err);
  }
});

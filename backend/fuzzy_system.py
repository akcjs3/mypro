import re
from typing import Dict, Any

LABELS = [
    "game", "other", "sns", "study", "webtoon",
    "youtube-ent", "youtube-music", "ott"
]

# ---- 키워드 세트 (모두 복원 + 확장) ---- #
MUSIC_KEYWORDS = [
    "youtube music", "spotify", "soundcloud", "melon", "genie", "bugs",
    "apple music", "flo", "vibe", "bandcamp", "beatport", "deezer",
    "music video", "mv", "노래", "음악", "재생", "playlist", "뮤직", "가요",
    "song", "track", "album", "뮤비", "뮤직비디오"
]

OTT_KEYWORDS = [
    "netflix", "tving", "wavve", "watcha", "disney+", "disney plus",
    "prime video", "hbo", "seezn", "serieson", "ott", "drama", "movie"
]

WEBTOON_KEYWORDS = [
    "webtoon", "toon", "naver webtoon", "kakao page", "lezhin", "manhwa",
    "만화", "웹툰", "코믹", "comic"
]

SNS_KEYWORDS = [
    "instagram", "facebook", "twitter", "x.com", "tiktok", "threads",
    "카카오톡", "discord", "reddit", "sns", "social"
]

GAME_KEYWORDS = [
    "game", "steam", "league of legends", "valorant", "overwatch",
    "minecraft", "roblox", "battlegrounds", "pubg", "롤", "게임"
]

STUDY_KEYWORDS = [
    "vscode", "pycharm", "colab", "notion", "word", "powerpoint", "excel",
    "visual studio", "devtools", "stackoverflow", "lecture", "강의", "공부",
    "edu", "study", "research", "document", "code"
]

# ---- 타이틀 기반 판별 ---- #
def match_keywords(title: str, keywords: list) -> bool:
    if not title:
        return False
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in keywords)

def get_label_from_title(title: str) -> str:
    if match_keywords(title, MUSIC_KEYWORDS): return "youtube-music"
    if match_keywords(title, OTT_KEYWORDS): return "ott"
    if match_keywords(title, WEBTOON_KEYWORDS): return "webtoon"
    if match_keywords(title, SNS_KEYWORDS): return "sns"
    if match_keywords(title, GAME_KEYWORDS): return "game"
    if match_keywords(title, STUDY_KEYWORDS): return "study"
    return None

# ---- 퍼지 로직 메인 ---- #
def apply_fuzzy_rules(result: Dict[str, Any]) -> str:
    scores = {label: 0.0 for label in LABELS}

    input_res = result.get("input", {}) or {}
    window_res = result.get("window", {}) or {}
    screen_res = result.get("screen", {}) or {}
    selected_task = result.get("selected_task")

    key_count = int(input_res.get("key_count", 0) or 0)
    mouse_count = int(input_res.get("mouse_count", 0) or 0)
    total_input = key_count + mouse_count

    window_label = window_res.get("top_label")
    raw_title = window_res.get("title") or ""
    screen_top = (
        screen_res.get("screen_top")
        or screen_res.get("screen_pred")
        or screen_res.get("top_label")
    )
    screen_probs = screen_res.get("screen_probs") or screen_res.get("probs") or {}

    # 기본값 설정
    for k, v in screen_probs.items():
        if k in scores:
            scores[k] = float(v)

    # ----- 1. 타이틀 기반 우선 판별 ----- #
    title_label = get_label_from_title(raw_title)
    if title_label:
        # 타이틀이 확실하면 그 라벨을 강하게 부스트하고 다른 건 약화
        for k in scores:
            scores[k] *= 0.3
        scores[title_label] = max(0.9, scores.get(title_label, 0.9))

    # ----- 2. 입력량 기반 보정 ----- #
    input_ratio = total_input / max(1, input_res.get("session_duration_sec", 1))
    if input_ratio < 0.05:  # 거의 입력 없음
        scores["youtube-music"] += 0.3  # 수동적 활동 (음악, 영상 등)
        scores["youtube-ent"] += 0.15
    elif input_ratio > 0.8:  # 적극적 활동(입력 많음)
        scores["study"] += 0.15
        scores["game"] += 0.12   # 기존보다 살짝 상향
        scores["sns"]  += 0.05   # 카톡/DM 같은 입력 많은 SNS 보정

    # ✅ 게임 특성(키+마우스 동시 고입력) 보정
    # 마우스 클릭/이동이 키 입력보다 확실히 많은 패턴이면 게임 쪽 추가 가산
    if mouse_count > key_count * 1.2 and total_input > 50:
        scores["game"] += 0.08
        
        if selected_task == "game":
            if input_ratio > 0.6:
                scores["game"] += 0.2
        
        if mouse_count > key_count * 1.2 or mouse_count > 200:
            scores["game"] += 0.1
        elif selected_task == "sns":
            if input_ratio > 0.4:
                scores["sns"] += 0.15


    # ----- 3. 사용자가 선택한 라벨 보정 ----- #
    if selected_task and selected_task in scores:
        scores[selected_task] += 0.25
    if selected_task == "study":
             scores["study"] += 0.05

    # ----- 4. window_label과 screen_top 병합 ----- #
    for lbl in [window_label, screen_top]:
        if lbl in scores:
            scores[lbl] += 0.2
            if lbl == "study":
                scores["study"] += 0.05  # ✅ study만 추가 가중

    # ----- 5. OTT + Music 우선 보정 ----- #
    if match_keywords(raw_title, OTT_KEYWORDS):
        scores["youtube-ent"] += 0.3
    if match_keywords(raw_title, MUSIC_KEYWORDS) and total_input < 20:
        for k in scores: scores[k] *= 0.2
        scores["youtube-music"] = 1.0

    # ----- 6. 정규화 후 최종 결정 ----- #
    total_score = sum(scores.values())
    if total_score == 0:
        total_score = 1
    for k in scores:
        scores[k] /= total_score

    final_label = max(scores, key=scores.get)

    print("[Fuzzy] scores =", scores, "=> final_label =", final_label)
    return final_label

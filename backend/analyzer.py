# analyzer.py
import os
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import load_img, img_to_array

from fuzzy_system import apply_fuzzy_rules


# =======================================================
# ✅ 경로 설정 (backend 기준으로 안전하게)
# - 기존 코드가 "../data/..." 로 잡혀서 backend 밖을 봐버림
# - 현재 로거들이 backend/data/* 에 저장하므로 그쪽을 1순위로 사용
# =======================================================
BASE_DIR = Path(__file__).resolve().parent

# backend/data
DATA_DIR = (BASE_DIR / "data").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 혹시 예전 구조(backend/../data)도 남아있다면 보조로 탐색
LEGACY_DATA_DIR = (BASE_DIR / ".." / "data").resolve()

SESSION_LOG_DIR = DATA_DIR / "session_logs"
SESSION_LOG_DIR.mkdir(parents=True, exist_ok=True)

SCREENS_DIR = DATA_DIR / "screens"
SCREENS_DIR.mkdir(parents=True, exist_ok=True)

WINDOW_CSV = DATA_DIR / "window_log.csv"
INPUT_CSV = DATA_DIR / "input_log.csv"
PROCESS_CSV = DATA_DIR / "process_log.csv"
SCREEN_CSV = DATA_DIR / "screen_log.csv"

ANALYZER_BASE_DIR = Path(__file__).resolve().parent
ANALYZER_DATA_DIR = (ANALYZER_BASE_DIR / "data").resolve()
ANALYZER_SESSION_LOG_DIR = ANALYZER_DATA_DIR / "session_logs"
ANALYZER_SESSION_LOG_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------------
# 🔥 1. TITLE KEYWORDS (모든 라벨 키워드) — 절대 삭제/수정 안 함
# -------------------------------------------------------
TITLE_KEYWORDS = {
    "game": ["game", "steam", "league of legends", "lol", "valorant", "overwatch", "maplestory", "lostark", "테트리스", "게임", "칼"],
    "study": ["ppt", "pdf", "study", "homework", "report", "notion", "stackoverflow", "postech", "lecture", "visual studio code", "vscode", "code.exe",
        "pycharm", "intellij", "android studio",
        "jupyter", "colab", "terminal", "cmd", "powershell","inflearn", "인프런", "강의", "학습 페이지", "lecture video", "중부대학교", "lms", "강좌"],
    "webtoon": ["webtoon", "naver webtoon", "kakao webtoon", "toon","만화", "웹툰", "뉴토끼"],
    "sns": ["instagram", "insta", "facebook", "twitter", "tiktok", "reels", "shorts", "인스타", "카카오톡"],
    "youtube-ent": ["youtube", "yt", "tv", "netflix", "tving", "watching", "drama"],
    "youtube-music": ["music", "song", "lyrics", "audio", "mv", "playlist", "melody", "뮤직", "가사"]
}

# -------------------------------------------------------
# 🔥 2. MUSIC KEYWORDS — 절대 줄이지 않음
# -------------------------------------------------------
MUSIC_KEYWORDS = [
    "music", "song", "lyrics", "lyric", "audio", "mv", "playlist", "melody",
    "가사", "노래", "뮤직", "audio only", "official audio"
]

# -------------------------------------------------------
# 🔥 음악 제목 판별 함수
# -------------------------------------------------------
def is_music_title(title: str) -> bool:
    if not title:
        return False
    title_lower = title.lower()
    for kw in MUSIC_KEYWORDS:
        if kw.lower() in title_lower:
            return True
    return False

# -------------------------------------------------------
# 🔥 TITLE 기반 라벨
# -------------------------------------------------------
def apply_keyword_priority(window_titles: list) -> str | None:
    if not window_titles:
        return None

    title_str = " ".join(t.lower() for t in window_titles if isinstance(t, str))

    for label, keywords in TITLE_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in title_str:
                return label

    return None


# -------------------------------------------------------
# 🔥 단일 제목 -> 키워드 라벨 추정 (fallback용)
# -------------------------------------------------------
def label_from_title(title: str) -> str:
    if not title:
        return "other"
    tl = title.lower()
    for label, keywords in TITLE_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in tl:
                return label
    return "other"


# -------------------------------------------------------
# 🔥 Sequence-based 비율 계산
# -------------------------------------------------------
def compute_sequence_distribution(window_labels: list, session_sec: float):
    if not window_labels:
        return {}

    per = {}
    total = len(window_labels)
    for w in window_labels:
        per[w] = per.get(w, 0) + 1

    return {k: (v / total) * 100 for k, v in per.items()}


# =======================================================
# ✅ CNN 모델 로드 (경로 여러 개 시도)
# =======================================================
LABELS = ["game", "other", "sns", "study", "webtoon", "youtube-ent", "youtube-music"]

def _resolve_cnn_model_path() -> Optional[str]:
    candidates = [
        str(BASE_DIR / "monitor_model.h5"),          # backend/monitor_model.h5
        str(BASE_DIR / "models" / "cnn_model.h5"),   # backend/models/cnn_model.h5 (예전)
        str(LEGACY_DATA_DIR / "models" / "cnn_model.h5"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

CNN_MODEL_PATH = _resolve_cnn_model_path()
cnn_model = None
if CNN_MODEL_PATH:
    try:
        cnn_model = load_model(CNN_MODEL_PATH)
        print(f"[Analyzer] CNN 모델 로드 성공: {CNN_MODEL_PATH}")
    except Exception as e:
        print("[Analyzer] CNN 모델 로드 실패:", e)
        cnn_model = None
else:
    print("⚠ CNN 모델을 찾지 못했습니다.")


# -------------------------------------------------------
# 🔥 SCREEN 폴더에서 이미지 수집 + CNN 예측
# -------------------------------------------------------
def analyze_screen_images(session_id: str): # -> Tuple[Dict[str, float], Optional[str]]:
    """
    해당 session_id에 해당하는 스샷들만 모아서 CNN 예측.
    - screen_capture.py 파일명에 session_id 포함됨.
    """
    if cnn_model is None:
        return ({label: 0.0 for label in LABELS}, None)

    folder = str(SCREENS_DIR)
    if not os.path.isdir(folder):
        return ({label: 0.0 for label in LABELS}, None)

    # 세션 id 포함된 스크린샷만
    files = [
        f for f in os.listdir(folder)
        if session_id in f and f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]
    if not files:
     return ({label: 0.0 for label in LABELS}, None, 0)

    files.sort()
    recent_files = files[-8:]
 
    xs = []
    for fn in recent_files:
        p = os.path.join(folder, fn)
        try:
            img = load_img(p, target_size=(128, 128))
            arr = img_to_array(img)
            arr = np.expand_dims(arr, axis=0) / 255.0
            xs.append(arr)
        except Exception:
            continue

    if not xs:
        return ({label: 0.0 for label in LABELS}, None, len(recent_files))

    X = np.vstack(xs)
    logits = cnn_model.predict(X, verbose=0)
    probs = logits.mean(axis=0)
    probs = probs / (probs.sum() + 1e-8)

    probs_dict = {label: float(v) for label, v in zip(LABELS, probs)}
    top_label = LABELS[int(np.argmax(probs))]

    return probs_dict, top_label, len(recent_files)


# =======================================================
# ✅ CSV 로부터 세션 로그 재구성 (json 없을 때 fallback)
# =======================================================
def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def _filter_by_session(rows: List[Dict[str, str]], session_id: str) -> List[Dict[str, str]]:
    return [r for r in rows if str(r.get("session_id")) == str(session_id)]

def _parse_datetime_safe(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def build_logs_from_csv(session_id: str) -> Dict:
    """
    window_log.csv / input_log.csv / process_log.csv / screen_log.csv에서
    해당 session_id만 골라 logs 구조 생성.
    """
    logs = {
        "session_id": session_id,
        "window": [],
        "input": [],
        "process": [],
        "screen": [],
        "idle_sec": 0,
        "session_start": None,
        "session_end": None,
    }

    # window
    w_rows = _filter_by_session(_read_csv_rows(WINDOW_CSV), session_id)
    for r in w_rows:
        logs["window"].append({
            "timestamp": r.get("timestamp"),
            "title": r.get("window_title") or "",
            "process_name": r.get("process_name") or "",
            "exe_path": r.get("exe_path") or "",
            "label": label_from_title(r.get("window_title") or ""),
        })

    # input
    i_rows = _filter_by_session(_read_csv_rows(INPUT_CSV), session_id)
    for r in i_rows:
        logs["input"].append({
            "timestamp": r.get("timestamp"),
            "event_type": r.get("event_type"),
            "key": r.get("key"),
            "button": r.get("button"),
        })

    # process
    p_rows = _filter_by_session(_read_csv_rows(PROCESS_CSV), session_id)
    for r in p_rows:
        logs["process"].append(r)

    # screen
    s_rows = _filter_by_session(_read_csv_rows(SCREEN_CSV), session_id)
    for r in s_rows:
        logs["screen"].append(r)

    # session start/end 추정
    all_ts = []
    for r in (w_rows + i_rows + s_rows + p_rows):
        dt = _parse_datetime_safe(r.get("timestamp", ""))
        if dt:
            all_ts.append(dt)

    if all_ts:
        logs["session_start"] = min(all_ts).isoformat()
        logs["session_end"] = max(all_ts).isoformat()

    return logs


# =======================================================
# ✅ 메인 분석 함수
# =======================================================
MIN_SESSION_SEC = 30  # 서버와 맞춰둠

def analyze_and_save(
    session_id: str,
    user_id: Optional[int] = None,
    selected_task: Optional[str] = None,
    usage_index: Optional[int] = None,
    **kwargs
):
    """
    server.py에서 호출:
      analyze_and_save(session_id=..., user_id=..., selected_task=..., usage_index=...)

    - 기존 기능 최대한 보존 + csv fallback + 프론트 필드 보강
    """

    # ---------------------------------------------------
    # 1) 세션 로그 json 로드 시도 (없으면 csv fallback)
    # ---------------------------------------------------
    json_path = SESSION_LOG_DIR / f"{session_id}.json"
    logs = None
    if json_path.exists():
        try:
            with json_path.open("r", encoding="utf-8") as f:
                logs = json.load(f)
        except Exception:
            logs = None

    if logs is None:
        logs = build_logs_from_csv(session_id)

    # ---------------------------------------------------
    # 2) 세션 시간 계산
    # ---------------------------------------------------
    start_dt = _parse_datetime_safe(logs.get("session_start") or "")
    end_dt = _parse_datetime_safe(logs.get("session_end") or "")

    if start_dt and end_dt:
        session_sec = max((end_dt - start_dt).total_seconds(), 1.0)
    else:
        # 로그가 거의 없을 때 최소값
        session_sec = 1.0

    # ---------------------------------------------------
    # 3) window titles/labels
    # ---------------------------------------------------
    
    window_logs = logs.get("window", [])
    
    filtered_logs = []
    for w in window_logs:
        title = (w.get("title") or "").strip()
        tl = title.lower()
        if title == "":
            continue
        
        if "작업 전환" in title or "task switching" in tl:
            continue
        if "monitor sketcher" in tl:
            continue
        filtered_logs.append(w)  
        
        window_logs = filtered_logs
    window_titles = [w.get("title", "") for w in window_logs]
    window_labels = [w.get("label", "other") for w in window_logs]

    # keyword 기반 우선 라벨
    keyword_label = apply_keyword_priority(window_titles)

    # ---------------------------------------------------
    # 4) input count
    # ---------------------------------------------------
    input_logs = logs.get("input", [])
    key_count = 0
    mouse_count = 0
    for r in input_logs:
        et = (r.get("event_type") or "").lower()
        if et == "key_press":
            key_count += 1
        elif et in ("mouse_down", "mouse_up", "mouse_scroll"):
            mouse_count += 1

    # ✅ (기존에 쓰던 input_ratio 누락 버그 수정)
    total_input = key_count + mouse_count
    input_ratio = key_count / total_input if total_input > 0 else 0.0

    # ---------------------------------------------------
    # 5) sequence distribution
    # ---------------------------------------------------
    seq_percent = compute_sequence_distribution(window_labels, session_sec)
    seq_ratio = {k: v / 100.0 for k, v in seq_percent.items()}

    # ---------------------------------------------------
    # 6) screen(CNN) 분석
    # ---------------------------------------------------
    screen_probs, screen_top, capture_count = analyze_screen_images(session_id)

    # ---------------------------------------------------
    # 7) fuzzy rules
    # ---------------------------------------------------
    last_window_label = window_labels[-1] if window_labels else None

    # ---- 퍼지 시스템 적용(✅ fuzzy_system.py 시그니처에 맞게 dict 1개만 전달) ---- #
    fuzzy_input = {
        "input": {
            "key_count": key_count,
            "mouse_count": mouse_count,
            "session_duration_sec": session_sec
        },
        "window": {
            # fuzzy_system은 top_label, title을 봄
            "top_label": last_window_label,
            "title": window_titles[-1] if window_titles else "",
            "window_labels": window_labels
        },
        "screen": {
            # fuzzy_system은 screen_top / screen_probs를 봄
            "screen_top": screen_top,
            "screen_probs": screen_probs
        },
        "selected_task": selected_task,
    }

    final_label = apply_fuzzy_rules(fuzzy_input)

    # ---------------------------------------------------
    # 8) idle / focus 계산
    # ---------------------------------------------------
    idle_sec = logs.get("idle_sec", 0) or 0
    idle_ratio = idle_sec / session_sec if session_sec > 0 else 0.0

    focus_ratio = seq_ratio.get(selected_task, 0.0)
    focus_percent = seq_percent.get(selected_task, 0.0)

    # ---------------------------------------------------
    # 9) 결과 구성 (프론트에서 쓰는 필드 포함)
    # ---------------------------------------------------
    result = {
        "session_id": session_id,
        "user_id": user_id,
        "usage_index": usage_index,
        "selected_task": selected_task,
        "session_start": logs.get("session_start"),
        "session_end": logs.get("session_end"),

        "final_label": final_label,   # ✅ test.html에서 필요
        "predicted": final_label,     # server.py에서 쓰던 이름 유지

        # ✅ 원그래프용
        "activity_distribution": {
            "percent": seq_percent,
            "ratio": seq_ratio,
        },

        # ✅ window 상세
        "window": {
            "window_titles": window_titles,
            "window_labels": window_labels,
            "distribution": {
                "percent": seq_percent,
                "ratio": seq_ratio,
            },
        },

        # ✅ screen 상세
        "screen": {
            "screen_probs": screen_probs,
            "screen_top": screen_top,
            "capture_count": capture_count,   # ✅ 프론트용
            "num_captures": capture_count,    # ✅ alias
            "total_captures": capture_count,  # ✅ alias

        },

        # ✅ 입력/참여도
        "input": {
            "key_count": key_count,
            "mouse_count": mouse_count,
        },

        "engagement": {
            "idle_percent": idle_ratio * 100,
            "idle_ratio": idle_ratio,
            "idle_time_sec": idle_sec,
            "input_per_min": total_input / max(session_sec / 60.0, 1.0),
            "session_duration_sec": session_sec,
            "total_input": total_input,
        },

        # ✅ process count (있으면)
        "process": {
            "process_count": len(logs.get("process", []))
        },

        # ✅ 화면/서버가 쓰던 필드 일부도 유지
        "focus_ratio": focus_ratio,
        "focus_percent": focus_percent,
        "inputPerMin": total_input / max(session_sec / 60.0, 1.0),
    }

    # ---------------------------------------------------
    # 10) 저장
    # ---------------------------------------------------
    out_path = SESSION_LOG_DIR / f"{session_id}_analysis.json"
    try:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print("[Analyzer] 분석 결과 저장 실패:", e)

    return result


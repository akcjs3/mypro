# backend/session_meta.py
import csv
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_META_PATH = os.path.join(BASE_DIR, "..", "data", "session_meta.csv")

SESSION_META_HEADER = [
    "session_id",
    "user_id",
    "label",
    "is_first",
    "started_at",
    "ended_at",
    "created_at",
]


def _ensure_meta_file_exists():
    """session_meta.csv 가 없으면 헤더만 있는 파일로 생성."""
    os.makedirs(os.path.dirname(SESSION_META_PATH), exist_ok=True)

    if not os.path.exists(SESSION_META_PATH):
        with open(SESSION_META_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(SESSION_META_HEADER)


def _read_all_sessions() -> List[Dict[str, str]]:
    """session_meta.csv 전체를 리스트[dict]로 읽기."""
    _ensure_meta_file_exists()
    rows: List[Dict[str, str]] = []
    with open(SESSION_META_PATH, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def _write_all_sessions(rows: List[Dict[str, str]]):
    """리스트[dict] 전체를 session_meta.csv 에 다시 쓰기."""
    _ensure_meta_file_exists()
    with open(SESSION_META_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SESSION_META_HEADER)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _generate_session_id(user_id: int) -> str:
    """user_id + 현재 시각으로 session_id 생성."""
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    return f"{user_id}_{now}"


def start_session(user_id: int, label: str) -> str:
    """
    새 세션 시작.
    - session_id 생성
    - is_first: 이 user_id로 기존 세션이 하나도 없으면 1, 아니면 0
    - started_at / created_at 기록
    - ended_at 은 "" 로 비워둠
    """
    _ensure_meta_file_exists()

    rows = _read_all_sessions()
    user_sessions = [r for r in rows if str(r.get("user_id")) == str(user_id)]
    is_first = 1 if len(user_sessions) == 0 else 0

    session_id = _generate_session_id(user_id)
    now_iso = datetime.utcnow().isoformat(timespec="seconds")

    new_row = {
        "session_id": session_id,
        "user_id": str(user_id),
        "label": label,
        "is_first": str(is_first),
        "started_at": now_iso,
        "ended_at": "",
        "created_at": now_iso,
    }

    rows.append(new_row)
    _write_all_sessions(rows)

    return session_id


def end_session(session_id: str):
    """세션 종료 시각 기록."""
    rows = _read_all_sessions()
    now_iso = datetime.utcnow().isoformat(timespec="seconds")
    changed = False

    for r in rows:
        if r.get("session_id") == session_id and not r.get("ended_at"):
            r["ended_at"] = now_iso
            changed = True
            break

    if changed:
        _write_all_sessions(rows)


def get_session_meta(session_id: str) -> Optional[Dict[str, Any]]:
    """특정 session_id 의 메타 정보 반환."""
    rows = _read_all_sessions()
    for r in rows:
        if r.get("session_id") == session_id:
            return r
    return None


def get_latest_session() -> Optional[Dict[str, Any]]:
    """가장 최근(시작 시각 기준) 세션 메타 반환."""
    rows = _read_all_sessions()
    if not rows:
        return None

    rows_sorted = sorted(
        rows,
        key=lambda r: r.get("started_at") or "",
    )
    return rows_sorted[-1]

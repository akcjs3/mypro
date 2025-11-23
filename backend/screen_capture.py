# screen_capture.py
import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Dict

import pyautogui
import threading

BASE_DIR = Path(__file__).resolve().parent

# ✅ (중요) backend/data 로 통일
DATA_DIR = (BASE_DIR / "data").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

SCREENS_DIR = DATA_DIR / "screens"
SCREENS_DIR.mkdir(parents=True, exist_ok=True)

SCREEN_CSV = DATA_DIR / "screen_log.csv"

CSV_HEADER = [
    "timestamp",
    "user_id",
    "session_id",
    "usage_index",
    "task_label",
    "filename",
]


def _ensure_header(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)


def start_screen_capture(
    session_meta: Dict,
    stop_event: threading.Event,
    interval: float = 2.0,
):
    """
    일정 간격으로 전체 화면을 캡쳐해서 저장.
    - 파일명에 user_id, session_id, usage_index를 포함.
    - 별도 screen_log.csv에 메타 기록.
    """
    _ensure_header(SCREEN_CSV)

    user_id = session_meta.get("user_id")
    session_id = session_meta.get("session_id")
    usage_index = session_meta.get("usage_index", 0)
    task_label = session_meta.get("task", "")

    base_prefix = f"user{user_id}_sess{session_id}_run{usage_index}"

    f = SCREEN_CSV.open("a", newline="", encoding="utf-8")
    writer = csv.writer(f)

    idx = 0

    # ✅ pyautogui 안전장치 해제(모서리 이동시 예외 방지)
    pyautogui.FAILSAFE = False

    print("[screen_capture] start:", session_meta)

    while not stop_event.is_set():
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"{base_prefix}_{ts}_{idx:04d}.png"
        save_path = SCREENS_DIR / filename

        try:
            img = pyautogui.screenshot()
            img.save(save_path)

            writer.writerow(
                [
                    datetime.utcnow().isoformat(),
                    user_id,
                    session_id,
                    usage_index,
                    task_label,
                    filename,
                ]
            )
            f.flush()
        except Exception as e:
            print("[screen_capture] capture error:", e)

        idx += 1

        steps = int(interval / 0.1)
        for _ in range(max(1, steps)):
            if stop_event.is_set():
                break
            time.sleep(0.1)

    f.close()
    print("[screen_capture] stop")


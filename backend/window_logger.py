# window_logger.py
import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Dict

import win32gui
import win32process
import psutil
import threading

BASE_DIR = Path(__file__).resolve().parent

# ✅ (중요) backend/data 로 통일
DATA_DIR = (BASE_DIR / "data").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

WINDOW_CSV = DATA_DIR / "window_log.csv"

CSV_HEADER = [
    "timestamp",
    "user_id",
    "session_id",
    "usage_index",
    "task_label",
    "process_name",
    "window_title",
    "exe_path",
]


def _ensure_header(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)


def _get_active_window_info():
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None

        _, pid = win32process.GetWindowThreadProcessId(hwnd)

        # ✅ pid 방어 (0/음수면 무시)
        if not pid or pid <= 0:
            return None

        proc = psutil.Process(pid)
        title = win32gui.GetWindowText(hwnd)

        return {
            "process_name": proc.name(),
            "window_title": title,
            "exe_path": proc.exe(),
        }
    except Exception as e:
        print("[window_logger] get_active_window_info error:", e)
        return None


def start_window_logging(session_meta: Dict, stop_event: threading.Event, interval: float = 0.5):
    """
    현재 활성 창(포그라운드 윈도우)의 정보를 주기적으로 기록.
    """
    _ensure_header(WINDOW_CSV)

    user_id = session_meta.get("user_id")
    session_id = session_meta.get("session_id")
    usage_index = session_meta.get("usage_index", 0)
    task_label = session_meta.get("task", "")

    f = WINDOW_CSV.open("a", newline="", encoding="utf-8")
    writer = csv.writer(f)

    last_info = None

    print("[window_logger] start:", session_meta)

    while not stop_event.is_set():
        info = _get_active_window_info()
        if info and info != last_info:
            ts = datetime.utcnow().isoformat()
            writer.writerow(
                [
                    ts,
                    user_id,
                    session_id,
                    usage_index,
                    task_label,
                    info["process_name"],
                    info["window_title"],
                    info["exe_path"],
                ]
            )
            f.flush()
            last_info = info

        time.sleep(interval)

    f.close()
    print("[window_logger] stop")

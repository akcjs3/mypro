# input_logger.py
import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Dict

from pynput import keyboard, mouse
import threading

BASE_DIR = Path(__file__).resolve().parent

# ✅ (중요) backend/data 로 통일
DATA_DIR = (BASE_DIR / "data").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

INPUT_CSV = DATA_DIR / "input_log.csv"

CSV_HEADER = [
    "timestamp",
    "user_id",
    "session_id",
    "usage_index",
    "task_label",
    "event_type",
    "key",
    "button",
    "x",
    "y",
]


def _ensure_header(path: Path):
    """CSV가 없거나 비어있으면 헤더를 써준다."""
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)


def start_input_logging(session_meta: Dict, stop_event: threading.Event):
    """
    키보드/마우스 이벤트를 CSV로 기록.
    - session_meta: {user_id, session_id, usage_index, task, ...}
    - stop_event: session_logger에서 들어오는 Event
    """
    _ensure_header(INPUT_CSV)

    user_id = session_meta.get("user_id")
    session_id = session_meta.get("session_id")
    usage_index = session_meta.get("usage_index", 0)
    task_label = session_meta.get("task", "")

    f = INPUT_CSV.open("a", newline="", encoding="utf-8")
    writer = csv.writer(f)

    def log_row(event_type: str, key="", button="", x="", y=""):
        ts = datetime.utcnow().isoformat()
        writer.writerow(
            [
                ts,
                user_id,
                session_id,
                usage_index,
                task_label,
                event_type,
                str(key),
                str(button),
                x,
                y,
            ]
        )
        f.flush()

    def on_press(key):
        try:
            k = getattr(key, "char", None)
            if k is None:
                k = str(key)
            log_row("key_press", key=k)
        except Exception as e:
            print("[input_logger] on_press error:", e)

    def on_release(key):
        pass

    def on_click(x, y, button, pressed):
        try:
            etype = "mouse_down" if pressed else "mouse_up"
            log_row(etype, button=str(button), x=x, y=y)
        except Exception as e:
            print("[input_logger] on_click error:", e)

    def on_scroll(x, y, dx, dy):
        try:
            log_row("mouse_scroll", x=x, y=y)
        except Exception as e:
            print("[input_logger] on_scroll error:", e)

    print("[input_logger] start:", session_meta)

    try:
        with keyboard.Listener(on_press=on_press, on_release=on_release) as kl, \
                mouse.Listener(on_click=on_click, on_scroll=on_scroll) as ml:

            while not stop_event.is_set():
                time.sleep(0.05)

    except Exception as e:
        # ✅ 권한/후킹 문제 시 로그만 남기고 종료
        print("[input_logger] listener error:", e)

    f.close()
    print("[input_logger] stop")

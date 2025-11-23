import threading
from typing import Optional, Dict

from input_logger import start_input_logging
from window_logger import start_window_logging
from process_logger import start_process_logging
from screen_capture import start_screen_capture

_session_threads = []
_stop_event: Optional[threading.Event] = None
_session_meta: Optional[Dict] = None


def start_session_logging(user_id: int, session_id: str, usage_index: int, task: str):
    """
    한 번의 검사 세션을 시작할 때 호출.
    - user_id: users 테이블의 PK
    - session_id: 고유 세션 ID
    - usage_index: 이 유저의 n번째 검사
    - task: 사용자가 선택한 작업(label)
    """
    global _stop_event, _session_threads, _session_meta

    # 혹시 기존 세션이 살아있으면 정리
    if _stop_event is not None:
        stop_session_logging()

    _stop_event = threading.Event()
    _session_meta = {
        "user_id": user_id,
        "session_id": session_id,
        "usage_index": usage_index,
        "task": task,
    }

    print(f"[SessionLogger] 세션 시작: {_session_meta}")

    # 각 로거 스레드 생성
    t1 = threading.Thread(
        target=start_input_logging,
        args=(_session_meta, _stop_event),   # ✅ session_meta dict 넘김
        daemon=True,
    )

    t2 = threading.Thread(
        target=start_window_logging,
        args=(_session_meta, _stop_event),   # ✅
        daemon=True,
    )

    t3 = threading.Thread(
        target=start_process_logging,
        args=(session_id, _stop_event),      # ✅ process_logger는 session_id만 필요
        daemon=True,
    )

    t4 = threading.Thread(
        target=start_screen_capture,
        args=(_session_meta, _stop_event),   # ✅
        daemon=True,
    )

    _session_threads = [t1, t2, t3, t4]

    for t in _session_threads:
        t.start()

    print(f"[SessionLogger] 스레드 {len(_session_threads)}개 시작 완료.")


def stop_session_logging():
    """세션 종료"""
    global _stop_event, _session_threads, _session_meta

    if _stop_event is None:
        print("[SessionLogger] 종료 요청 무시: 시작된 세션 없음")
        return None

    print("[SessionLogger] 세션 종료 중…")
    _stop_event.set()

    for t in _session_threads:
        if t.is_alive():
            t.join()

    print("[SessionLogger] 스레드 종료 완료.")

    ended_meta = dict(_session_meta) if _session_meta else None

    _stop_event = None
    _session_threads = []
    _session_meta = None

    return ended_meta

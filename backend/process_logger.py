import os
import time
import csv
from datetime import datetime

import psutil

# backend 기준으로 ../data/process_log.csv 에 저장되도록 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

PROCESS_LOG_PATH = os.path.join(DATA_DIR, "process_log.csv")


def get_active_processes():
    """
    한 번 호출될 때, 현재 실행 중인 프로세스 목록을 반환.
    (디버그용 / 단발 실행용)
    """
    processes = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return processes


def _append_process_log_row(session_id: str):
    """
    현재 실행 중인 프로세스 목록을 한 번 스냅샷 찍어서
    process_log.csv 에 (여러 줄로) 추가.
    """
    # 파일이 없으면 헤더 먼저 작성
    file_exists = os.path.exists(PROCESS_LOG_PATH)

    with open(PROCESS_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "session_id", "pid", "process_name", "cpu_percent", "memory_percent"])

        now = datetime.utcnow().isoformat()

        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                writer.writerow(
                    [
                        now,
                        session_id,
                        info.get("pid"),
                        info.get("name"),
                        info.get("cpu_percent"),
                        info.get("memory_percent"),
                    ]
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # 중간에 죽은 프로세스는 무시
                continue


def start_process_logging(session_id: str, stop_event, interval: float = 2.0):
    """
    session_logger.py 에서 쓰는 백그라운드 로거 진입점.

    - session_id: 이번 검사 세션 ID
    - stop_event: threading.Event (True가 되면 루프 종료)
    - interval: 몇 초마다 프로세스 스냅샷을 찍을지 (기본 2초)
    """
    print(f"[ProcessLogger] start_process_logging: session_id={session_id}, interval={interval}s")

    while not stop_event.is_set():
        _append_process_log_row(session_id)
        # 너무 자주 찍지 않도록 interval 만큼 쉼
        stop_event.wait(interval)

    print("[ProcessLogger] stop_event 감지, 종료합니다.")


if __name__ == "__main__":
    # 단독 실행 시: 현재 프로세스 목록 한 번 출력
    active = get_active_processes()
    print(f"총 실행 중인 프로세스 수: {len(active)}")
    for p in active:
        print(p)

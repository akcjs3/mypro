import os
import csv
import time
import threading
from datetime import datetime

import psutil
import pyautogui
from pynput import keyboard, mouse

DATA_DIR = "../data"
PROCESS_CSV = os.path.join(DATA_DIR, "process_log.csv")
INPUT_CSV = os.path.join(DATA_DIR, "input_log.csv")

# ====== 공통 유틸 ======
def now_ts():
    # 날짜 포함: "YYYY-MM-DD HH:MM:SS"
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def write_csv_header_if_missing(path, header):
    ensure_data_dir()
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)

# ====== 프로세스 로거 ======
def process_logger(stop_event, interval_sec=2):
    write_csv_header_if_missing(
        PROCESS_CSV, ["time", "pid", "name", "exe", "username", "cpu_percent", "memory_mb"]
    )
    while not stop_event.is_set():
        ts = now_ts()
        rows = []
        for p in psutil.process_iter(attrs=["pid", "name", "exe", "username"]):
            try:
                cpu = p.cpu_percent(interval=None)  # non-blocking
                mem = p.memory_info().rss / (1024 * 1024)
                info = p.info
                rows.append([
                    ts,
                    info.get("pid", ""),
                    info.get("name", "") or "",
                    info.get("exe", "") or "",
                    info.get("username", "") or "",
                    round(cpu, 2),
                    round(mem, 2),
                ])
            except Exception:
                continue
        # append 한번에
        if rows:
            with open(PROCESS_CSV, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerows(rows)
        time.sleep(interval_sec)

# ====== 입력(키보드/마우스) 로거 ======
def input_logger(stop_event):
    write_csv_header_if_missing(
        INPUT_CSV, ["time", "device", "event", "detail", "x", "y"]
    )

    def write_row(device, event, detail="", x="", y=""):
        with open(INPUT_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([now_ts(), device, event, detail, x, y])
            f.flush()

    # 키보드
    def on_press(key):
        try:
            write_row("keyboard", "press", getattr(key, "char", str(key)))
        except Exception:
            write_row("keyboard", "press", str(key))

    def on_release(key):
        write_row("keyboard", "release", str(key))
        if stop_event.is_set():
            return False  # stop listener

    kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    kb_listener.start()

    # 마우스
    def on_click(x, y, button, pressed):
        write_row("mouse", "click_down" if pressed else "click_up", str(button), x, y)

    def on_scroll(x, y, dx, dy):
        write_row("mouse", "scroll", f"dx={dx},dy={dy}", x, y)

    def on_move(x, y):
        # 너무 많으면 용량 커지므로 필요 시 주석처리 가능
        # write_row("mouse", "move", "", x, y)
        pass

    ms_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll, on_move=on_move)
    ms_listener.start()

    # 종료 대기
    while not stop_event.is_set():
        time.sleep(0.2)

    kb_listener.stop()
    ms_listener.stop()
    kb_listener.join()
    ms_listener.join()

# ====== 스크린샷 로거(선택) ======
def screenshot_logger(stop_event, interval_sec=30):
    idx = 0
    while not stop_event.is_set():
        path = os.path.join(DATA_DIR, f"screenshot_{idx}.png")
        try:
            img = pyautogui.screenshot()
            img.save(path)
            print(f"[Screenshot] {path} saved")
        except Exception as e:
            print(f"[Screenshot][ERROR] {e}")
        idx += 1
        # 중간에 끊겨도 이전까지 저장된 파일은 남음
        for _ in range(interval_sec * 5):  # 0.2s * N = interval_sec
            if stop_event.is_set():
                break
            time.sleep(0.2)

# ====== 메인 ======
def main(duration_sec=2 * 60 * 60, with_screenshot=True):
    ensure_data_dir()
    print("[Init] data 폴더 준비 완료")
    print(f"[Running] 로깅 시작 (총 {duration_sec//60}분)")

    stop_event = threading.Event()

    th_proc = threading.Thread(target=process_logger, args=(stop_event, 2), daemon=True)
    th_input = threading.Thread(target=input_logger, args=(stop_event,), daemon=True)
    th_proc.start()
    th_input.start()

    th_shot = None
    if with_screenshot:
        th_shot = threading.Thread(target=screenshot_logger, args=(stop_event, 30), daemon=True)
        th_shot.start()

    # 지정 시간 대기
    t0 = time.time()
    try:
        while time.time() - t0 < duration_sec:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[Stop] 사용자 중지(Ctrl+C)")

    stop_event.set()
    th_proc.join(timeout=3)
    th_input.join(timeout=3)
    if th_shot:
        th_shot.join(timeout=3)
    print("[Done] 로깅 종료")

if __name__ == "__main__":
    main()

import os
import pandas as pd
import numpy as np


#############################################
#   🔥 세션 ID 불러오기
#############################################

def load_session_id():
    """
    서버에서 검사 종료 시 기록되는
    data/current_session_id.txt 에서 session_id 읽기
    """
    path = "data/current_session_id.txt"
    if not os.path.exists(path):
        raise FileNotFoundError("[FeatureExtractor] current_session_id.txt 없음")

    with open(path, "r") as f:
        return f.read().strip()


#############################################
#   🔥 세션별 raw 파일 경로 세팅
#############################################

def get_session_paths(session_id: str):
    base = "data/raw"
    return {
        "input": f"{base}/{session_id}_input.csv",
        "window": f"{base}/{session_id}_window.csv",
        "process": f"{base}/{session_id}_process.csv",
    }


#############################################
#   🔥 입력 특징 추출 (키보드 / 마우스)
#############################################

def extract_input_features(csv_path: str):
    if not os.path.exists(csv_path):
        return {
            "key_per_sec": 0,
            "mouse_per_sec": 0,
            "total_keys": 0,
            "total_mouse": 0
        }

    df = pd.read_csv(csv_path)

    if df.empty or "timestamp" not in df.columns:
        return {
            "key_per_sec": 0,
            "mouse_per_sec": 0,
            "total_keys": 0,
            "total_mouse": 0
        }

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # 전체 시간
    total_seconds = (df["timestamp"].max() - df["timestamp"].min()).total_seconds()
    if total_seconds <= 0:
        total_seconds = 1

    key_count = df[df["event_type"] == "key"].shape[0]
    mouse_count = df[df["event_type"].isin(["mouse_click", "mouse_move", "mouse_scroll"])].shape[0]

    return {
        "key_per_sec": key_count / total_seconds,
        "mouse_per_sec": mouse_count / total_seconds,
        "total_keys": int(key_count),
        "total_mouse": int(mouse_count),
    }


#############################################
#   🔥 Window 특징 추출 (앱 사용 패턴)
#############################################

def extract_window_features(csv_path: str):
    if not os.path.exists(csv_path):
        return {"top_apps": [], "app_counts": {}}

    df = pd.read_csv(csv_path)

    if df.empty or "process_name" not in df.columns:
        return {"top_apps": [], "app_counts": {}}

    top_apps = df["process_name"].value_counts().head(5).index.tolist()
    counts = df["process_name"].value_counts().to_dict()

    return {
        "top_apps": top_apps,
        "app_counts": counts
    }


#############################################
#   🔥 Process 특징 추출
#############################################

def extract_process_features(csv_path: str):
    if not os.path.exists(csv_path):
        return {"unique_processes": 0}

    df = pd.read_csv(csv_path)

    if df.empty or "process_name" not in df.columns:
        return {"unique_processes": 0}

    unique = df["process_name"].nunique()

    return {"unique_processes": int(unique)}


#############################################
#   🔥 세션 기반 전체 feature 추출
#############################################

def extract_session_features():
    """
    🔥 server.py → analyzer.py 로 넘어가는 중간 단계
    - session_id 기반으로 raw 파일 가져옴
    """
    session_id = load_session_id()
    paths = get_session_paths(session_id)

    input_f = extract_input_features(paths["input"])
    window_f = extract_window_features(paths["window"])
    process_f = extract_process_features(paths["process"])

    features = {
        "session_id": session_id,
        "input_features": input_f,
        "window_features": window_f,
        "process_features": process_f
    }

    return features

# cnn_screen_model.py
import os
from typing import Dict, List, Optional

import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image

# ✅ train_cnn.py / monitor_model.h5에서 학습한 라벨 순서 그대로 유지 (절대 줄이지 않음)
LABELS = ["game", "other", "sns", "study", "webtoon", "youtube-ent", "youtube-music"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ✅ backend 폴더에 monitor_model.h5를 넣어둔 구조에 맞춤
MODEL_PATH = os.path.join(BASE_DIR, "monitor_model.h5")

# ✅ screen_capture.py가 저장하는 경로와 동일
SCREEN_DIR = os.path.join(BASE_DIR, ".", "data", "screens")

_model = None


def _get_model():
    """싱글톤 방식으로 CNN 모델 로드."""
    global _model
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"[cnn_screen_model] CNN 모델 파일을 찾을 수 없습니다: {MODEL_PATH}"
            )
        _model = load_model(MODEL_PATH)
        print(f"[cnn_screen_model] CNN 모델 로드 성공: {MODEL_PATH}")
    return _model


def _list_screen_files() -> List[str]:
    if not os.path.isdir(SCREEN_DIR):
        return []

    files = [
        f for f in os.listdir(SCREEN_DIR)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]
    files.sort()  # timestamp 기반 파일명이라면 시간순 정렬됨
    return files


def _load_recent_screens(n: int = 5, session_id: Optional[str] = None) -> List[str]:
    """
    data/screens 폴더에서 최근 스크린샷 경로 n개 반환.
    - session_id가 주어지면 해당 세션 스크린만 필터링.
    - 필터링 결과가 없으면 전체 최근 n개로 fallback.
    """
    files = _list_screen_files()
    if not files:
        return []

    if session_id:
        # screen_capture.py 파일명: user{uid}_sess{session_id}_run{usage}_...png
        sess_key = f"_sess{session_id}_"
        sess_files = [f for f in files if sess_key in f]
        if sess_files:
            files = sess_files  # 세션 파일이 있으면 그걸로만 사용

    recent = files[-n:]
    return [os.path.join(SCREEN_DIR, f) for f in recent]


def predict_screen_probs(n_images: int = 5, session_id: Optional[str] = None) -> Dict:
    """
    data/screens 폴더에서 최근 스크린샷 n장 읽어서
    7개 라벨에 대한 평균 확률과 top label 반환.

    반환 형태:
    {
      "probs": {label: prob, ...},
      "top_label": "study" | ... | None
    }
    """
    model = _get_model()
    paths = _load_recent_screens(n_images, session_id=session_id)

    if not paths:
        # 이미지가 없으면 “화면 신호 없음”
        return {
            "probs": {label: 0.0 for label in LABELS},
            "top_label": None,
        }

    xs = []
    for p in paths:
        try:
            # ✅ 모델 학습 input 크기 유지 (128x128)
            img = image.load_img(p, target_size=(128, 128))
            arr = image.img_to_array(img)
            arr = np.expand_dims(arr, axis=0)
            arr = arr / 255.0
            xs.append(arr)
        except Exception as e:
            print(f"[cnn_screen_model] 이미지 로드 실패: {p} ({e})")

    if not xs:
        return {
            "probs": {label: 0.0 for label in LABELS},
            "top_label": None,
        }

    X = np.vstack(xs)

    # (N, num_labels)
    logits = model.predict(X, verbose=0)
    probs = logits.mean(axis=0)

    # 안정화
    probs = probs / (probs.sum() + 1e-8)

    probs_dict = {label: float(v) for label, v in zip(LABELS, probs)}
    top_label = LABELS[int(np.argmax(probs))] if len(probs) == len(LABELS) else None

    return {
        "probs": probs_dict,
        "top_label": top_label,
    }


def predict_screen_probs_for_session(session_id: str, n_images: int = 5) -> Dict:
    """세션 전용 convenience wrapper."""
    return predict_screen_probs(n_images=n_images, session_id=session_id)


if __name__ == "__main__":
    # 간단 테스트
    try:
        out = predict_screen_probs(n_images=5)
        print(out)
    except Exception as e:
        print(e)

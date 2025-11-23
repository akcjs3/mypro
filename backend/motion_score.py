import os, glob
import cv2
import numpy as np

DATA_DIR = "../data"

def motion_score_between(imgA, imgB):
    # 그레이 변환 → 블러 → 차이 → 이진화 → 변화 비율
    A = cv2.cvtColor(imgA, cv2.COLOR_BGR2GRAY)
    B = cv2.cvtColor(imgB, cv2.COLOR_BGR2GRAY)
    A = cv2.GaussianBlur(A, (5,5), 0)
    B = cv2.GaussianBlur(B, (5,5), 0)
    diff = cv2.absdiff(A, B)
    _, th = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    changed = np.count_nonzero(th)
    total = th.size
    return changed / max(total, 1)

def compute_motion_score(sample_n=8):
    """
    data 폴더의 screenshot_*.png에서 균일 샘플을 뽑아 평균 변화율 반환(0~1).
    스크린샷 간격이 길면 sample_n을 줄이세요.
    """
    paths = sorted(glob.glob(os.path.join(DATA_DIR, "screenshot_*.png")))
    if len(paths) < 2:
        return 0.0
    # 균등 샘플
    idxs = np.linspace(0, len(paths)-1, num=min(sample_n, len(paths)), dtype=int)
    samples = [cv2.imread(paths[i]) for i in idxs]
    scores = []
    for i in range(len(samples)-1):
        if samples[i] is None or samples[i+1] is None:
            continue
        s = motion_score_between(samples[i], samples[i+1])
        scores.append(s)
    if not scores:
        return 0.0
    return float(np.mean(scores))

import os
from typing import Tuple
import numpy as np
import tensorflow as tf

def create_lstm_model(input_dim: int, num_classes: int = 5) -> tf.keras.Model:
    """
    LSTM 기반 시계열 분류 (대학원 수준: 시계열 구조 반영)
    클래스 5개: ["game","youtube","study","idle","other"]
    """
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(None, input_dim)),  # (T, F)
        tf.keras.layers.LSTM(32, return_sequences=False),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(num_classes, activation="softmax")
    ])
    model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
    return model

def soft_labels_from_probs(probs: np.ndarray) -> np.ndarray:
    """
    probs: (T, K) 각 타임스텝의 활동 확률(K=5)
    전체 시퀀스의 소프트 라벨 = 평균 확률
    """
    return probs.mean(axis=0, keepdims=True)  # (1, K)

def bootstrap_train_or_load(
    model_path="../data/lstm_model.h5",
    X_seq: np.ndarray = None,      # (1, T, F)
    Y_soft: np.ndarray = None      # (1, K)
) -> tf.keras.Model:
    """
    - 모델 파일이 있으면 로드
    - 없으면 부트스트랩(퍼지 추론 soft label)으로 짧게 학습해 저장
    """
    if os.path.exists(model_path):
        return tf.keras.models.load_model(model_path)

    # 최초 학습(부트스트랩): 데이터가 적으므로 epoch 작게
    model = create_lstm_model(input_dim=X_seq.shape[-1], num_classes=Y_soft.shape[-1])
    model.fit(X_seq, Y_soft, epochs=60, batch_size=1, verbose=0)
    model.save(model_path)
    return model

def predict_sequence(model: tf.keras.Model, X_seq: np.ndarray) -> np.ndarray:
    """
    X_seq: (1, T, F)
    반환: (T, K) 각 타임스텝의 확률(여기서는 전체 시퀀스를 하나로 예측 → 동일 확률을 T번 복제)
    """
    # 간단화: 시퀀스 단위 예측 값을 타임스텝에 동일 분배
    p = model.predict(X_seq, verbose=0)  # (1, K)
    T = X_seq.shape[1]
    return np.repeat(p, T, axis=0)       # (T, K)

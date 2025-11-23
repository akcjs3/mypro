# train_cnn.py (backend 폴더에 두고 실행)
import os
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras import layers, models

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "..", "data", "dataset")
MODEL_PATH = os.path.join(BASE_DIR, "monitor_model.h5")

LABELS = ["game", "other", "sns", "study", "webtoon", "youtube-ent", "youtube-music"]

img_size = (128, 128)
batch_size = 8

datagen = ImageDataGenerator(
    rescale=1./255,
    validation_split=0.2
)

train_gen = datagen.flow_from_directory(
    DATASET_DIR,
    target_size=img_size,
    batch_size=batch_size,
    classes=LABELS,          # 라벨 순서 고정!
    class_mode="categorical",
    subset="training"
)

val_gen = datagen.flow_from_directory(
    DATASET_DIR,
    target_size=img_size,
    batch_size=batch_size,
    classes=LABELS,
    class_mode="categorical",
    subset="validation"
)

model = models.Sequential([
    layers.Input(shape=(*img_size, 3)),
    layers.Conv2D(32, (3,3), activation="relu"),
    layers.MaxPooling2D(2,2),
    layers.Conv2D(64, (3,3), activation="relu"),
    layers.MaxPooling2D(2,2),
    layers.Conv2D(128, (3,3), activation="relu"),
    layers.MaxPooling2D(2,2),
    layers.Flatten(),
    layers.Dense(128, activation="relu"),
    layers.Dense(len(LABELS), activation="softmax")
])

model.compile(
    optimizer="adam",
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)

model.fit(
    train_gen,
    validation_data=val_gen,
    epochs=20
)

model.save(MODEL_PATH)
print("saved:", MODEL_PATH)

"""
train_cnn.py - PP-03, step 2 of 3.

Trains a small CNN that looks at one text-box crop and gives a score from 0 to 1:
how likely it is that the box holds a date. It uses models/cnn/data/crops.npz
from prepare_data.py and saves the model to models/cnn/date_cnn.keras.

Run from the project folder:
    backend/.venv/bin/python models/cnn/train_cnn.py
"""

import os

import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models

# -------------------------------------------------------------------
# SETTINGS
# -------------------------------------------------------------------
CNN_DIR = os.path.dirname(os.path.abspath(__file__))
CROPS_FILE = os.path.join(CNN_DIR, "data", "crops.npz")
MODEL_FILE = os.path.join(CNN_DIR, "date_cnn.keras")

FIRST_VALIDATION_PHOTO = 340   # photos 0-339 train the CNN, photos 340-399 check it
EPOCHS = 14                    # chosen with the validation loss, see Step 7
BATCH_SIZE = 64

# -------------------------------------------------------------------
# 1. DATA PREPARATION
# -------------------------------------------------------------------
# Step 1: Load the crops and scale every pixel from 0-255 to 0-1, as in LAB8P1.
data = np.load(CROPS_FILE)
crops = data["crops"].astype("float32") / 255.0
labels = data["labels"]
photo_numbers = data["photo_numbers"]

# Keras wants a channel dimension for gray pictures:
# (number of crops, 32, 128) becomes (number of crops, 32, 128, 1).
crops = np.expand_dims(crops, -1)

# Step 2: Split by photo, so all crops from one photo land on the same side.
# With crops of one photo on both sides, the validation scores would look
# better than they really are.
is_training = photo_numbers < FIRST_VALIDATION_PHOTO
is_validation = photo_numbers >= FIRST_VALIDATION_PHOTO
x_train = crops[is_training]
y_train = labels[is_training]
x_val = crops[is_validation]
y_val = labels[is_validation]
print("Training crops:", len(x_train), "| validation crops:", len(x_val))

# Step 3: Only about 1 training crop in 24 is a date. Without help, the CNN
# learns to always answer "not date" and still gets about 96% accuracy.
# class_weight makes each date crop count as much as about 22 not-date crops
# (the exact weight is printed below), so both groups weigh the same in total.
number_of_dates = int(y_train.sum())
number_of_not_dates = len(y_train) - number_of_dates
class_weight = {0: 1.0, 1: number_of_not_dates / number_of_dates}
print(f"Date crops in training: {number_of_dates} | weight for a date crop: {class_weight[1]:.2f}")

# -------------------------------------------------------------------
# 2. BUILD THE CNN
# -------------------------------------------------------------------
# Step 4: Fix the random start, so a rerun gives the same result.
tf.keras.utils.set_random_seed(0)

# Step 5: Two Conv2D + MaxPooling2D blocks learn the small shapes in a crop
# (digits, dots, letters). The Dense layers turn them into one score. The
# last layer uses sigmoid, so the score is between 0 (not date) and 1 (date).
model = models.Sequential([
    layers.Input(shape=(32, 128, 1)),
    layers.Conv2D(16, 3, activation="relu", padding="same"),
    layers.MaxPooling2D(2),
    layers.Conv2D(32, 3, activation="relu", padding="same"),
    layers.MaxPooling2D(2),
    layers.Flatten(),
    layers.Dense(64, activation="relu"),
    layers.Dense(1, activation="sigmoid"),
])
model.summary()

# -------------------------------------------------------------------
# 3. TRAIN
# -------------------------------------------------------------------
# Step 6: binary_crossentropy is the usual loss for a yes/no answer.
# Precision and recall show how well the date crops are found.
model.compile(
    optimizer="adam",
    loss="binary_crossentropy",
    metrics=[
        "accuracy",
        tf.keras.metrics.Precision(name="precision"),
        tf.keras.metrics.Recall(name="recall"),
    ],
)

# Step 7: Train and check on the validation photos after each epoch.
# Tuning note: the first run used 10 epochs (validation loss 0.12). A 30-epoch
# trial run, checked on the validation photos, showed the validation loss
# still falling until epoch 14 (0.07) and rising after about epoch 17, because
# the CNN starts to memorize the training crops. So training stops after 14 epochs.
model.fit(
    x_train,
    y_train,
    validation_data=(x_val, y_val),
    epochs=EPOCHS,
    batch_size=BATCH_SIZE,
    class_weight=class_weight,
)

# -------------------------------------------------------------------
# 4. CHECK AND SAVE
# -------------------------------------------------------------------
# Step 8: Score the validation crops with the final model (cut-off 0.5).
# return_dict=True gives the scores by name (a dict) instead of a list.
results = model.evaluate(x_val, y_val, verbose=0, return_dict=True)
print()
print("Validation (photos 340-399, score cut-off 0.5):")
print(f"  accuracy:  {results['accuracy']:.2f}")
print(f"  precision: {results['precision']:.2f}  (of the crops called date, how many are dates)")
print(f"  recall:    {results['recall']:.2f}  (of the date crops, how many were found)")

model.save(MODEL_FILE)
print("Saved to", MODEL_FILE)

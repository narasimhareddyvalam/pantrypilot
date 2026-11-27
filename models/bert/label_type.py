"""
label_type.py - PP-04, step 4 of 4.

find_label_type(text) gives the label type of a date (expiration, best_before,
sell_by, manufacturing or other) from the text around it, using the BERT model
that train_bert.py saved in models/bert/label_model/. The text is the date line
and its nearby lines joined with " | ", as label_text() in models/cnn/read_date.py
makes it.

Run from the project folder to try one line:
    backend/.venv/bin/python models/bert/label_type.py "2022.08.31 | Best before: | NET WT 500g"
"""

import os
import sys
import threading

import keras_hub
import numpy as np

from make_train_lines import LABEL_TYPES

# -------------------------------------------------------------------
# SETTINGS
# -------------------------------------------------------------------
BERT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BERT_DIR, "label_model")

# Load the model once, when this file starts. label_model/ is a KerasHub
# "preset": a folder with the model's settings, weights and word list, so
# loading it needs no internet.
model = keras_hub.models.BertTextClassifier.from_preset(MODEL_DIR)

# Only one line at a time goes through the model, so two scans at the same
# moment (two phones using the app) can't get in each other's way.
label_lock = threading.Lock()


# -------------------------------------------------------------------
# 1. FIND THE LABEL TYPE
# -------------------------------------------------------------------
def find_label_type(text):
    """Return (label type, how sure from 0 to 1) for the text around a date."""
    # predict_on_batch runs the model once on a list of texts (here a list of
    # one), and [0] is this text's row of 5 raw scores. Unlike predict, it
    # also works on Windows, where KerasHub has no tensorflow-text, and it is
    # much faster for a single line.
    with label_lock:
        scores = model.predict_on_batch([text])[0]

    # softmax turns the 5 raw scores into chances that add up to 1.
    # Taking away the largest score first keeps the numbers small; the
    # chances come out the same.
    chances = np.exp(scores - np.max(scores))
    chances = chances / np.sum(chances)
    best = int(np.argmax(chances))
    return LABEL_TYPES[best], float(chances[best])


# -------------------------------------------------------------------
# 2. MAIN
# -------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) > 1:
        label_type, sure = find_label_type(sys.argv[1])
        print(f"{label_type} (sure: {sure:.2f})")
    else:
        print('Give a line to read, for example: "2022.08.31 | Best before: | NET WT 500g"')

"""
read_date.py - PP-03, step 3 of 3.

find_date(photo_path) finds and reads the date on a package photo:
  1. RapidOCR finds every line of text on the photo.
  2. The CNN from train_cnn.py scores each line: how likely is it the date?
  3. RapidOCR reads the 3 best-scoring lines. The first that looks like a date wins.
  4. If none of them looks like a date, RapidOCR reads the whole photo instead.

Run from the project folder.
  Measure it on the first 120 test photos (the numbers for the slides):
    backend/.venv/bin/python models/cnn/read_date.py
  Read one photo:
    backend/.venv/bin/python models/cnn/read_date.py path/to/photo.jpg
"""

import os
import re
import sys
import threading
import time

import numpy as np
import tensorflow as tf
from rapidocr import RapidOCR

from prepare_data import (
    DATA_DIR,
    box_has_a_date,
    contains_date,
    cut_crop,
    date_boxes_from_labels,
    find_text_boxes,
    load_labels,
    load_photo,
)

# -------------------------------------------------------------------
# SETTINGS
# -------------------------------------------------------------------
CNN_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(CNN_DIR, "date_cnn.keras")

BOXES_TO_READ = 3                       # read the 3 best-scoring boxes
DATE_PATTERN = r"\d{1,4}[./ -]\d{1,4}"  # digits, then . / space or -, then digits
NUMBER_OF_TEST_PHOTOS = 120
SCORE_CUTOFF = 0.5                      # a box scoring 0.5 or more is called "date"

# Load the CNN and start the text finder once, when this file starts.
model = tf.keras.models.load_model(MODEL_FILE)
engine = RapidOCR(params={"Global.log_level": "warning"})

# Only one photo at a time may go through the engine and the CNN. RapidOCR
# keeps the settings of the current call (use_det, use_rec ...) inside the
# engine, so two scans at the same moment (two phones using the app) would
# mix them up. find_date holds this lock while it works.
scanner_lock = threading.Lock()


# -------------------------------------------------------------------
# 1. FIND AND READ THE DATE
# -------------------------------------------------------------------
def score_boxes(photo, boxes):
    """Give every box a CNN score from 0 to 1, where 1 means "this is the date"."""
    if len(boxes) == 0:
        return []
    gray_photo = photo.convert("L")
    crops = []
    for box in boxes:
        crops.append(cut_crop(gray_photo, box))

    # Prepare the crops the same way as train_cnn.py: scale to 0-1, add the channel dimension.
    crops = np.array(crops, dtype="float32") / 255.0
    crops = np.expand_dims(crops, -1)
    predictions = model.predict(crops, verbose=0)

    # predict gives one score per box, each in its own list: [[0.91], [0.02], ...]
    scores = []
    for prediction in predictions:
        scores.append(float(prediction[0]))
    return scores


def read_text(photo, box):
    """Read the text inside one box with RapidOCR (reading only, no finding)."""
    # The rotation step (use_cls) stays off because it turned some correct
    # dates upside down before reading them.
    result = engine(photo.crop(box), use_det=False, use_cls=False, use_rec=True)
    if result.txts:
        return result.txts[0]
    return ""


def looks_like_date(text):
    """True if the text has a date-like part, such as 2025.01.28, 28/01 or 21-01-22."""
    return re.search(DATE_PATTERN, text) is not None


def read_from_boxes(photo, boxes, scores):
    """Read the best-scoring boxes and return the first text that looks like a date."""
    # Pair each score with its box, then sort so the highest score comes first.
    pairs = []
    for i in range(len(boxes)):
        pairs.append((scores[i], boxes[i]))
    pairs.sort(reverse=True)

    for score, box in pairs[:BOXES_TO_READ]:
        text = read_text(photo, box)
        if looks_like_date(text):
            return text
    return ""


def read_whole_photo(photo):
    """Backup plan: read every line on the photo and return the first that looks like a date."""
    # Find and read in one call. The rotation step stays off, as in read_text.
    result = engine(photo, use_det=True, use_cls=False, use_rec=True)
    if result.txts:
        for text in result.txts:
            if looks_like_date(text):
                return text
    return ""


def find_date(photo_path):
    """Find and read the date on one photo.

    Returns (text, how), where how is "box", "whole photo" or "not found".
    """
    photo = load_photo(photo_path)
    with scanner_lock:
        # Step 1: Find every line of text.
        boxes = find_text_boxes(engine, photo)

        # Step 2: Give every line a CNN score.
        scores = score_boxes(photo, boxes)

        # Step 3: Read the best 3 lines and keep the first that looks like a date.
        text = read_from_boxes(photo, boxes, scores)
        if text != "":
            return text, "box"

        # Step 4: Backup plan: read the whole photo.
        text = read_whole_photo(photo)
        if text != "":
            return text, "whole photo"
        return "", "not found"


# -------------------------------------------------------------------
# 2. MEASURE ON THE TEST PHOTOS
# -------------------------------------------------------------------
def expiry_label(photo_labels):
    """Return the box and the text of the photo's expiry date (its "exp" label)."""
    for label in photo_labels["ann"]:
        if label["cls"] == "exp":
            return tuple(label["bbox"]), label["transcription"]
    return None, ""


def digits_of(text):
    """Keep only the digits 0-9: "2025.01.28" becomes "20250128"."""
    digits = ""
    for character in text:
        if character in "0123456789":
            digits += character
    return digits


def read_is_right(text, real_text):
    """True if the real date's digits appear in the digits that were read."""
    real_digits = digits_of(real_text)
    return real_digits != "" and real_digits in digits_of(text)


def measure_on_test_photos():
    """Run the scanner on the first 120 test photos and print the numbers for the slides."""
    labels = load_labels("evaluation")
    photo_names = sorted(labels.keys())[:NUMBER_OF_TEST_PHOTOS]

    top_box_right = 0
    true_positives = 0       # scored 0.5 or more, and holds a date
    false_positives = 0      # scored 0.5 or more, but holds no date
    false_negatives = 0      # holds a date, but scored below 0.5
    box_reads_right = 0
    whole_photo_reads_right = 0
    scanner_reads_right = 0
    found_by = {"box": 0, "whole photo": 0, "not found": 0}
    box_seconds = 0.0
    whole_photo_seconds = 0.0

    for count, name in enumerate(photo_names, start=1):
        photo = load_photo(os.path.join(DATA_DIR, "evaluation", "images", name))
        expiry_box, expiry_text = expiry_label(labels[name])
        date_boxes = date_boxes_from_labels(labels[name])

        # Step 1: Box reading (find the boxes, score them, read the best 3), timed.
        start = time.time()
        boxes = find_text_boxes(engine, photo)
        scores = score_boxes(photo, boxes)
        box_text = read_from_boxes(photo, boxes, scores)
        box_seconds += time.time() - start

        # Step 2: Whole-photo reading of the same photo, timed, to compare.
        start = time.time()
        whole_photo_text = read_whole_photo(photo)
        whole_photo_seconds += time.time() - start

        # Step 3: Does the highest-scoring box hold the expiry date?
        if len(boxes) > 0:
            best = 0
            for i in range(len(boxes)):
                if scores[i] > scores[best]:
                    best = i
            if contains_date(boxes[best], expiry_box):
                top_box_right += 1

        # Step 4: Count the right and wrong "date" calls at the 0.5 cut-off.
        # A box holds a date when any real date's centre is inside it (expiry
        # or other date), the same rule the CNN was trained with.
        for i in range(len(boxes)):
            holds_date = box_has_a_date(boxes[i], date_boxes)
            called_date = scores[i] >= SCORE_CUTOFF
            if called_date and holds_date:
                true_positives += 1
            elif called_date and not holds_date:
                false_positives += 1
            elif holds_date and not called_date:
                false_negatives += 1

        # Step 5: Check the reads against the real expiry date.
        if read_is_right(box_text, expiry_text):
            box_reads_right += 1
        if read_is_right(whole_photo_text, expiry_text):
            whole_photo_reads_right += 1

        # The full scanner makes the same choice as find_date:
        # the box reading first, and the whole photo as the backup.
        if box_text != "":
            scanner_text = box_text
            found_by["box"] += 1
        elif whole_photo_text != "":
            scanner_text = whole_photo_text
            found_by["whole photo"] += 1
        else:
            scanner_text = ""
            found_by["not found"] += 1
        if read_is_right(scanner_text, expiry_text):
            scanner_reads_right += 1

        if count % 20 == 0:
            print("Done", count, "photos")

    # Step 6: Print the numbers for the slides.
    number_of_photos = len(photo_names)
    if true_positives + false_positives > 0:
        precision = true_positives / (true_positives + false_positives)
    else:
        precision = 0.0
    if true_positives + false_negatives > 0:
        recall = true_positives / (true_positives + false_negatives)
    else:
        recall = 0.0

    print()
    print(f"Test photos: {number_of_photos} (ExpDate evaluation set, first {number_of_photos} by name)")
    print()
    print("Finding the date (a box is right when the real date's centre is inside it):")
    print(f"  top box holds the expiry date:  {top_box_right / number_of_photos:.2f}")
    print(f"  boxes scoring 0.5 or more:      precision {precision:.2f}, recall {recall:.2f}")
    print()
    print("Reading the expiry date (right when its digits appear in the text read):")
    print(f"  box reading (best 3 boxes):     {box_reads_right / number_of_photos:.2f}"
          f"  ({box_seconds / number_of_photos:.2f} s per photo)")
    print(f"  whole-photo reading:            {whole_photo_reads_right / number_of_photos:.2f}"
          f"  ({whole_photo_seconds / number_of_photos:.2f} s per photo)")
    print(f"  full scanner (box, then whole): {scanner_reads_right / number_of_photos:.2f}")
    print(f"  found by: box {found_by['box']}, whole photo {found_by['whole photo']}, "
          f"not found {found_by['not found']}")


# -------------------------------------------------------------------
# 3. MAIN
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Some terminals can't show Chinese or Korean letters, which OCR text can
    # contain. errors="replace" prints a ? for those instead of stopping.
    sys.stdout.reconfigure(errors="replace")

    if len(sys.argv) > 1:
        # A photo path was given: read just that photo.
        text, how = find_date(sys.argv[1])
        if how == "not found":
            print("No date found.")
        else:
            print("Date:", text, "| found by:", how)
    else:
        measure_on_test_photos()

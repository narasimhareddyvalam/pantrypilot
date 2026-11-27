"""
collect_real_lines.py - PP-04, step 2 of 4.

Collects real lines from ExpDate photos, with the PP-03 OCR code. For every
labelled date, it reads the text line that holds the date (found with the
dataset's date box, not the CNN) plus the 3 lines nearest to it, joined the
same way as the practice lines. It makes two sets:
  - real lines from the 665 evaluation photos. BERT learns from most of them,
    next to the practice lines, and the rest check it during training.
  - test lines from training photos img_00701.jpg to img_01102.jpg. No model
    learns from them and no setting is chosen with them; they only test BERT.
Saves models/bert/data/real_lines_to_label.csv and test_lines_to_label.csv.
The labelled copies are kept in Git as models/bert/real_lines.csv and test_lines.csv.

Run from the project folder:
    backend/.venv/bin/python models/bert/collect_real_lines.py
"""

import csv
import os
import sys

# -------------------------------------------------------------------
# SETTINGS
# -------------------------------------------------------------------
BERT_DIR = os.path.dirname(os.path.abspath(__file__))
REAL_FILE = os.path.join(BERT_DIR, "data", "real_lines_to_label.csv")
TEST_FILE = os.path.join(BERT_DIR, "data", "test_lines_to_label.csv")
FIRST_TEST_PHOTO = 700     # from position 700 in the sorted names (img_00701.jpg) to the end: used for nothing else

# The PP-03 scanner code is in models/cnn. Adding that folder to Python's
# search path lets this script import from it.
sys.path.insert(0, os.path.join(BERT_DIR, "..", "cnn"))
from prepare_data import DATA_DIR, contains_date, find_text_boxes, load_labels, load_photo
from read_date import engine, label_text, read_nearby_lines, read_text


# -------------------------------------------------------------------
# 1. COLLECT THE LINES OF SOME PHOTOS
# -------------------------------------------------------------------
def collect_lines(folder, labels, photo_names, output_file):
    """Read the date line and its 3 nearest lines for every labelled date, and save them."""
    rows = []
    dates_not_boxed = 0
    for count, name in enumerate(photo_names, start=1):
        photo = load_photo(os.path.join(DATA_DIR, folder, "images", name))
        boxes = find_text_boxes(engine, photo)

        for label in labels[name]["ann"]:
            # "exp" is the expiry date, "date" any other printed date.
            if label["cls"] not in ["exp", "date"]:
                continue

            # Step 1: Find the text line that holds this date.
            date_box = None
            for box in boxes:
                if contains_date(box, label["bbox"]):
                    date_box = box
                    break
            if date_box is None:
                dates_not_boxed += 1
                continue

            # Step 2: Read the date line and its 3 nearest lines.
            date_line = read_text(photo, date_box)
            nearby = read_nearby_lines(photo, boxes, date_box)
            rows.append([len(rows) + 1, name, label["cls"], label["transcription"], label_text(date_line, nearby)])

        if count % 100 == 0:
            print("  done", count, "photos,", len(rows), "lines so far")

    # Step 3: Save the lines, ready to be labelled.
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "photo", "date_class", "real_date", "text"])
        writer.writerows(rows)
    print(" ", len(rows), "lines,", dates_not_boxed, "dates no text line holds. Saved to", output_file)


# -------------------------------------------------------------------
# 2. MAIN
# -------------------------------------------------------------------
if __name__ == "__main__":
    print("Real lines (all 665 evaluation photos):")
    evaluation_labels = load_labels("evaluation")
    collect_lines("evaluation", evaluation_labels, sorted(evaluation_labels.keys()), REAL_FILE)

    print("Test lines (training photos img_00701.jpg to img_01102.jpg):")
    train_labels = load_labels("train")
    collect_lines("train", train_labels, sorted(train_labels.keys())[FIRST_TEST_PHOTO:], TEST_FILE)

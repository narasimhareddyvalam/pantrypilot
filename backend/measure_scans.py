"""
measure_scans.py - how well the whole scan works, for the slides (PP-04).

Runs read_label from scan.py, the same code POST /scans uses, on the ExpDate
training photos img_00701.jpg to img_01102.jpg. No model learned from these
photos and no setting was chosen with them. For each photo it checks:
  - the date: shown as sure and right, shown as sure but wrong, or sent to
    the user to check ("Please check this"). A date counts as right when it is
    one of the dates printed on the package (some print a production date too).
  - the label type, when the date is right (against models/bert/test_lines.csv)

Run from the project folder (needs the ExpDate photos, see models/cnn/README.md):
    backend/.venv/bin/python backend/measure_scans.py
"""

import csv
import os
import time

from PIL import Image

from dates import parse_date
from scan import read_label

# scan.py has added models/cnn to Python's search path, so prepare_data can be imported too.
from prepare_data import DATA_DIR, load_labels

# -------------------------------------------------------------------
# SETTINGS
# -------------------------------------------------------------------
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_LINES_FILE = os.path.join(BACKEND_DIR, "..", "models", "bert", "test_lines.csv")
FIRST_PHOTO = 700     # position 700 in the sorted names is img_00701.jpg, as in collect_real_lines.py


# -------------------------------------------------------------------
# MEASURE
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Step 1: Load the photo labels, and the label type of every test line,
    # looked up by (photo, printed date).
    labels = load_labels("train")
    photo_names = sorted(labels.keys())[FIRST_PHOTO:]
    label_of = {}
    with open(TEST_LINES_FILE, encoding="utf-8") as file:
        for row in csv.DictReader(file):
            label_of[(row["photo"], row["real_date"])] = row["label"]

    outcomes = {
        "sure, right date": 0,
        "sure, wrong date": 0,
        "check, right date filled in": 0,
        "check, wrong date filled in": 0,
        "check, no date filled in": 0,
    }
    photos_with_two_way_dates = 0
    labels_checked = 0
    labels_right = 0
    seconds = 0.0

    for count, name in enumerate(photo_names, start=1):
        # Step 2: The real dates on this photo as YYYY-MM-DD, using the same
        # rules as the app. A printed date that can be read two ways has no
        # single right answer, so the right result for it is "check".
        real_dates = {}
        two_way = False
        for label in labels[name]["ann"]:
            if label["cls"] == "date":
                date, unsure = parse_date(label["transcription"])
                if date is not None:
                    real_dates[date] = label["transcription"]
                elif unsure:
                    two_way = True
        if two_way:
            photos_with_two_way_dates += 1

        # Step 3: Scan the photo exactly as POST /scans does, and time it.
        with Image.open(os.path.join(DATA_DIR, "train", "images", name)) as picture:
            picture.load()
            start = time.time()
            result = read_label(picture)
            seconds += time.time() - start

        # Step 4: Sort the result into one of the five outcomes. A date shown
        # as sure but wrong is the risky one: nothing asks the user to check it.
        right_date = result["date"] is not None and result["date"] in real_dates
        if not result["requiresReview"]:
            if right_date:
                outcomes["sure, right date"] += 1
            else:
                outcomes["sure, wrong date"] += 1
        elif result["date"] is None:
            outcomes["check, no date filled in"] += 1
        elif right_date:
            outcomes["check, right date filled in"] += 1
        else:
            outcomes["check, wrong date filled in"] += 1

        # Step 5: When the date is right, check the label type against the test line.
        if right_date:
            printed = real_dates[result["date"]]
            if (name, printed) in label_of:
                expected = label_of[(name, printed)]
                if expected == "other":
                    expected = None      # the app sends null for "no label word"
                labels_checked += 1
                if result["labelType"] == expected:
                    labels_right += 1

        if count % 100 == 0:
            print("Done", count, "photos")

    # Step 6: Print the numbers for the slides.
    total = len(photo_names)
    sure = outcomes["sure, right date"] + outcomes["sure, wrong date"]
    check = total - sure
    right_filled = outcomes["sure, right date"] + outcomes["check, right date filled in"]
    print()
    print(f"Photos: {total} (ExpDate training photos img_00701.jpg to img_01102.jpg)")
    print(f"  with a printed date that can be read two ways: {photos_with_two_way_dates}")
    print()
    print(f"Shown as sure (no \"Please check this\"):  {sure:3d}  ({sure / total:.2f})")
    print(f"  right date:                            {outcomes['sure, right date']:3d}")
    print(f"  wrong date:                            {outcomes['sure, wrong date']:3d}")
    print(f"Sent to \"Please check this\":             {check:3d}  ({check / total:.2f})")
    print(f"  right date already filled in:          {outcomes['check, right date filled in']:3d}")
    print(f"  wrong date filled in:                  {outcomes['check, wrong date filled in']:3d}")
    print(f"  no date filled in:                     {outcomes['check, no date filled in']:3d}")
    print(f"Right date filled in, sure or not:       {right_filled:3d}  ({right_filled / total:.2f})")
    print()
    if labels_checked > 0:
        print(f"Label type, when the date is right:      {labels_right} of {labels_checked}  ({labels_right / labels_checked:.2f})")
    print(f"Time per scan:                           {seconds / total:.2f} s")

"""
prepare_data.py - PP-03, step 1 of 3.

Cuts every line of text that RapidOCR finds out of the ExpDate training photos
and labels it 1 (holds a date) or 0 (not a date). Everything is saved to
models/cnn/data/crops.npz, which train_cnn.py uses.

Run from the project folder:
    backend/.venv/bin/python models/cnn/prepare_data.py
"""

import json
import math
import os

import numpy as np
from PIL import Image, ImageOps
from rapidocr import RapidOCR

# -------------------------------------------------------------------
# SETTINGS
# -------------------------------------------------------------------
CNN_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CNN_DIR, "data", "Products-Real")
CROPS_FILE = os.path.join(CNN_DIR, "data", "crops.npz")

NUMBER_OF_PHOTOS = 400          # the first 400 training photos, sorted by name
CROP_WIDTH = 128
CROP_HEIGHT = 32
DATE_CLASSES = ["date", "exp"]  # train labels dates "date"; evaluation uses "exp" and "date"


# -------------------------------------------------------------------
# 1. HELPER FUNCTIONS (read_date.py uses these too)
# -------------------------------------------------------------------
def load_labels(folder):
    """Read annotations.json from the "train" or "evaluation" folder."""
    path = os.path.join(DATA_DIR, folder, "annotations.json")
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def load_photo(path):
    """Open a photo the right way up, as an RGB image."""
    with Image.open(path) as photo:
        # Phones save some photos sideways, with a note (EXIF) that says how
        # to turn them. exif_transpose turns the photo so it matches the labels.
        photo = ImageOps.exif_transpose(photo)
        return photo.convert("RGB")


def find_text_boxes(engine, photo):
    """Return one (x1, y1, x2, y2) box for every line of text RapidOCR finds."""
    # RapidOCR takes the PIL photo as it is and changes it to the colour order
    # it needs by itself. use_rec=False: only find where the text is, don't
    # read it yet. use_cls (the rotation step) only matters when reading, so
    # it stays off here.
    result = engine(photo, use_det=True, use_cls=False, use_rec=False)
    if result.boxes is None:
        return []

    width, height = photo.size
    boxes = []
    for corners in result.boxes:
        # Each box comes as 4 corner points. The smallest and largest x and y
        # turn it into a plain rectangle. Left and top are rounded down, right
        # and bottom rounded up, so no text is cut off, and the box is kept
        # inside the photo.
        xs = [point[0] for point in corners]
        ys = [point[1] for point in corners]
        x1 = max(0, math.floor(min(xs)))
        y1 = max(0, math.floor(min(ys)))
        x2 = min(width, math.ceil(max(xs)))
        y2 = min(height, math.ceil(max(ys)))
        # Skip boxes with no width or height left (it can happen at the photo edge).
        if x2 > x1 and y2 > y1:
            boxes.append((x1, y1, x2, y2))
    return boxes


def date_boxes_from_labels(photo_labels):
    """Return the real date boxes of one photo from its labels."""
    date_boxes = []
    for label in photo_labels["ann"]:
        if label["cls"] in DATE_CLASSES:
            date_boxes.append(tuple(label["bbox"]))
    return date_boxes


def contains_date(box, date_box):
    """True if the centre of the real date box is inside the found box."""
    # RapidOCR boxes a whole printed line, like "Best Before: 21.01.22", while
    # the label boxes only the date. So a found box counts as the date when
    # the middle point of the real date box sits inside it.
    x1, y1, x2, y2 = box
    centre_x = (date_box[0] + date_box[2]) / 2
    centre_y = (date_box[1] + date_box[3]) / 2
    return x1 <= centre_x <= x2 and y1 <= centre_y <= y2


def box_has_a_date(box, date_boxes):
    """True if the found box holds at least one of the photo's real dates."""
    for date_box in date_boxes:
        if contains_date(box, date_box):
            return True
    return False


def cut_crop(gray_photo, box):
    """Cut one box out of a grayscale photo, resized to 128 x 32 pixels."""
    crop = gray_photo.crop(box)
    crop = crop.resize((CROP_WIDTH, CROP_HEIGHT))
    return np.array(crop, dtype=np.uint8)


# -------------------------------------------------------------------
# 2. CUT AND LABEL THE CROPS
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Step 1: Load the labels and take the first 400 training photos.
    labels = load_labels("train")
    photo_names = sorted(labels.keys())[:NUMBER_OF_PHOTOS]
    print("Photos:", len(photo_names))

    # Step 2: Start the text finder once. Starting it for every photo would be slow.
    # log_level "warning" hides RapidOCR's start-up messages.
    engine = RapidOCR(params={"Global.log_level": "warning"})

    # Step 3: For every photo, cut out each text box and label it.
    crops = []
    crop_labels = []
    photo_numbers = []          # which photo each crop came from (0 to 399)
    photos_without_boxes = 0
    real_dates = 0
    real_dates_in_a_box = 0

    for photo_number, name in enumerate(photo_names):
        photo = load_photo(os.path.join(DATA_DIR, "train", "images", name))
        gray_photo = photo.convert("L")
        date_boxes = date_boxes_from_labels(labels[name])
        boxes = find_text_boxes(engine, photo)

        if len(boxes) == 0:
            photos_without_boxes += 1

        for box in boxes:
            crops.append(cut_crop(gray_photo, box))
            if box_has_a_date(box, date_boxes):
                crop_labels.append(1)
            else:
                crop_labels.append(0)
            photo_numbers.append(photo_number)

        # Count the real dates that sit inside at least one found box.
        # A date that no box holds can never be found by the CNN later.
        for date_box in date_boxes:
            real_dates += 1
            for box in boxes:
                if contains_date(box, date_box):
                    real_dates_in_a_box += 1
                    break

        if (photo_number + 1) % 50 == 0:
            print("Done", photo_number + 1, "photos,", len(crops), "crops so far")

    # Step 4: Save everything in one file. uint8 (0-255) keeps the file small.
    crops = np.array(crops, dtype=np.uint8)
    crop_labels = np.array(crop_labels, dtype=np.uint8)
    photo_numbers = np.array(photo_numbers)
    np.savez(CROPS_FILE, crops=crops, labels=crop_labels, photo_numbers=photo_numbers)

    # Step 5: Print the counts.
    number_of_dates = int(crop_labels.sum())
    print()
    print("Crops:", len(crops))
    print(f"Date crops: {number_of_dates} ({number_of_dates / len(crops):.2%})")
    print("Not-date crops:", len(crops) - number_of_dates)
    print("Photos with no text found:", photos_without_boxes)
    print(f"Real dates inside a found box: {real_dates_in_a_box} of {real_dates} "
          f"({real_dates_in_a_box / real_dates:.2%})")
    print("Saved to", CROPS_FILE)

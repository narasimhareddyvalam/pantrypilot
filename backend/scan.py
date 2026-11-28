"""POST /scans - read the date label from a photo of a food package.

The scanner finds the printed date on the photo (PP-03), BERT decides the label
type from the text around it (PP-04), and simple rules turn the date into
YYYY-MM-DD (dates.py). Anything unsure comes back with requiresReview set to
true, so the page asks the user to check it. With ?sample=readable, ambiguous
or unreadable, it returns one of the shared examples in shared/fixtures
instead, so the review screen can be tested.
"""

import json
import os
import sys

from flask import Blueprint, jsonify, request
from PIL import Image, ImageOps, UnidentifiedImageError

from dates import parse_date
from errors import PantryError

# The shared examples live in shared/fixtures, one folder up from backend/.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(BASE_DIR, "..", "shared", "fixtures")

# The scanner's code and models live in models/cnn (PP-03) and models/bert
# (PP-04). Adding those folders to Python's search path lets this file import
# them. Importing loads the models once, when the app starts (a few seconds).
sys.path.insert(0, os.path.join(BASE_DIR, "..", "models", "cnn"))
sys.path.insert(0, os.path.join(BASE_DIR, "..", "models", "bert"))
from label_type import find_label_type
from read_date import find_date_in_photo, label_text

# The example names the page can ask for, and the file each one comes from.
SAMPLE_FILES = {
    "readable": "scan_readable.json",
    "ambiguous": "scan_ambiguous.json",
    "unreadable": "scan_unreadable.json",
}

# The label types the team agreed on in the design.
LABEL_TYPES = ["expiration", "best_before", "sell_by", "manufacturing", "other"]

# The label types of dates that look ahead (use by, best before, sell by),
# unlike a production date, which looks back. When the scanner finds more than
# one date line, a date with one of these labels is filled in first.
EXPIRY_TYPES = ["expiration", "best_before", "sell_by"]

# Phone photos are about 12 to 50 megapixels. A bigger picture could use too much
# memory to open, so anything over this many pixels is refused.
MAX_PIXELS = 50_000_000

# The page always sends JPEG, and the error message promises JPG or PNG.
PHOTO_FORMATS = ["JPEG", "PNG"]

# When BERT is less sure than this about the label type, the user checks it.
# On the 148 validation lines, BERT was under 0.7 sure on 9 lines and right on
# only 3 of them; on the other 139 lines it was right 130 times (0.94).
SURE_ENOUGH = 0.7

# A long, thin picture (like a long screenshot) is blown up to many millions of
# pixels by the text finder, so pictures longer than 4 times their width (or
# wider than 4 times their height) are refused. Phone photos are about 2 to 1.
MAX_SIDE_RATIO = 4

scan_blueprint = Blueprint("scan", __name__)


def read_photo(file):
    """Open the uploaded file as a picture, or raise a polite error."""
    # Step 1: Check that a photo was really sent.
    if file is None or file.filename == "":
        raise PantryError("Please add a photo of the package.")

    # Step 2: Open the file as a picture. A phone can send any kind of file,
    # so if Pillow can't open it as a JPEG or PNG, it is not a usable photo.
    try:
        picture = Image.open(file.stream, formats=PHOTO_FORMATS)

        # Step 3: Opening only reads the picture's size, not the picture itself.
        # So the size is checked first, before the whole picture is decoded into memory.
        width, height = picture.size
        if width * height > MAX_PIXELS:
            raise PantryError("That photo is too big to read. Please use a smaller photo.", 413, "too_large")
        if width > MAX_SIDE_RATIO * height or height > MAX_SIDE_RATIO * width:
            raise PantryError("Please use a normal photo of the label, not a long, thin picture.")
        picture.load()
    except Image.DecompressionBombError:
        # A picture with a huge number of pixels could use up all the memory.
        raise PantryError("That photo is too big to read. Please use a smaller photo.", 413, "too_large")
    except (UnidentifiedImageError, OSError):
        raise PantryError("That file isn't a photo we can read. Please use a JPG or PNG photo.")
    return picture


def load_sample(name):
    """Read one of the shared scan examples from shared/fixtures."""
    if name not in SAMPLE_FILES:
        raise PantryError("Sample must be readable, ambiguous or unreadable.")
    path = os.path.join(FIXTURES_DIR, SAMPLE_FILES[name])
    with open(path) as sample_file:
        return json.load(sample_file)


def choose_date_line(date_lines):
    """Choose the date the user needs when the scanner finds more than one date line.

    date_lines is a list of (date_line, nearby_lines): best CNN score first, or
    in reading order for the whole-photo backup. Returns (date_line,
    label_type, sure, clear): the chosen line, its label type from BERT, how
    sure BERT is (0 to 1), and clear, which is False when the photo shows
    different dates and the label words don't settle which one to use.
    """
    # Step 1: Keep the lines that hold a date, each with its date and its
    # label type from BERT. A price like "45.00" or a barcode can look like a
    # date to the scanner, but holds none. An unsure date (like 03/04/27, or
    # the misread 2021.10.2077) is kept with the date None, because it can
    # still be the expiry date.
    kept = []
    for date_line, nearby_lines in date_lines:
        date, unsure = parse_date(date_line)
        if date is not None or unsure:
            label_type, sure = find_label_type(label_text(date_line, nearby_lines))
            kept.append((date_line, date, label_type, sure))

    # If no line holds a date, the first line is still used, so the user sees
    # what was read.
    if len(kept) == 0:
        date_line, nearby_lines = date_lines[0]
        label_type, sure = find_label_type(label_text(date_line, nearby_lines))
        return date_line, label_type, sure, True

    # Step 2: Lines with an expiry-type label come first, like "EXP" over
    # "MFG". Only when there are none do all the lines take part.
    choices = []
    for date_line, date, label_type, sure in kept:
        if label_type in EXPIRY_TYPES:
            choices.append((date_line, date, label_type, sure))
    if len(choices) == 0:
        choices = kept

    # Step 3: Among the choices, the latest date wins, because an expiry date
    # always comes after the production date. Dates written as YYYY-MM-DD text
    # sort in date order, so ">" finds the later one. If no choice has a date,
    # the first one is used.
    chosen = choices[0]
    for date_line, date, label_type, sure in choices:
        chosen_date = chosen[1]
        if date is not None and (chosen_date is None or date > chosen_date):
            chosen = (date_line, date, label_type, sure)
    chosen_line, chosen_date, chosen_label, chosen_sure = chosen

    # Step 4: The choice is clear when every other line holds the same date,
    # or when the chosen date has an expiry label and the other lines are
    # labelled as production dates. Otherwise the user checks it.
    clear = True
    for date_line, date, label_type, sure in kept:
        if date_line == chosen_line:
            continue
        same_date = date is not None and date == chosen_date
        production_beside_expiry = chosen_label in EXPIRY_TYPES and label_type == "manufacturing"
        if not same_date and not production_beside_expiry:
            clear = False

    return chosen_line, chosen_label, chosen_sure, clear


def read_label(picture):
    """Read the date and its label type from a photo, in the agreed response shape."""
    # Step 1: Turn the photo the right way up, in RGB colours, like the training photos.
    photo = ImageOps.exif_transpose(picture).convert("RGB")

    # Step 2: Find the date lines and the lines near each one.
    date_lines, how = find_date_in_photo(photo)
    if how == "not found":
        return {"rawText": "", "labelType": None, "date": None, "requiresReview": True}

    # Step 3: BERT decides the label type of each date line, and the expiry
    # date is chosen over a production date (see choose_date_line). BERT's
    # "other" means no label word goes with the date, so the page gets null,
    # which it shows as "No label, or not sure".
    date_line, label_type, sure, clear = choose_date_line(date_lines)
    if label_type == "other":
        label_type = None

    # Step 4: Turn the date text into YYYY-MM-DD. It is unsure when it can
    # mean more than one day, or when only the month and year are printed.
    date, unsure = parse_date(date_line)

    # Step 5: Ask the user to check whenever something is uncertain: no date,
    # a date that can mean more than one day, a date found only by the
    # whole-photo backup, a label type BERT isn't sure about, or different
    # dates that the label words don't settle. (A label type of null is not a
    # guess: the page shows "No label, or not sure".)
    requires_review = (
        date is None
        or unsure
        or how == "whole photo"
        or sure < SURE_ENOUGH
        or not clear
    )
    return {"rawText": date_line, "labelType": label_type, "date": date, "requiresReview": requires_review}


@scan_blueprint.post("/scans")
def scan_photo():
    # Step 1: Check the photo first, so a bad photo is refused even when a sample is asked for.
    picture = read_photo(request.files.get("image"))

    # Step 2: ?sample=readable, ambiguous or unreadable returns one of the
    # shared examples, so the review screen can be tested.
    sample_name = request.args.get("sample")
    if sample_name is not None:
        return jsonify(load_sample(sample_name))

    # Step 3: Otherwise read the real photo.
    return jsonify(read_label(picture))

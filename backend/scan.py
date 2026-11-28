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
    # so if Pillow can't open it as a JPEG or PNG, it is not a photo we can use.
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


def read_label(picture):
    """Read the date and its label type from a photo, in the agreed response shape."""
    # Step 1: Turn the photo the right way up, in RGB colours, like the training photos.
    photo = ImageOps.exif_transpose(picture).convert("RGB")

    # Step 2: Find the date line and the lines near it.
    date_line, nearby_lines, how = find_date_in_photo(photo)
    if how == "not found":
        return {"rawText": "", "labelType": None, "date": None, "requiresReview": True}

    # Step 3: BERT decides the label type from the date line and the lines near
    # it. Its "other" means no label word goes with the date, so the page gets
    # null, which it shows as "No label, or not sure".
    label_type, sure = find_label_type(label_text(date_line, nearby_lines))
    if label_type == "other":
        label_type = None

    # Step 4: Turn the date text into YYYY-MM-DD. It is unsure when it can
    # mean more than one day, or when only the month and year are printed.
    date, unsure = parse_date(date_line)

    # Step 5: Ask the user to check whenever something is uncertain: no date,
    # a date that can mean more than one day, a date found only by the
    # whole-photo backup, or a label type BERT isn't sure about. (A label type
    # of null is not a guess: the page shows "No label, or not sure".)
    requires_review = (
        date is None
        or unsure
        or how == "whole photo"
        or sure < SURE_ENOUGH
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

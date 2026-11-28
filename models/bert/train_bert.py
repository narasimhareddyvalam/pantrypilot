"""
train_bert.py - PP-04, step 3 of 4.

Teaches a small BERT model (bert_tiny_en_uncased from KerasHub) the five label
types. It learns from the practice lines (make_train_lines.py) and from real
labelled lines of the evaluation photos (real_lines.csv). Then it is tested on
the separate test lines (test_lines.csv), next to simple keyword rules, and
saved in models/bert/label_model/.

Run from the project folder:
    backend/.venv/bin/python models/bert/train_bert.py
"""

import csv
import os
import re

import keras
import keras_hub
import numpy as np

from make_train_lines import KEYWORDS, LABEL_TYPES, SEPARATOR, TRAIN_FILE

# -------------------------------------------------------------------
# SETTINGS
# -------------------------------------------------------------------
BERT_DIR = os.path.dirname(os.path.abspath(__file__))
REAL_FILE = os.path.join(BERT_DIR, "real_lines.csv")
TEST_FILE = os.path.join(BERT_DIR, "test_lines.csv")
MODEL_DIR = os.path.join(BERT_DIR, "label_model")

PRESET = "bert_tiny_en_uncased"     # the smallest English BERT: 4.4 million weights, 18 MB
SEQUENCE_LENGTH = 64                # fits every practice line and all but 3 real ones (those lose only junk at the end)
FIRST_VALIDATION_PHOTO = "test_00533.jpg"   # evaluation photos from here on (the last 20%) check training
REAL_REPEATS = 3                    # each real line is used 3 times, so they count more (see Step 5)
EPOCHS = 2                          # chosen with the validation loss, see Step 5
BATCH_SIZE = 32
LEARNING_RATE = 1e-4
DATE_PATTERN = r"\d{1,4}[./ -]\d{1,4}"   # the same date pattern as read_date.py


# -------------------------------------------------------------------
# 1. HELPER FUNCTIONS
# -------------------------------------------------------------------
def load_lines(path):
    """Read a CSV of lines and return its rows as a list of dictionaries."""
    with open(path, encoding="utf-8") as file:
        return list(csv.DictReader(file))


def texts_and_numbers(rows):
    """Split rows into their texts and their label numbers (0-4)."""
    texts = []
    numbers = []
    for row in rows:
        texts.append(row["text"])
        numbers.append(LABEL_TYPES.index(row["label"]))
    return texts, np.array(numbers)


def find_keyword_type(segment):
    """Return the label type whose English word appears in this piece of text, or None."""
    for label_type in KEYWORDS:
        for keyword in KEYWORDS[label_type]:
            # \b means a word edge, so "PRO" matches "PRO:13.11" but not "PROTEIN".
            # re.escape makes the dot in "EXP." a plain dot, not "any character".
            if re.search(r"\b" + re.escape(keyword) + r"\b", segment.upper()):
                return label_type
    return None


def rule_label_type(text):
    """The simple baseline: decide the label type with English keyword rules."""
    segments = text.split(SEPARATOR)

    # Rule 1: a label word on the date line itself decides.
    found = find_keyword_type(segments[0])
    if found is not None:
        return found

    # Rules 2 and 3: otherwise the nearest line with a label word and no date
    # of its own decides. A label word with its own date belongs to that date,
    # so it is skipped.
    for segment in segments[1:]:
        found = find_keyword_type(segment)
        if found is not None and re.search(DATE_PATTERN, segment) is None:
            return found

    # Rule 4: no label word counts, so the type is other.
    return "other"


def print_scores(title, rows, bert_answers, rule_answers):
    """Print how often BERT and the rules give each line's label."""
    bert_right = 0
    rules_right = 0
    for i in range(len(rows)):
        if bert_answers[i] == rows[i]["label"]:
            bert_right += 1
        if rule_answers[i] == rows[i]["label"]:
            rules_right += 1
    count = len(rows)
    if count > 0:
        # :34 and :4d pad the title and count to fixed widths, so the columns line up.
        print(f"  {title:34} {count:4d} lines   BERT {bert_right / count:.2f}   rules {rules_right / count:.2f}")


# -------------------------------------------------------------------
# 2. DATA
# -------------------------------------------------------------------
# Step 1: Load the practice lines and the real labelled lines. The real lines
# are split by photo: most teach BERT, the last 20% of photos check training.
practice_rows = load_lines(TRAIN_FILE)
real_rows = load_lines(REAL_FILE)
real_train_rows = []
validation_rows = []
for row in real_rows:
    # The photo names are test_00001.jpg to test_00665.jpg, so they sort in order.
    if row["photo"] < FIRST_VALIDATION_PHOTO:
        real_train_rows.append(row)
    else:
        validation_rows.append(row)

# Step 2: Train on all practice lines, plus every real line REAL_REPEATS times.
# (A list times 3 is the list three times in a row.)
x_train, y_train = texts_and_numbers(practice_rows + real_train_rows * REAL_REPEATS)
x_val, y_val = texts_and_numbers(validation_rows)
print("Training lines:", len(practice_rows), "practice +", len(real_train_rows), "real (each used", REAL_REPEATS, "times)")
print("Validation lines:", len(validation_rows), "real")

# Step 3: Load the test lines (training photos img_00701.jpg to img_01102.jpg).
# Nothing learns from them and no setting was chosen with them; they are only
# used at the end.
test_rows = load_lines(TEST_FILE)
print("Test lines:", len(test_rows), "real")

# -------------------------------------------------------------------
# 3. BUILD THE MODEL
# -------------------------------------------------------------------
# Step 4: Load the pre-trained BERT with a new last layer for the 5 label types.
# A "preset" is KerasHub's name for a saved model folder: settings, weights and
# word list. The first run downloads this one (about 17 MB) once.
# The preprocessor turns text into word pieces ("expiry" -> "ex", "##pi", "##ry")
# and cuts every line to SEQUENCE_LENGTH pieces, instead of the default 512.
# The seed fixes the random start of the new last layer, so a rerun gives the
# same numbers.
keras.utils.set_random_seed(0)
preprocessor = keras_hub.models.BertTextClassifierPreprocessor.from_preset(
    PRESET, sequence_length=SEQUENCE_LENGTH
)
model = keras_hub.models.BertTextClassifier.from_preset(
    PRESET, preprocessor=preprocessor, num_classes=len(LABEL_TYPES)
)

# -------------------------------------------------------------------
# 4. TRAIN
# -------------------------------------------------------------------
# Step 5: The model gives 5 raw scores (logits), one per label type.
# SparseCategoricalCrossentropy compares them with the right label's number.
# The lines go in a fixed order every epoch: the practice lines first (mixed
# once in make_train_lines.py), then the real lines 3 times. So every epoch
# ends on real text. shuffle=False says so: KerasHub hands Keras the lists in
# a form Keras can't shuffle anyway.
# Tuning notes:
# - Trained on practice lines alone, BERT gave a label type to many real lines
#   that have no label word: the made-up "other" lines look too clean next to
#   real OCR text. So the real lines were added, and the test moved to new photos.
# - Trial runs (learning rate 1e-4 or 3e-4, real lines used once or 3 times,
#   12 epochs) were checked on the validation lines only. The lowest validation
#   loss was 1e-4 with the real lines 3 times, at epoch 2. After that, the
#   validation loss rises: BERT starts to memorize its training lines.
# - After a review added maker lines and nearest-word examples to the practice
#   lines, a second round compared this fixed order with the lines shuffled
#   once. The fixed order had the lower validation loss (0.34 against 0.42).
model.compile(
    optimizer=keras.optimizers.Adam(LEARNING_RATE),
    loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=["accuracy"],
)
model.fit(x=x_train, y=y_train, validation_data=(x_val, y_val), epochs=EPOCHS, batch_size=BATCH_SIZE,
          shuffle=False)

# -------------------------------------------------------------------
# 5. TEST
# -------------------------------------------------------------------
# Step 6: Ask BERT and the keyword rules about every test line.
test_texts, _ = texts_and_numbers(test_rows)
scores = model.predict(test_texts, verbose=0)
bert_answers = []
rule_answers = []
for i in range(len(test_rows)):
    bert_answers.append(LABEL_TYPES[int(np.argmax(scores[i]))])
    rule_answers.append(rule_label_type(test_texts[i]))

# Step 7: Print the scores: all lines, then by the language of the label word
# (the practice lines only have English words), then by label type.
print()
print("Test lines (share of lines where the answer matches the label):")
print_scores("all lines", test_rows, bert_answers, rule_answers)
for language in ["english", "none", "other_language"]:
    picked = [i for i in range(len(test_rows)) if test_rows[i]["keyword_language"] == language]
    print_scores("label word: " + language, [test_rows[i] for i in picked],
                 [bert_answers[i] for i in picked], [rule_answers[i] for i in picked])
print()
print("By label type:")
for label_type in LABEL_TYPES:
    picked = [i for i in range(len(test_rows)) if test_rows[i]["label"] == label_type]
    print_scores(label_type, [test_rows[i] for i in picked],
                 [bert_answers[i] for i in picked], [rule_answers[i] for i in picked])

# -------------------------------------------------------------------
# 6. SAVE
# -------------------------------------------------------------------
# Step 8: Compile again with a fresh optimizer before saving. The optimizer's
# memory is only needed to keep training, and leaving it out makes the saved
# model 18 MB instead of 53 MB.
model.compile(
    optimizer=keras.optimizers.Adam(LEARNING_RATE),
    loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
)
model.save_to_preset(MODEL_DIR)
print()
print("Saved to", MODEL_DIR)

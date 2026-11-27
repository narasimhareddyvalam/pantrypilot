"""
make_train_lines.py - PP-04, step 1 of 4.

Makes the practice text that teaches BERT the label types. Each line looks
like what the scanner reads around a date: the date line first, then the 3
lines nearest to it, joined with " | ". For example:
    2022.08.31 | Best before: | NET WT 500g | KEEP REFRIGERATED   ->  best_before

No public dataset has these label types, so the lines are made up from
keyword lists, the date formats seen in the ExpDate photos, other package
text, and OCR-style typos. BERT also learns from real labelled lines (see
collect_real_lines.py and train_bert.py). Saves models/bert/data/train_lines.csv.

Run from the project folder:
    backend/.venv/bin/python models/bert/make_train_lines.py
"""

import csv
import os
import random

# -------------------------------------------------------------------
# SETTINGS
# -------------------------------------------------------------------
BERT_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_FILE = os.path.join(BERT_DIR, "data", "train_lines.csv")

LINES_PER_TYPE = 1000
SEPARATOR = " | "      # between the date line and each nearby line (label_text in read_date.py joins real lines the same way)

# The label types the team agreed on, in the order BERT numbers them (0 to 4).
LABEL_TYPES = ["expiration", "best_before", "sell_by", "manufacturing", "other"]

# The words that mark each label type ("other" has none). "USE BY" counts
# as expiration, as in the team's scan examples.
KEYWORDS = {
    "expiration": ["EXP", "EXP.", "EXP DATE", "EXP. DATE", "EXPIRY", "EXPIRY DATE", "EXPIRES",
                   "EXPIRES ON", "EXPIRATION DATE", "USE BY", "USE-BY", "USE BEFORE", "CONSUME BY"],
    "best_before": ["BEST BEFORE", "BEST BEFORE END", "BEST BY", "BEST IF USED BY", "BEST IF USED BEFORE",
                    "BEST WHEN USED BY", "BB", "BBE", "ENJOY BY"],
    "sell_by": ["SELL BY", "SELL-BY", "SELL BEFORE", "DISPLAY UNTIL"],
    "manufacturing": ["MFG", "MFG DATE", "MFD", "MANUFACTURED ON", "DATE OF MANUFACTURE",
                      "PROD", "PRO", "PROD DATE", "PRODUCED ON", "PRODUCTION DATE", "MADE ON", "PACKED ON",
                      "PACK DATE", "PKD"],
}
# "MANUFACTURED" alone is not a label word: on US packages it is mostly a maker
# line, like "MANUFACTURED FOR ACME FOODS" (see OTHER_LINES).

# Other text found on packages, with no label-type words. Some look a bit
# like dates or keywords on purpose ("USE WITHIN", "MADE IN", lot numbers).
OTHER_LINES = [
    "NET WT 16 OZ (454g)", "NET WT 500g", "1.5 L", "KEEP REFRIGERATED", "KEEP FROZEN",
    "STORE IN A COOL DRY PLACE", "INGREDIENTS: SUGAR, SALT", "MADE IN USA", "PRODUCT OF ITALY",
    "DISTRIBUTED BY ACME FOODS", "NUTRITION FACTS", "CALORIES 120", "LOT 21345B", "L2134 08:56",
    "BATCH 278", "1802 0745", "www.acmefoods.com", "1-800-555-0199", "SERVING SIZE 1 CUP", "ORGANIC",
    "GLUTEN FREE", "PLEASE RECYCLE", "SHAKE WELL", "ONCE OPENED USE WITHIN 3 DAYS", "PRICE $3.99",
    "PASTEURIZED", "WHOLE MILK", "NO ADDED SUGAR", "18 g (1.5 g x 12)", "69.2%", "5.3g", "Fat 8g 10%",
    "NEW YORK, NY 10001", "SINCE 1845", "ITEM 40312", "UPC 0 12345 67890 5", "CONTAINS: MILK, SOY",
    "MANUFACTURED FOR ACME FOODS", "MANUFACTURED BY ACME FOODS INC.", "PRODUCED BY ACME DAIRY",
    "PACKED BY ACME FOODS", "MADE BY ACME BAKERY", "DIST. BY ACME FOODS",
]

MONTH_NAMES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# OCR often mixes up these look-alike characters.
LOOK_ALIKES = {"O": "0", "0": "O", "I": "1", "1": "I", "S": "5", "5": "S", "B": "8", "8": "B", "G": "6", "Z": "2"}


# -------------------------------------------------------------------
# 1. HELPER FUNCTIONS
# -------------------------------------------------------------------
def random_date_text():
    """Write a random date in one of the formats seen on real packages."""
    year = random.randint(2019, 2029)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    short_year = year % 100
    month_name = MONTH_NAMES[month - 1]
    # :02d writes a number with 2 digits, so 3 becomes 03.
    formats = [
        f"{year}.{month:02d}.{day:02d}",            # 2025.01.28 (the most common)
        f"{year}.{month:02d}.{day:02d}",
        f"{short_year:02d}.{month:02d}.{day:02d}",  # 25.01.28
        f"{day:02d}.{month:02d}.{short_year:02d}",  # 28.01.25
        f"{day:02d}.{month:02d}.{year}",            # 28.01.2025
        f"{day:02d}/{month:02d}/{year}",            # 28/01/2025
        f"{year}/{month:02d}/{day:02d}",            # 2025/01/28
        f"{month:02d}/{day:02d}/{short_year:02d}",  # 01/28/25
        f"{year}-{month:02d}-{day:02d}",            # 2025-01-28
        f"{day:02d} {month:02d} {year}",            # 28 01 2025
        f"{year} {month:02d} {day:02d}",            # 2025 01 28
        f"{month:02d}/{year}",                      # 01/2025
        f"{day:02d} {month_name} {year}",           # 28 JAN 2025
        f"{month_name} {day:02d} {year}",           # JAN 28 2025
    ]
    return random.choice(formats)


def keyword_line(label_type):
    """A line that is just a label word, like "BEST BEFORE:"."""
    return random.choice(KEYWORDS[label_type]) + random.choice(["", ":", " :", "."])


def keyword_with_date(label_type):
    """A label word and its date on one line, like "EXP 2021.11.17"."""
    keyword = random.choice(KEYWORDS[label_type])
    return keyword + random.choice([" ", ": ", ":", " : "]) + random_date_text()


def add_typos(text):
    """Make about half the lines look like a slightly wrong OCR read."""
    if random.random() < 0.5:
        return text
    letters = list(text)
    for i in range(len(letters)):
        chance = random.random()
        if chance < 0.03 and letters[i].upper() in LOOK_ALIKES:
            letters[i] = LOOK_ALIKES[letters[i].upper()]   # a look-alike swap
        elif chance < 0.05:
            letters[i] = ""                                # a dropped character
    text = "".join(letters)
    if random.random() < 0.15:
        text = text.replace(" ", "")                       # lost spaces
    if random.random() < 0.3:
        text = text.title()                                # "Best Before" instead of "BEST BEFORE"
    return text


def make_example(label_type):
    """Make one practice line for a label type: the date line, then 3 nearby lines."""
    nearby = random.sample(OTHER_LINES, 3)
    other_types = [t for t in KEYWORDS if t != label_type]

    if label_type == "other":
        # A date with no label word anywhere near it. Sometimes a nearby line
        # is a different date with its own label word, which doesn't count.
        date_line = random_date_text()
        if random.random() < 0.3:
            nearby[random.randint(0, 2)] = keyword_with_date(random.choice(list(KEYWORDS)))
    elif random.random() < 0.5:
        # The label word is on the date line itself, like "EXP 2021.11.17".
        date_line = keyword_with_date(label_type)
        if random.random() < 0.3:
            # A nearby label word for something else doesn't change the answer,
            # because the date line's own word comes first.
            spot = random.randint(0, 2)
            if random.random() < 0.5:
                nearby[spot] = keyword_line(random.choice(other_types))
            else:
                nearby[spot] = keyword_with_date(random.choice(other_types))
    else:
        # The label word is on its own line near the date, like "BEST BEFORE:".
        date_line = random_date_text()
        keyword_spot = random.randint(0, 2)
        nearby[keyword_spot] = keyword_line(label_type)
        if keyword_spot < 2 and random.random() < 0.3:
            # A label word farther away doesn't change the answer: the nearest one decides.
            nearby[random.randint(keyword_spot + 1, 2)] = keyword_line(random.choice(other_types))
        elif random.random() < 0.3:
            # Another date with its own label word doesn't change the answer either.
            other_spots = [0, 1, 2]
            other_spots.remove(keyword_spot)
            nearby[random.choice(other_spots)] = keyword_with_date(random.choice(other_types))

    lines = [date_line] + nearby
    noisy_lines = []
    for line in lines:
        noisy_lines.append(add_typos(line))
    return SEPARATOR.join(noisy_lines)


# -------------------------------------------------------------------
# 2. MAKE AND SAVE THE LINES
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Step 1: Fix the randomness, so a rerun makes the same lines.
    random.seed(0)

    # Step 2: Make the same number of lines for every label type.
    rows = []
    for label_type in LABEL_TYPES:
        for _ in range(LINES_PER_TYPE):
            rows.append([make_example(label_type), label_type])
    random.shuffle(rows)

    # Step 3: Save them as a CSV file with a text column and a label column.
    os.makedirs(os.path.dirname(TRAIN_FILE), exist_ok=True)
    with open(TRAIN_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["text", "label"])
        writer.writerows(rows)

    # Step 4: Print a few examples and the counts.
    for text, label_type in rows[:8]:
        print(f"{label_type:14} {text}")
    print()
    print("Lines:", len(rows), "|", LINES_PER_TYPE, "for each of", len(LABEL_TYPES), "label types")
    print("Saved to", TRAIN_FILE)

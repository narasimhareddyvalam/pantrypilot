"""Turn the date text read from a package into a YYYY-MM-DD date.

Printed dates come in many orders: 2025.01.28, 28.01.25, 01/28/25, MAY 27 2027.
When the text can be read as more than one real date (21.01.22 could be
22 Jan 2021 or 21 Jan 2022), the date is "unsure" and the app asks the user to
check it, instead of guessing. Numbers with a 1-digit day or month (5/27/2027)
are not trusted either, because OCR often drops a digit; the user types them in.
"""

import calendar
import re

# -------------------------------------------------------------------
# SETTINGS
# -------------------------------------------------------------------
MONTH_NAMES = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
               "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}
# A whole month name, short or long. \b is a word edge, so "MARINATED" is not March.
MONTH = (r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL"
         r"|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\b")
SEP = r"[,./\- ]{1,3}"   # 1 to 3 of , . / - or space between the parts of a date

# The date shapes, tried in this order. ( ) marks the parts that are kept.
# In the month-name shapes, \b keeps each number whole. The number shapes leave
# \b out, because OCR often glues other characters (like Chinese) to the
# digits; readings_of_three_numbers checks how many digits each part has instead.
DAY_MONTHNAME_YEAR = r"\b(\d{1,2})" + SEP + MONTH + SEP + r"(\d{2,4})\b"     # 27 MAY 2027, 27MAY27
MONTHNAME_DAY_YEAR = MONTH + SEP + r"(\d{1,2})" + SEP + r"(\d{2,4})\b"       # MAY 27 2027, MAY 27, 27
MONTHNAME_YEAR = MONTH + SEP + r"(\d{4})\b"                                 # MAY 2027
THREE_NUMBERS = r"(\d{1,4})" + SEP + r"(\d{1,2})" + SEP + r"(\d{1,4})"     # 2025.01.28, 28/01/25, 22 /09 /2021
MONTH_YEAR = r"(\d{1,2})" + SEP + r"(\d{4})"                              # 05/2027
YEAR_MONTH = r"(\d{4})" + SEP + r"(\d{1,2})"                              # 2027.05


# -------------------------------------------------------------------
# 1. HELPER FUNCTIONS
# -------------------------------------------------------------------
def full_year(year_text):
    """Turn "27" or "2027" into 2027."""
    year = int(year_text)
    if year < 100:
        year = 2000 + year
    return year


def real_date(year, month, day):
    """True if the day exists in that month (so 2027-02-30 is not real)."""
    if year < 2000 or year > 2099 or month < 1 or month > 12 or day < 1:
        return False
    # monthrange gives (the first weekday, the number of days), so [1] is the number of days.
    return day <= calendar.monthrange(year, month)[1]


def as_text(year, month, day):
    """Write a date as YYYY-MM-DD."""
    return f"{year:04d}-{month:02d}-{day:02d}"


def last_day_of_month(year, month):
    """The last day of a month, for dates printed as month and year only."""
    return as_text(year, month, calendar.monthrange(year, month)[1])


def readings_of_three_numbers(first, middle, last):
    """List every real date that three printed numbers could mean."""
    # A printed day, month or short year has 2 digits, and a long year 4. A part
    # with 1 or 3 digits is most likely an OCR slip (a lost or an extra digit,
    # like 2022.05.3 for 2022.05.31), so no reading is trusted.
    for part in [first, middle, last]:
        if len(part) != 2 and len(part) != 4:
            return []

    readings = []
    if len(first) == 4:
        readings.append((int(first), int(middle), int(last)))              # 2025.01.28
    if len(last) == 4:
        readings.append((int(last), int(middle), int(first)))              # 28.01.2025
        readings.append((int(last), int(first), int(middle)))              # 01/28/2025
    if len(first) == 2 and len(last) == 2:
        readings.append((full_year(first), int(middle), int(last)))        # 25.01.28
        readings.append((full_year(last), int(middle), int(first)))        # 28.01.25
        readings.append((full_year(last), int(first), int(middle)))        # 01/28/25

    real = []
    for year, month, day in readings:
        if real_date(year, month, day) and (year, month, day) not in real:
            real.append((year, month, day))
    return real


# -------------------------------------------------------------------
# 2. PARSE A DATE
# -------------------------------------------------------------------
def parse_date(text):
    """Return (date as YYYY-MM-DD or None, unsure) for the date in the text.

    unsure is True when the date could mean more than one day, when the line
    has two dates, or when only the month and year are printed. Then the app
    asks the user to check it.
    """
    # Step 1: Use capital letters, and put a space between digits and letters,
    # so "27may27" reads as "27 MAY 27". (\1 and \2 put back the digit and the
    # letter that were found, with a space between them.)
    text = text.upper()
    text = re.sub(r"(\d)([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z])(\d)", r"\1 \2", text)
    # Clock times like 13:47 are not part of the date. They become a word, so
    # no date shape can take the hour or the minutes as a day, month or year.
    text = re.sub(r"\d{2}:\d{2}", " TIME ", text)

    # Step 2: Dates with a month name are never mixed up: 27 MAY 2027, MAY 27 2027.
    # group(1) is the first ( ) from the left, group(2) the second, and so on;
    # the ( ) around the month names in MONTH counts too.
    # [:3] keeps the first 3 letters, so "SEPTEMBER" is looked up as "SEP".
    found = re.search(DAY_MONTHNAME_YEAR, text)
    if found:
        day = int(found.group(1))
        month = MONTH_NAMES[found.group(2)[:3]]
        year = full_year(found.group(3))
        if real_date(year, month, day):
            return as_text(year, month, day), False
    found = re.search(MONTHNAME_DAY_YEAR, text)
    if found:
        month = MONTH_NAMES[found.group(1)[:3]]
        day = int(found.group(2))
        year = full_year(found.group(3))
        if real_date(year, month, day):
            return as_text(year, month, day), False
    found = re.search(MONTHNAME_YEAR, text)
    if found:
        month = MONTH_NAMES[found.group(1)[:3]]
        year = int(found.group(2))
        if real_date(year, month, 1):
            return last_day_of_month(year, month), True

    # Step 3: Three numbers, like 2025.01.28 or 21.01.22. A line with two such
    # dates (like "PRD 16.01.2021 EXP 15.01.2022") doesn't say which one is
    # meant, so the user checks it. If the numbers can mean more than one real
    # date, the date is unsure. If they make no real date (like 2027.02.30,
    # probably a misread), there is no date to trust.
    if len(re.findall(THREE_NUMBERS, text)) > 1:
        return None, True
    found = re.search(THREE_NUMBERS, text)
    if found:
        readings = readings_of_three_numbers(found.group(1), found.group(2), found.group(3))
        if len(readings) == 1:
            year, month, day = readings[0]
            return as_text(year, month, day), False
        if len(readings) > 1:
            return None, True
        return None, False

    # Step 4: Month and year only, like 05/2027 or 2027.05. Packages mean the
    # end of that month, so the last day is used, and the user checks it.
    found = re.search(MONTH_YEAR, text)
    if found:
        month = int(found.group(1))
        year = int(found.group(2))
        if real_date(year, month, 1):
            return last_day_of_month(year, month), True
    found = re.search(YEAR_MONTH, text)
    if found:
        year = int(found.group(1))
        month = int(found.group(2))
        if real_date(year, month, 1):
            return last_day_of_month(year, month), True

    # Step 5: No date we can trust.
    return None, False

import re
from datetime import datetime
from typing import List, Optional

# --- Regex building blocks ---
# Month names + common abbreviations (with optional trailing period)
_MONTH_RE = (
    r"(?:Jan(?:uary)?\.?|Feb(?:ruary)?\.?|Mar(?:ch)?\.?|Apr(?:il)?\.?|May\.?|"
    r"Jun(?:e)?\.?|Jul(?:y)?\.?|Aug(?:ust)?\.?|Sep(?:t(?:ember)?)?\.?|"
    r"Oct(?:ober)?\.?|Nov(?:ember)?\.?|Dec(?:ember)?\.?)"
)

# 1) "July 1, 2023" (also "Jul 1, 2023", "Jul. 1, 2023")
# There are many other variations TSA has used historically in the reading room file titles
# including missing commas, per
_MONTH_DAY_YEAR_RE = re.compile(
    rf"\b(?P<month>{_MONTH_RE})"
    rf"(?:\D+)"                          # not a digit (separator before day)
    rf"(?P<day>0?[1-9]|[12][0-9]|3[01])"
    rf"(?:\D+)"                          # not a digit (separator before year)
    rf"(?P<year>\d{{4}})\b",
    re.IGNORECASE,
)

# 2) "MM/DD/YYYY" or "M/D/YY" etc.
_NUMERIC_SLASH_RE = re.compile(
    r"\b(?P<m>0?[1-9]|1[0-2])/(?P<d>0?[1-9]|[12][0-9]|3[01])/(?P<y>\d{2}|\d{4})\b"
)

# Cross-month range (relaxed): "February 26-March 4, 2017" /
# "Feb. 26 – Mar. 4 2017" / "March 26-April 1 2017" / etc.
_RANGE_CROSS_MONTH_RE = re.compile(
    rf"\b(?P<m1>{_MONTH_RE})(?:\s+|\s*[-/.,]?\s*)"
    rf"(?P<d1>0?[1-9]|[12][0-9]|3[01])\s*"
    rf"(?:-|–|—|\bto\b)\s*"                      # <-- important: "to" as a word
    rf"(?P<m2>{_MONTH_RE})(?:\s+|\s*[-/.,]?\s*)"
    rf"(?P<d2>0?[1-9]|[12][0-9]|3[01])"
    rf"(?:\s*,?\s*)(?P<year>\d{{4}})\b",
    re.IGNORECASE,
)

# Same-month range (relaxed): "March 19-25, 2017" /
# "Mar. 19–25 2017" / "March 19 to 25 2017" / etc.
_RANGE_SAME_MONTH_RE = re.compile(
    rf"\b(?P<m1>{_MONTH_RE})"                                # month
    rf"(?:\s+|\s*[-/.,]?\s*)"                                # flexible separator
    rf"(?P<d1>0?[1-9]|[12][0-9]|3[01])"                      # day 1
    rf"\s*[-–—to]+\s*"                                       # range separator
    rf"(?P<d2>0?[1-9]|[12][0-9]|3[01])"                      # day 2
    rf"(?:\s*,?\s*)"                                         # optional comma before year
    rf"(?P<year>\d{{4}})\b",                                 # year
    re.IGNORECASE,
)

_MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

def _month_str_to_int(s: str) -> int:
    s = s.strip().lower().rstrip(".")
    # handle "sept" explicitly (rstrip('.') already done)
    if s == "sept":
        return 9
    return _MONTH_MAP[s]

def _safe_dt(year: int, month: int, day: int) -> Optional[datetime]:
    try:
        return datetime(year, month, day)
    except ValueError:
        return None

def _yy_to_yyyy(yy: int, pivot: int = 69) -> int:
    """
    Convert 2-digit year to 4-digit using a pivot.
    Default mimics common behavior: 00-69 => 2000-2069, 70-99 => 1970-1999.
    """
    return 2000 + yy if yy <= pivot else 1900 + yy

def find_dates(text: str) -> List[datetime]:
    """
    Tries, in order:
      1) MonthName Day, YYYY  (e.g., "July 1, 2023", "Jul 1, 2023", "Jul. 1, 2023")
      2) Numeric slash dates  (MM/DD/YYYY or M/D/YY)
      3) MonthName D1-D2, YYYY (same-month ranges) -> returns BOTH start and end as datetimes

    Returns a list of datetimes in detection order, de-duplicated by exact datetime value.
    """
    if not text:
        return []

    found: List[datetime] = []
    seen = set()

    def add(dt: Optional[datetime]):
        if dt is None:
            return
        if dt not in seen:
            seen.add(dt)
            found.append(dt)

    # 1) MonthName Day, YYYY
    for m in _MONTH_DAY_YEAR_RE.finditer(text):
        month = _month_str_to_int(m.group("month"))
        day = int(m.group("day"))
        year = int(m.group("year"))
        add(_safe_dt(year, month, day))

    # 2) Numeric slash formats
    for m in _NUMERIC_SLASH_RE.finditer(text):
        month = int(m.group("m"))
        day = int(m.group("d"))
        y = m.group("y")
        year = int(y) if len(y) == 4 else _yy_to_yyyy(int(y))
        add(_safe_dt(year, month, day))

    # Cross-month ranges: "Feb 26–Mar 4 2017"
    for m in _RANGE_CROSS_MONTH_RE.finditer(text):
        m1 = _month_str_to_int(m.group("m1"))
        m2 = _month_str_to_int(m.group("m2"))
        year = int(m.group("year"))
        d1 = int(m.group("d1"))
        d2 = int(m.group("d2"))
        add(_safe_dt(year, m1, d1))
        add(_safe_dt(year, m2, d2))

    # Same-month ranges: "Mar 19–25 2017"
    for m in _RANGE_SAME_MONTH_RE.finditer(text):
        month = _month_str_to_int(m.group("m1"))  # note: group is m1 in the updated regex
        year = int(m.group("year"))
        d1 = int(m.group("d1"))
        d2 = int(m.group("d2"))
        add(_safe_dt(year, month, d1))
        add(_safe_dt(year, month, d2))

    return found
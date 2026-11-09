"""Formula functions that must never be written into a workbook.

These functions reach outside the document: they call external programs or DLLs (CALL, EXEC, SHELL,
REGISTER), pull data from external sources (DDE, RTD, SQL.REQUEST, WEBSERVICE), follow links
(HYPERLINK) or resolve references dynamically (INDIRECT). A value write already refuses formula
prefixes; this list guards the paths that intentionally write formulas — spreadsheet-formula-write
and the HTML data-formula restore — so a crafted formula cannot smuggle one in.
"""

from __future__ import annotations

import re

FORBIDDEN_FORMULA_FUNCTIONS = (
    "CALL",
    "DDE",
    "EXEC",
    "HYPERLINK",
    "INDIRECT",
    "REGISTER",
    "RTD",
    "SHELL",
    "SQL.REQUEST",
    "WEBSERVICE",
)

# Excel stores functions newer than 2007 with a namespace prefix in the file (=_xlfn.WEBSERVICE(...),
# _xlws. for worksheet-only ones), and both spellings calculate; the prefix must not hide the name.
_PREFIX = r"(?:_xlfn\.|_xlws\.)?"
_FORBIDDEN = re.compile(
    r"(?<![A-Z0-9_.])" + _PREFIX + r"(" + "|".join(re.escape(name) for name in FORBIDDEN_FORMULA_FUNCTIONS) + r")\s*\(",
    re.IGNORECASE,
)


def forbidden_formula_function(formula: str) -> str | None:
    """The forbidden function a formula calls, upper-cased, or None when the formula is clean."""
    match = _FORBIDDEN.search(formula)
    return match.group(1).upper() if match else None

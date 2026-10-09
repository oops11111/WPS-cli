from __future__ import annotations

from typing import Any

from openpyxl.utils.cell import range_boundaries


MAX_SPREADSHEET_READ_CELLS = 10_000
MAX_EXCEL_ROWS = 1_048_576
MAX_EXCEL_COLUMNS = 16_384


def validate_spreadsheet_read_range(
    range_address: Any,
    max_cells: int = MAX_SPREADSHEET_READ_CELLS,
) -> tuple[tuple[int, int, int, int] | None, dict[str, str] | None]:
    if not isinstance(range_address, str) or not range_address.strip():
        return None, {"code": "INVALID_RANGE", "message": "A finite A1 cell range is required."}
    address = range_address.strip()
    if "!" in address:
        return None, {
            "code": "INVALID_RANGE",
            "message": "Sheet-qualified ranges such as Sheet1!A1:B2 are not supported; pass the sheet separately when the command allows it, and use a finite A1 range like A1:B2.",
        }
    if ":" in address:
        start, _, end = address.partition(":")
        if start and end and (
            (start.isalpha() and end.isalpha())
            or (start.isdigit() and end.isdigit())
        ):
            return None, {
                "code": "INVALID_RANGE",
                "message": "Whole-column and whole-row ranges such as A:A or 1:1 are not supported; use a finite A1 range like A1:A100.",
            }
    try:
        min_col, min_row, max_col, max_row = range_boundaries(address)
    except (TypeError, ValueError) as exc:
        message = str(exc)
        if "!" in address or message.lower().startswith("invalid"):
            message = f"{message}; a finite A1 cell range without a sheet qualifier is required."
        return None, {"code": "INVALID_RANGE", "message": message}
    if not min_col or not min_row or not max_col or not max_row:
        return None, {"code": "INVALID_RANGE", "message": "A finite A1 cell range is required."}
    if max_col > MAX_EXCEL_COLUMNS or max_row > MAX_EXCEL_ROWS:
        return None, {"code": "INVALID_RANGE", "message": "Range exceeds Excel worksheet limits."}
    if min_col > max_col or min_row > max_row:
        return None, {"code": "INVALID_RANGE", "message": "Range start must not follow its end."}
    cell_count = (max_col - min_col + 1) * (max_row - min_row + 1)
    if cell_count > max_cells:
        return None, {
            "code": "RANGE_TOO_LARGE",
            "message": f"Range contains {cell_count} cells; the maximum is {max_cells}.",
        }
    return (min_col, min_row, max_col, max_row), None

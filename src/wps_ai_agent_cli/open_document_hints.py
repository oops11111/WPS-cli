"""Point a file-based write that was refused on a document open in WPS to the open-document tools (P9-001).

A file-based write (writer-replace, presentation-replace, spreadsheet-write, ...) cannot change a document WPS has
open: WPS holds the file, so the command refuses before it writes anything. That refusal is right, but in P8-008
it did not say what to do instead, and agents tried the same tool again before finding the selection tools. The
hint below names them and says how the arguments carry over.
"""

from __future__ import annotations

from typing import Any

from .errors import COM_OPERATION_FAILED, DOCUMENT_HELD_OPEN

_SELECTION_WORKFLOW = (
    "If the document is open in WPS, file-based tools cannot change it; use the open-document tools instead. "
    "Call wps_agent_open_documents (CLI open-documents) with register to get its document_id, then work on the "
    "current selection in WPS: {read} shows what is selected; {replace} replaces it{replace_args}; {insert}"
    "{delete} deletes it. They write in WPS, take a backup first, save, and undo the write in WPS if a check fails. "
    "Select the target in WPS first (or ask the user to)."
)


def _workflow(component: str, replace_args: str, insert: str) -> str:
    return _SELECTION_WORKFLOW.format(
        read=f"wps_agent_{component}_selection_read",
        replace=f"wps_agent_{component}_selection_replace",
        replace_args=replace_args,
        insert=insert,
        delete=f"wps_agent_{component}_selection_delete",
    )


_WRITER = _workflow(
    "writer",
    " (text = the new text; select what find matched)",
    "wps_agent_writer_selection_insert inserts text at a collapsed caret; ",
)
_PRESENTATION = _workflow(
    "presentation",
    " (text = the new text; select what find matched, inside one text box)",
    "wps_agent_presentation_selection_insert inserts text at a caret in a text box; ",
)
_SPREADSHEET = _workflow(
    "spreadsheet",
    " (text fills every selected cell; values_json writes a matrix of the selection's shape)",
    "",
)
_SHEET_STRUCTURE = (
    "If the workbook is open in WPS, this command cannot change it, and there is no open-document tool for sheet "
    "structure. Save the workbook in WPS (wps_agent_save_open_document) and close it there, then retry."
)

# The file-based commands that change a document, and what to use when the document is open in WPS.
OPEN_DOCUMENT_ALTERNATIVES: dict[str, str] = {
    "writer-replace": _WRITER,
    "writer-fill-bookmark": _WRITER,
    "writer-table-write": _WRITER,
    "presentation-replace": _PRESENTATION,
    "spreadsheet-write": _SPREADSHEET,
    "spreadsheet-formula-write": _SPREADSHEET,
    "spreadsheet-rename-sheet": _SHEET_STRUCTURE,
    "spreadsheet-create-sheet": _SHEET_STRUCTURE,
    "spreadsheet-set-sheet-visibility": _SHEET_STRUCTURE,
    "spreadsheet-delete-sheet": _SHEET_STRUCTURE,
    "spreadsheet-copy-sheet": _SHEET_STRUCTURE,
    "spreadsheet-set-sheet-tab-color": _SHEET_STRUCTURE,
}


# What the pre-open guards in the PowerShell scripts say (wps_script_snippets); they surface as COM_OPERATION_FAILED.
_GUARD_PHRASES = ("is open in WPS", "already open in WPS")


def _refused_as_open(error: dict[str, Any]) -> bool:
    """The command refused because WPS has the document open: the held-file code, or a pre-open guard.

    Rollback errors that mention WPS (the write already happened) are not refusals and get no hint.
    """
    code = error.get("code")
    if code == DOCUMENT_HELD_OPEN:
        return True
    message = str(error.get("message") or "")
    return code == COM_OPERATION_FAILED and any(phrase in message for phrase in _GUARD_PHRASES)


def add_open_document_hint(command: str, errors: list[dict[str, Any]]) -> bool:
    """Append the open-document hint to each error of `command` that refused a document open in WPS.

    Returns whether a hint was added. Errors of other commands, and other errors, are left as they are.
    """
    hint = OPEN_DOCUMENT_ALTERNATIVES.get(command)
    if hint is None:
        return False
    added = False
    for error in errors:
        if not isinstance(error, dict) or not _refused_as_open(error):
            continue
        message = str(error.get("message") or "")
        if hint not in message:
            error["message"] = f"{message} {hint}".strip()
            added = True
    return added

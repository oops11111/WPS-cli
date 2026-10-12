"""Run the real CLI with a test-only in-memory injection (no production hook, no repo edits).

Makes both "is it open?" checks answer "not open", so Open-WpsDocument / Open-WpsPresentation
reach Assert-WpsFileNotHeld (and, on older builds, Open()). Use this to force the file-lock
probe path while the document is actually open in the user's WPS.

Optional C2_TRACE_FILE: append one JSON line right after Open() returns (proves Open was reached).

usage (PYTHONPATH=<repo>\\src):
  python inject_driver.py spreadsheet-inspect --document-id ... --range A1:A1
  python inject_driver.py writer-replace --document-id ... --find ALPHA --replace BETA
  python inject_driver.py presentation-replace --document-id ... --find ALPHA --replace BETA
  python inject_driver.py spreadsheet-write --document-id ... --range A1:A1 --values-json "[[9]]"
"""
from __future__ import annotations

import sys

PATH_OPEN_MARKER = "function Test-WpsPathOpen($collection, [string]$path) {"
FIND_MARKER = "function Find-WpsOpenDocument($collection, [string]$path) {"
COUNT_CHECK_MARKER = (
    "  if ([int]$collection.Count -le $countBefore) {\n"
    "    # Nothing new appeared in the collection"
)
# Presentation path uses a slightly different Count check comment-less form in some builds;
# also patch the Workbooks Open path used by documents.
TRACE_SNIPPET = r"""  try {
    $c2File = [string]$env:C2_TRACE_FILE
    if ($c2File) {
      $c2Saved = $null
      try { $c2Saved = [bool]$opened.Saved } catch { }
      $c2Line = (@{ event = 'open_returned'; count_before = $countBefore; count_after = [int]$collection.Count; returned_saved = $c2Saved } | ConvertTo-Json -Compress)
      Add-Content -LiteralPath $c2File -Encoding UTF8 -Value $c2Line
    }
  } catch { }
"""


def patch_guard(guard: str) -> str:
    for marker in (PATH_OPEN_MARKER, FIND_MARKER):
        if guard.count(marker) != 1:
            raise SystemExit("PRE_OPEN_GUARD changed; update markers in inject_driver.py: " + marker.splitlines()[0])
    patched = guard.replace(PATH_OPEN_MARKER, PATH_OPEN_MARKER + "\n  return $false", 1)
    patched = patched.replace(FIND_MARKER, FIND_MARKER + "\n  return $null", 1)
    if COUNT_CHECK_MARKER in patched and patched.count(COUNT_CHECK_MARKER) == 1:
        patched = patched.replace(COUNT_CHECK_MARKER, TRACE_SNIPPET + COUNT_CHECK_MARKER, 1)
    return patched


def apply_patch() -> None:
    from wps_ai_agent_cli import (
        com_backend,
        presentation_ops,
        spreadsheet_inspect,
        spreadsheet_ops,
        wps_script_snippets,
        writer_ops,
    )

    patched = patch_guard(wps_script_snippets.PRE_OPEN_GUARD)
    wps_script_snippets.PRE_OPEN_GUARD = patched
    for mod in (spreadsheet_ops, spreadsheet_inspect, writer_ops, presentation_ops, com_backend):
        if hasattr(mod, "PRE_OPEN_GUARD"):
            mod.PRE_OPEN_GUARD = patched


def main(argv: list[str]) -> int:
    from wps_ai_agent_cli import cli

    apply_patch()
    return cli.run(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

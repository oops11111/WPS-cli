"""Run the real CLI with a test-only injection that reproduces "the document was opened after the last check".

The CLI's own PowerShell text is patched in memory (nothing in the repo is modified, no production hook exists):

* ``Test-WpsPathOpen`` answers "closed" (the caller's first check lost the race), and
* ``Find-WpsOpenDocument`` answers "not found" (the recheck right before ``Open()`` lost it too),

so ``Open-WpsDocument`` is not stopped by either look. On a build that calls ``Workbooks.Open()`` next (main@bec1c64),
real ET reloads the open workbook from disk (unsaved edits are lost), ``Count`` does not grow and the command is then
refused. A build with a file-lock probe before ``Open()`` is expected to refuse without calling it.

When ``C2_TRACE_FILE`` is set, one JSON line is appended right after ``Open()`` returns with the workbook count
before/after and the returned object's ``Saved`` and ``B2``; that proves Open() was reached.

usage (PYTHONPATH=<repo>\\src):
    python c2_post_open_driver.py spreadsheet-write --document-id doc_xxx --range A1:A1 --values-json "[[6]]"
"""

import sys

PATH_OPEN_MARKER = "function Test-WpsPathOpen($collection, [string]$path) {"
FIND_MARKER = "function Find-WpsOpenDocument($collection, [string]$path) {"
COUNT_CHECK_MARKER = "  if ([int]$collection.Count -le $countBefore) {\n    # Nothing new appeared in the collection"
TRACE_SNIPPET = r"""  try {
    $c2File = [string]$env:C2_TRACE_FILE
    if ($c2File) {
      $c2Saved = $null; $c2B2 = $null
      try { $c2Saved = [bool]$opened.Saved } catch { }
      try { $c2B2 = [string]$opened.Worksheets.Item(1).Range('B2').Value2 } catch { }
      $c2Line = (@{ event = 'open_returned'; count_before = $countBefore; count_after = [int]$collection.Count; returned_saved = $c2Saved; returned_b2 = $c2B2 } | ConvertTo-Json -Compress)
      Add-Content -LiteralPath $c2File -Encoding UTF8 -Value $c2Line
    }
  } catch { }
"""


def patch_guard(guard: str) -> str:
    for marker in (PATH_OPEN_MARKER, FIND_MARKER, COUNT_CHECK_MARKER):
        if guard.count(marker) != 1:
            raise SystemExit("PRE_OPEN_GUARD changed; update the markers in this driver: " + marker.splitlines()[0])
    patched = guard.replace(PATH_OPEN_MARKER, PATH_OPEN_MARKER + "\n  return $false", 1)
    patched = patched.replace(FIND_MARKER, FIND_MARKER + "\n  return $null", 1)
    return patched.replace(COUNT_CHECK_MARKER, TRACE_SNIPPET + COUNT_CHECK_MARKER, 1)


def main(argv: list[str]) -> int:
    from wps_ai_agent_cli import cli, spreadsheet_ops, wps_script_snippets

    spreadsheet_ops.PRE_OPEN_GUARD = patch_guard(wps_script_snippets.PRE_OPEN_GUARD)
    return cli.run(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

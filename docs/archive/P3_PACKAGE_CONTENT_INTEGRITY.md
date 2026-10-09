# Package Content Integrity

P3-071 selects a correctness fix in the existing coverage/readiness commands.
Path presence and package modification time cannot prove that packaged content
matches the workspace: copying a ZIP or preserving file timestamps can hide changes.

P3-072 scope: stream SHA-256 comparisons for shared sync-root entries, report
changed content and obsolete entries, reject duplicate normalized entry names,
and propagate integrity failures through readiness. Keep the existing cutoff
diagnostics for compatibility. Do not extract archive paths or modify documents.

Validation: identical content passes; same-size edits with restored timestamps,
obsolete entries and duplicate archive entries fail; truncated output must not
truncate counts. Read failures must produce structured errors. Test readiness
propagation and run the existing unit suite. All work remains local.

Next: P3-073 audits original product requirements against executable evidence to
prioritize document automation gaps instead of adding more status wrappers.

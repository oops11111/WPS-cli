"""Check a release tag against the package version and print that version's CHANGELOG section (P5-008).

    python scripts/release_notes.py --tag v0.2.0 > release-notes.md

Exits 1 with a reason when the tag is not v<__version__>, or CHANGELOG.md has no dated, non-empty section for
that version. The release workflow runs it before it builds anything.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HEADING = re.compile(r"^## \[(?P<version>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?\s*$", re.M)


class ReleaseError(Exception):
    pass


def version_section(changelog: str, version: str) -> tuple[str | None, str]:
    """(date, body) of the section for version; body excludes the heading and ends before the next section."""
    headings = list(HEADING.finditer(changelog))
    for index, match in enumerate(headings):
        if match.group("version") == version:
            end = headings[index + 1].start() if index + 1 < len(headings) else len(changelog)
            return match.group("date"), changelog[match.end() : end].strip()
    raise ReleaseError(f"CHANGELOG.md has no section for {version}")


def release_notes(tag: str, package_version: str, changelog: str) -> str:
    if tag != f"v{package_version}":
        raise ReleaseError(
            f"tag {tag} does not match the package version {package_version} (expected v{package_version})"
        )
    date, body = version_section(changelog, package_version)
    if date is None:
        raise ReleaseError(
            f"the CHANGELOG.md section for {package_version} has no date: use '## [{package_version}] - YYYY-MM-DD'"
        )
    if not body:
        raise ReleaseError(f"the CHANGELOG.md section for {package_version} is empty")
    return body + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="The pushed tag, for example v0.2.0.")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from wps_ai_agent_cli import __version__

    try:
        notes = release_notes(args.tag, __version__, (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    except ReleaseError as exc:
        print(f"release check failed: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

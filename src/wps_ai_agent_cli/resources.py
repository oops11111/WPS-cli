"""Configuration files shipped inside the package, so an installed wheel works without the repository.

The repository keeps the files under config/. The package carries identical copies under resources/
(tests/test_packaged_resources.py keeps them in step). A command that is given one of the default config/
paths uses, in order: the file at that path from the current directory, the file in the source checkout the
package runs from, and the packaged copy.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = PACKAGE_DIR / "resources"
# The default config/ paths that have a packaged copy, by the copy's file name.
SHIPPED_CONFIG = {
    "config/regression_manifest.json": "regression_manifest.json",
    "config/mcp_catalog_guard.json": "mcp_catalog_guard.json",
    "config/mcp_client_config.regression.template.json": "mcp_client_config.regression.template.json",
}


def resolve_config(path: str | Path) -> Path:
    """Path(path) when it exists; for a default config/ path that does not, the checkout's file or the packaged copy.

    Any other path is returned unchanged, so a missing file the caller named is still reported as missing.
    """
    candidate = Path(path)
    if candidate.exists():
        return candidate
    shipped = SHIPPED_CONFIG.get(candidate.as_posix())
    if shipped is None:
        return candidate
    checkout = source_checkout()
    if checkout is not None and (checkout / candidate).is_file():
        return checkout / candidate
    if (RESOURCE_DIR / shipped).is_file():
        return RESOURCE_DIR / shipped
    return candidate


def source_checkout() -> Path | None:
    """The repository root when the package is running from a source checkout (src layout), else None."""
    root = PACKAGE_DIR.parents[1]
    if (root / "src" / PACKAGE_DIR.name).is_dir() and (root / "pyproject.toml").is_file():
        return root
    return None

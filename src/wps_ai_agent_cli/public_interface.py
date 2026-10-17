"""The public interface, as a committed inventory that a test keeps in step with the code (P12-006).

What callers depend on: the CLI commands and their arguments, the MCP tools and their parameters, and the error
codes. Each is read from the code itself: the argparse parser, the MCP tool schemas, and the error codes the
sources return. `config/public_interface.json` holds the inventory; `scripts/public_interface.py --write`
regenerates it, and `tests/test_public_interface.py` fails when the code and the file differ, so an interface
change is always a visible change to that file. docs/RELEASING.md says which changes are breaking.

The fields under `data` in each response are built at run time and have no schema to read, so they are not in the
inventory; RELEASING.md's rules cover them (adding a field is not breaking, removing or renaming one is).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

INVENTORY_VERSION = 1
PACKAGE_ROOT = Path(__file__).resolve().parent

# An error code is an upper-case identifier, given as "code": "..." or through a constant: "code": NAME, where
# NAME = "..." is defined in some module (errors.py and its siblings), or a constant named after its value.
_CODE_LITERAL = re.compile(r"""["']code["']\s*:\s*["']([A-Z][A-Z0-9_]{2,})["']""")
_CODE_NAME = re.compile(r"""["']code["']\s*:\s*([A-Z][A-Z0-9_]{2,})\b""")
_CONSTANT = re.compile(r"""^([A-Z][A-Z0-9_]{2,})\s*=\s*["']([A-Z][A-Z0-9_]{2,})["']""", re.MULTILINE)


def _arguments(parser: argparse.ArgumentParser) -> list[dict[str, Any]]:
    arguments = []
    for action in parser._actions:  # noqa: SLF001 - argparse has no public list of a parser's arguments
        if isinstance(action, (argparse._HelpAction, argparse._SubParsersAction)):  # noqa: SLF001
            continue
        name = max(action.option_strings, key=len) if action.option_strings else action.dest
        entry: dict[str, Any] = {"name": name, "required": bool(action.required or not action.option_strings)}
        if action.choices:
            entry["choices"] = sorted(str(choice) for choice in action.choices)
        arguments.append(entry)
    return sorted(arguments, key=lambda item: item["name"])


def cli_global_options() -> list[dict[str, Any]]:
    """The options given before the command (for example --request-id), which every command takes."""
    from .cli_parser import build_parser

    return _arguments(build_parser())


def cli_commands() -> dict[str, list[dict[str, Any]]]:
    from .cli_parser import build_parser

    parser = build_parser()
    commands: dict[str, list[dict[str, Any]]] = {}
    for action in parser._actions:  # noqa: SLF001
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            for name, subparser in action.choices.items():
                commands[name] = _arguments(subparser)
    return dict(sorted(commands.items()))


def mcp_tools() -> dict[str, dict[str, Any]]:
    from .mcp_schema import list_mcp_tool_schemas

    tools = {}
    for schema in list_mcp_tool_schemas():
        properties = schema["input_schema"].get("properties") or {}
        tools[schema["name"]] = {
            "cli_command": schema["cli_command"],
            "mutates_document": bool(schema["mutates_document"]),
            "parameters": sorted(properties),
            "required": sorted(schema["input_schema"].get("required") or []),
        }
    return dict(sorted(tools.items()))


def error_codes() -> list[str]:
    literals: set[str] = set()
    names: set[str] = set()
    constants: dict[str, str] = {}
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        literals.update(_CODE_LITERAL.findall(text))
        names.update(_CODE_NAME.findall(text))
        for name, value in _CONSTANT.findall(text):
            constants.setdefault(name, value)
    errors_module = (PACKAGE_ROOT / "errors.py").read_text(encoding="utf-8")
    codes = literals | {constants[name] for name in names if name in constants}
    codes |= {value for _name, value in _CONSTANT.findall(errors_module)}
    codes |= {value for name, value in constants.items() if name == value}
    return sorted(codes)


def build_inventory() -> dict[str, Any]:
    return {
        "inventory_version": INVENTORY_VERSION,
        "cli_global_options": cli_global_options(),
        "cli_commands": cli_commands(),
        "mcp_tools": mcp_tools(),
        "error_codes": error_codes(),
    }


def diff_inventories(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """What changed between two inventories, one line each, marking the changes RELEASING.md calls breaking."""
    lines: list[str] = []
    for section in ("cli_commands", "mcp_tools"):
        before, after = old.get(section) or {}, new.get(section) or {}
        for name in sorted(set(before) - set(after)):
            lines.append(f"breaking: {section} {name} removed")
        for name in sorted(set(after) - set(before)):
            lines.append(f"added: {section} {name}")
        for name in sorted(set(before) & set(after)):
            if before[name] != after[name]:
                lines.append(f"changed: {section} {name}")
    before_options = {item["name"] for item in old.get("cli_global_options") or []}
    after_options = {item["name"] for item in new.get("cli_global_options") or []}
    lines += [f"breaking: global option {name} removed" for name in sorted(before_options - after_options)]
    lines += [f"added: global option {name}" for name in sorted(after_options - before_options)]
    before_codes, after_codes = set(old.get("error_codes") or []), set(new.get("error_codes") or [])
    lines += [f"breaking: error code {code} removed" for code in sorted(before_codes - after_codes)]
    lines += [f"added: error code {code}" for code in sorted(after_codes - before_codes)]
    return lines

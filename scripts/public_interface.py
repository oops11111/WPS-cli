"""Write or check config/public_interface.json, the inventory of the public interface (P12-006).

python scripts/public_interface.py --write   # after an intended interface change
python scripts/public_interface.py           # check: exit 1 and list the changes when the file is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from wps_ai_agent_cli.public_interface import build_inventory, diff_inventories  # noqa: E402

INVENTORY = REPO_ROOT / "config" / "public_interface.json"


def render(inventory: dict) -> str:
    return json.dumps(inventory, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true", help="Regenerate the inventory file.")
    args = parser.parse_args(argv)
    current = build_inventory()
    if args.write:
        INVENTORY.write_text(render(current), encoding="utf-8")
        print(f"wrote {INVENTORY.relative_to(REPO_ROOT)}")
        return 0
    committed = json.loads(INVENTORY.read_text(encoding="utf-8")) if INVENTORY.exists() else {}
    changes = diff_inventories(committed, current)
    if render(committed) == render(current):
        print("public interface unchanged")
        return 0
    print("config/public_interface.json is out of date; review, then run scripts/public_interface.py --write:")
    for line in changes or ["(argument details changed)"]:
        print(f"  {line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

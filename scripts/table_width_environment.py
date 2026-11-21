"""Stage42 runner-only environment and exact fresh-source snapshot gates."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch


def environment_gate(root):
    from wps_ai_agent_cli.html_styles import browser_runtime

    module_path = os.environ.get("NODE_PATH", "")
    if not module_path or not any(Path(p).is_dir() for p in module_path.split(os.pathsep)):
        raise ValueError("NODE_PATH missing or unresolved; no exports permitted")
    if os.environ.get("PYTHONUTF8") != "1":
        raise ValueError("PYTHONUTF8=1 required")
    for name in ("TEMP", "TMP"):
        if not os.environ.get(name):
            raise ValueError("Explicit workspace TEMP/TMP required")
        folder = Path(os.environ.get(name, "")).resolve()
        if not folder.is_relative_to(root.resolve()) or not folder.is_dir():
            raise ValueError("Workspace TEMP/TMP required")
        with tempfile.TemporaryFile(dir=folder):
            pass
    node, browser = browser_runtime()
    if not node or not browser or not Path(node).is_file() or not Path(browser).is_file():
        raise ValueError("No real Node/browser runtime")
    done = subprocess.run(
        [
            node,
            "-e",
            "console.log(JSON.stringify({module:require.resolve('playwright'),chromium:!!require('playwright').chromium,node:process.execPath,node_path:process.env.NODE_PATH}))",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    if done.returncode != 0:
        raise ValueError(f"Playwright resolution failed: {done.stderr}")
    result = json.loads(done.stdout)
    if result.get("chromium") is not True or not Path(result.get("module", "")).is_file():
        raise ValueError("Invalid resolved Playwright module")
    return {"node": node, "browser": browser, "playwright": result, "utf8": True, "workspace_temp": os.environ["TEMP"]}


def restore_snapshot(source, snapshot):
    """Parse only; never run browser or synthesize missing captured properties."""
    from paragraph_mark_font_mechanism import sha

    from wps_ai_agent_cli import html_styles

    if snapshot.get("mode") != "browser" or snapshot.get("source_sha256") != sha(source):
        raise ValueError("Not a matching current browser snapshot")
    styled = html_styles.load(source, use_browser=False)
    nodes = list(html_styles._walk(styled.root))
    entries = snapshot["elements"]
    if len(nodes) != len(entries):
        raise ValueError("Snapshot annotation count mismatch")
    styled.styles, styled.boxes, styled.pseudo, styled.summary_markers = {}, {}, {}, {}
    for n, entry in zip(nodes, entries, strict=True):
        if n.tag != entry["tag"] or n.attrs != entry["attrs"]:
            raise ValueError("Snapshot source/annotation mismatch")
        styled.styles[id(n)] = entry["style"]
        if entry["box"] is not None:
            styled.boxes[id(n)] = entry["box"]
        if entry.get("pseudo"):
            styled.pseudo[id(n)] = entry["pseudo"]
        if entry.get("summary_marker"):
            styled.summary_markers[id(n)] = entry["summary_marker"]
    styled.mode = "browser"
    styled.browser = snapshot["browser"]
    styled.print_context = snapshot["print_context"]
    styled.page = snapshot["page"]
    return styled


def semantic_snapshot(source, target, styled):
    from wps_ai_agent_cli import html_styles
    from wps_ai_agent_cli.fidelity import fidelity_check

    if styled.mode != "browser" or styled.source.resolve() != source.resolve():
        raise ValueError("Semantic source is not the verified browser snapshot")
    calls = []

    def same_source(path, **kwargs):
        if Path(path).resolve() != source.resolve():
            raise ValueError("Unexpected semantic source load")
        calls.append(str(path))
        return styled

    with patch.object(html_styles, "load", side_effect=same_source):
        result = fidelity_check(source, target, layout=False)
    if len(calls) != 1:
        raise ValueError("Semantic reader did not consume exact source snapshot")
    return result


def semantic_assessment(result):
    """Normalize explicitly N/A aspects without altering raw scores/verdicts."""
    record = result[1]
    verdict = record.get("verdict", {})
    aspects = record.get("aspects", {})
    effective, reasons = {}, {}
    valid = result[0] is True and record.get("group") == "A" and record.get("passed") is True
    valid = (
        valid
        and set(verdict).issubset({"text", "structure", "formatting", "data", "animations"})
        and all(v is True for v in verdict.values())
    )
    for key in ("text", "structure", "formatting", "data", "animations"):
        aspect = aspects.get(key)
        if key in {"data", "animations"} and aspect == {"status": "not applicable"}:
            effective[key] = key not in verdict or verdict[key] is True
            reasons[key] = "explicit N/A; raw verdict preserved"
        elif key != "animations" and isinstance(aspect, dict):
            score = aspect.get("score")
            effective[key] = (
                not isinstance(score, bool)
                and isinstance(score, (float, int))
                and score == 1.0
                and verdict.get(key) is True
                and "status" not in aspect
            )
            reasons[key] = "applicable score must equal1 and raw verdict true"
        else:
            effective[key] = False
            reasons[key] = "missing/unknown/contradictory aspect schema"
    return {
        "accepted": bool(valid and all(effective.values())),
        "effective_verdict": effective,
        "reasons": reasons,
        "raw_verdict": verdict,
    }


def semantic_pass(result):
    return semantic_assessment(result)["accepted"]


def audit_schemas(base, cases):
    from paragraph_mark_font_mechanism import sha

    audit = {}
    for case in cases:
        path = base / case / "semantic-fidelity.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        evaluation = semantic_assessment(raw)
        audit[case] = {"source_sha256": sha(path), "raw": raw, "evaluation": evaluation}
        if not evaluation["accepted"]:
            raise ValueError(f"Original semantic schema not accepted: {case}")
    return audit

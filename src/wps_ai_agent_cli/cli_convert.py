"""The convert and fidelity-check commands (Phase 13)."""

from __future__ import annotations

from typing import Any

from .convert import convert
from .fidelity import fidelity_check
from .models import CommandResponse, ValidationResult


def convert_response(
    request_id: str, input_path: str, output_path: str, check: bool = False, **options: Any
) -> CommandResponse:
    ok, data, errors = convert(input_path, output_path, **options)
    checks = [
        {"name": "output_created", "passed": ok, "details": data.get("output_path") or data.get("pages")},
    ]
    if ok and check and data.get("output_path"):
        checked, report, check_errors = fidelity_check(
            input_path, data["output_path"], layout=False, use_browser=options.get("use_browser", True)
        )
        if checked:
            data["fidelity"] = report
            checks.append({"name": "fidelity", "passed": report["passed"], "details": report["verdict"]})
        else:
            checks.append({"name": "fidelity", "passed": False, "details": check_errors})
    route = " -> ".join(data.get("route", [])) if ok else ""
    return CommandResponse(
        ok=ok,
        command="convert",
        request_id=request_id,
        backend="powershell-com" if "wps" in data.get("route", []) else "python",
        summary=f"Converted ({route})." if ok else "Conversion could not complete.",
        data=data,
        validation=ValidationResult(
            status="passed" if ok and all(c["passed"] for c in checks) else "failed", checks=checks
        ),
        errors=errors,
    )


def fidelity_check_response(
    request_id: str,
    source: str,
    target: str,
    renderer: str = "auto",
    layout: bool = True,
    baseline: float | None = None,
    use_browser: bool = True,
) -> CommandResponse:
    ok, data, errors = fidelity_check(
        source, target, renderer=renderer, layout=layout, baseline=baseline, use_browser=use_browser
    )
    passed = bool(ok and data.get("passed"))
    return CommandResponse(
        ok=ok,
        command="fidelity-check",
        request_id=request_id,
        backend="python",
        summary=(
            ("Fidelity thresholds met." if passed else "Fidelity below the thresholds; see aspects.")
            if ok
            else "Fidelity check could not run."
        ),
        data=data,
        validation=ValidationResult(
            status="passed" if passed else "failed",
            checks=[
                {"name": name, "passed": value, "details": data["aspects"][name].get("score")}
                for name, value in (data.get("verdict") or {}).items()
            ],
        ),
        errors=errors,
    )

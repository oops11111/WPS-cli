from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Phase:
    id: str
    name: str
    goal: str
    status: str
    exit_criteria: tuple[str, ...] = ()


PHASES: tuple[Phase, ...] = (
    Phase(
        id="phase0",
        name="Technical feasibility validation",
        status="done",
        goal=(
            "Validate WPS COM, ProgID fallback, conversion behavior, "
            "calculation fidelity, and HTML baseline before Phase 1."
        ),
        exit_criteria=(
            "WPS component ProgID matrix is recorded",
            "Minimal COM prototype can open, save a copy, and close documents",
            "Spreadsheet calculation can be verified against displayed values",
            "Conversion backend and loss matrix is documented",
            "Go/no-go recommendation for Phase 1 is written",
        ),
    ),
    Phase(
        id="phase1",
        name="MVP CLI",
        status="done",
        goal=(
            "Deliver an Agent-callable CLI with document_id, backup, "
            "validation, dry-run, JSON protocol, and core WPS operations."
        ),
    ),
    Phase(
        id="phase2",
        name="Agent-ready scalable version",
        status="done",
        goal=(
            "Add mature sessions, MCP reuse, batch operations, HTML modes, "
            "observability, and long-running task controls."
        ),
    ),
    Phase(
        id="phase3",
        name="Production-ready automation infrastructure",
        status="done",
        goal=("Strengthen recovery, security, performance, regression testing, and ecosystem integration."),
    ),
    Phase(
        id="phase4",
        name="Multi-environment and agent workflow readiness",
        status="done",
        goal=(
            "Prove the tools across WPS versions and agent clients, let agents complete real WPS "
            "write tasks safely with in-CLI recovery, and make the package releasable."
        ),
    ),
    Phase(
        id="phase5",
        name="First release and broader coverage",
        status="done",
        goal=(
            "Make every tool failure visible to agents, widen the agent evaluation beyond the four "
            "write tasks, and publish a first release that works without the repository."
        ),
    ),
    Phase(
        id="phase6",
        name="Documents the user opened",
        status="done",
        goal=(
            "Make the open-document tools work on documents the user opened the usual way, or say clearly "
            "when they cannot; prove agents can write to open documents; and release it as 0.3.0."
        ),
    ),
    Phase(
        id="phase7",
        name="Open-document writes: undo in WPS and full coverage",
        status="done",
        goal=(
            "Undo a failed open-document write inside WPS instead of a blocked file rollback, evaluate every "
            "open-document write command on Windows, run the Windows checks with one command, and release 0.4.0."
        ),
    ),
    Phase(
        id="phase8",
        name="Chinese content and workbooks opened the usual way",
        status="done",
        goal=(
            "Make Chinese content work end to end and close workbooks the user opened the usual way: test every "
            "path non-ASCII text takes, evaluate Chinese tasks on Windows, fix or explain the failing workbook "
            "close, and release 0.4.1 and 0.5.0."
        ),
    ),
    Phase(
        id="phase9",
        name="Right tools, lossless text export, clean Windows runs",
        status="done",
        goal=(
            "Make agents pick the open-document tools, keep every character in text exports, and end the Windows "
            "runs' WPS cleanly so no manual cleanup is needed; release 0.6.0."
        ),
    ),
    Phase(
        id="phase10",
        name="Self-verifying write results, undoable chart and shape writes",
        status="done",
        goal=(
            "Make open-document write results carry the verified document state so agents stop re-checking, undo "
            "failed chart and shape selection writes in WPS, and release 0.7.0."
        ),
    ),
)


def list_phases() -> list[dict[str, object]]:
    return [
        {
            "id": phase.id,
            "name": phase.name,
            "goal": phase.goal,
            "status": phase.status,
            "exit_criteria": list(phase.exit_criteria),
        }
        for phase in PHASES
    ]

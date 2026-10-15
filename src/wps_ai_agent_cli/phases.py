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
        status="active",
        goal=(
            "Make the open-document tools work on documents the user opened the usual way, or say clearly "
            "when they cannot; prove agents can write to open documents; and release it as 0.3.0."
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

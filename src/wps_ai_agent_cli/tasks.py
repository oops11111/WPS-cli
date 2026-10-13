from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources


@dataclass(frozen=True)
class ProjectTask:
    id: str
    phase: str
    title: str
    status: str
    acceptance: str


def _load_tasks() -> tuple[ProjectTask, ...]:
    """Read the task catalog that ships with the package (task_catalog.json)."""
    text = resources.files(__package__).joinpath("task_catalog.json").read_text(encoding="utf-8")
    return tuple(ProjectTask(**entry) for entry in json.loads(text))


TASKS: tuple[ProjectTask, ...] = _load_tasks()


def list_tasks(phase: str | None = None, status: str | None = None) -> list[dict[str, str]]:
    tasks = TASKS
    if phase:
        tasks = tuple(task for task in tasks if task.phase == phase)
    if status:
        tasks = tuple(task for task in tasks if task.status == status)
    return [
        {
            "id": task.id,
            "phase": task.phase,
            "title": task.title,
            "status": task.status,
            "acceptance": task.acceptance,
        }
        for task in tasks
    ]

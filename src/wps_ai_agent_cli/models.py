from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationResult:
    status: str
    checks: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class CommandResponse:
    ok: bool
    command: str
    request_id: str
    backend: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    validation: ValidationResult = field(
        default_factory=lambda: ValidationResult(status="not_applicable")
    )
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

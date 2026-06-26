from __future__ import annotations

from dataclasses import dataclass

from .llm_planner import PlannerArtifacts
from .models import ModSpec


@dataclass(slots=True)
class PlannerResolution:
    """Successful planner outcome for a full ModSpec or a patch ModSpec."""

    spec: ModSpec
    artifacts: PlannerArtifacts | None
    warnings: list[str]
    planner_mode_used: str

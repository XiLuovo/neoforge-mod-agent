from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class AppConfig:
    project_root: Path
    templates_root: Path
    template_name: str
    workspace_root: Path
    gradle_user_home: Path
    loader: str = "neoforge"
    neo_version: str = "26.1"
    java_version: int = 25
    default_mod_version: str = "0.1.0"
    default_license_name: str = "All Rights Reserved"
    default_group_prefix: str = "com.generated"
    gradle_task: str = "build"
    build_timeout_seconds: int = 900

    @property
    def template_dir(self) -> Path:
        return self.templates_root / self.template_name

    @classmethod
    def default(cls) -> "AppConfig":
        project_root = Path(os.environ.get("NEOFORGE_AGENT_ROOT", PROJECT_ROOT)).resolve()
        templates_root = Path(
            os.environ.get("NEOFORGE_AGENT_TEMPLATES_ROOT", project_root / "templates")
        ).resolve()
        workspace_root = Path(
            os.environ.get("NEOFORGE_AGENT_WORKSPACE_ROOT", project_root / "workspace")
        ).resolve()
        return cls(
            project_root=project_root,
            templates_root=templates_root,
            template_name="neoforge-26.1",
            workspace_root=workspace_root,
            gradle_user_home=(project_root / ".gradle-user-home").resolve(),
        )

    def agent_dir_for(self, project_dir: Path) -> Path:
        return project_dir / ".agent"

    def logs_dir_for(self, project_dir: Path) -> Path:
        return self.agent_dir_for(project_dir) / "logs"

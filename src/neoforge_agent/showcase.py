from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .agent_orchestrator import AgentOrchestrator
from .config import AppConfig
from .doctor import EnvironmentDoctor
from .evaluator import BenchmarkEvaluator
from .models import RequestOverrides
from .quality_gate import QualityGateRunner
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class ShowcaseStep:
    name: str
    status: str
    summary: str
    artifacts: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "artifacts": dict(self.artifacts),
            "metrics": dict(self.metrics),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(slots=True)
class ShowcaseResult:
    success: bool
    run_id: str
    showcase_dir: Path
    steps: list[ShowcaseStep]
    showcase_report_json_path: Path
    showcase_report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        passed = sum(1 for step in self.steps if step.status == "pass")
        failed = sum(1 for step in self.steps if step.status == "fail")
        skipped = sum(1 for step in self.steps if step.status == "skip")
        return {
            "success": self.success,
            "run_id": self.run_id,
            "showcase_dir": str(self.showcase_dir),
            "steps": [step.to_dict() for step in self.steps],
            "passed_count": passed,
            "failed_count": failed,
            "skipped_count": skipped,
            "steps_count": len(self.steps),
            "showcase_report_json_path": str(self.showcase_report_json_path),
            "showcase_report_md_path": str(self.showcase_report_md_path),
        }


class ShowcaseRunner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        planner_mode: str = "llm",
        llm_provider: str = "mock",
        run_build: bool = False,
        run_quality_gate: bool = False,
        eval_limit: int = 2,
    ) -> ShowcaseResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        showcase_dir = ensure_directory(self.config.workspace_root / "showcase-runs" / run_id)
        agent_dir = ensure_directory(showcase_dir / ".agent")
        scoped_workspace_root = ensure_directory(showcase_dir / "workspaces")
        scoped_config = replace(self.config, workspace_root=scoped_workspace_root)

        steps: list[ShowcaseStep] = []
        steps.append(self._run_doctor(run_id, scoped_config))
        steps.append(self._run_agent_generate(scoped_config, planner_mode, llm_provider, run_build))
        steps.append(self._run_agent_modify(scoped_config, planner_mode, llm_provider, run_build))
        steps.append(self._run_eval(run_id, scoped_config, planner_mode, llm_provider, eval_limit))
        steps.append(self._run_quality_gate(run_id, scoped_config) if run_quality_gate else self._skip_quality_gate())

        success = all(step.status in {"pass", "skip"} for step in steps)
        report_json = agent_dir / "showcase-report.json"
        report_md = agent_dir / "showcase-report.md"
        result = ShowcaseResult(
            success=success,
            run_id=run_id,
            showcase_dir=showcase_dir,
            steps=steps,
            showcase_report_json_path=report_json,
            showcase_report_md_path=report_md,
        )
        write_json(report_json, result.to_dict())
        write_text(report_md, self._render_report_md(result))
        return result

    def _run_doctor(self, run_id: str, config: AppConfig) -> ShowcaseStep:
        result = EnvironmentDoctor(config).run(run_name=f"{run_id}-doctor", check_java=False)
        return ShowcaseStep(
            name="doctor",
            status="pass" if result.success else "fail",
            summary="Environment doctor preflight completed.",
            artifacts={
                "doctor_report_json": str(result.doctor_report_json_path),
                "doctor_report_md": str(result.doctor_report_md_path),
            },
            metrics={
                "passed": result.to_dict()["passed_count"],
                "warnings": result.to_dict()["warnings_count"],
                "failed": result.to_dict()["failed_count"],
                "skipped": result.to_dict()["skipped_count"],
            },
            warnings=[check.message for check in result.checks if check.status == "warning"],
            errors=[check.message for check in result.checks if check.status == "fail"],
        )

    def _run_agent_generate(
        self,
        config: AppConfig,
        planner_mode: str,
        llm_provider: str,
        run_build: bool,
    ) -> ShowcaseStep:
        run = AgentOrchestrator(config).run_generate(
            "Create a ruby mod with a ruby charm item.",
            overrides=RequestOverrides(),
            planner_mode=planner_mode,
            llm_provider=llm_provider,
            workspace_name="showcase-agent-generate",
            overwrite=True,
            run_build=run_build,
            run_audit=True,
            repair=True,
        )
        return ShowcaseStep(
            name="agent_generate",
            status="pass" if run.success else "fail",
            summary="Generated a behavior item workspace through the multi-role agent workflow.",
            artifacts={
                "workspace": str(run.workspace or ""),
                "agent_run_json": str(run.agent_run_json_path or ""),
                "agent_run_md": str(run.agent_run_md_path or ""),
                "agent_trace_summary_json": str(run.agent_trace_summary_json_path or ""),
                "agent_trace_summary_md": str(run.agent_trace_summary_md_path or ""),
                "prompt_trace_json": str(run.prompt_trace_json_path or ""),
            },
            metrics={
                "steps": len(run.steps),
                "decisions": len(run.decisions),
                "prompt_traces": len(run.prompt_traces),
                "audit_success": run.payload.get("audit", {}).get("success"),
                "build_attempted": run.payload.get("generation", {}).get("build", {}).get("attempted"),
            },
            warnings=_agent_warnings(run.to_dict()),
            errors=_agent_errors(run.to_dict()),
        )

    def _run_agent_modify(
        self,
        config: AppConfig,
        planner_mode: str,
        llm_provider: str,
        run_build: bool,
    ) -> ShowcaseStep:
        orchestrator = AgentOrchestrator(config)
        setup = orchestrator.run_generate(
            "Create a ruby mod with ruby and ruby ore.",
            overrides=RequestOverrides(),
            planner_mode=planner_mode,
            llm_provider=llm_provider,
            workspace_name="showcase-agent-modify-base",
            overwrite=True,
            run_build=False,
            run_audit=True,
            repair=True,
        )
        if not setup.success or setup.workspace is None:
            return ShowcaseStep(
                name="agent_modify",
                status="fail",
                summary="Could not create the base workspace for the modify showcase.",
                artifacts={
                    "agent_run_json": str(setup.agent_run_json_path or ""),
                    "agent_run_md": str(setup.agent_run_md_path or ""),
                    "agent_trace_summary_json": str(setup.agent_trace_summary_json_path or ""),
                },
                errors=_agent_errors(setup.to_dict()) or ["Base workspace generation failed."],
            )

        run = orchestrator.run_modify(
            setup.workspace,
            "Make ruby ore generate underground in the overworld, Y -64 to 32, vein size 6, 4 per chunk.",
            planner_mode=planner_mode,
            llm_provider=llm_provider,
            run_build=run_build,
            run_audit=True,
            repair=True,
        )
        modify_payload = run.payload.get("modify", {})
        return ShowcaseStep(
            name="agent_modify",
            status="pass" if run.success else "fail",
            summary="Modified an existing workspace to add ore worldgen through the agent workflow.",
            artifacts={
                "workspace": str(run.workspace or ""),
                "agent_run_json": str(run.agent_run_json_path or ""),
                "agent_run_md": str(run.agent_run_md_path or ""),
                "agent_trace_summary_json": str(run.agent_trace_summary_json_path or ""),
                "agent_trace_summary_md": str(run.agent_trace_summary_md_path or ""),
                "prompt_trace_json": str(run.prompt_trace_json_path or ""),
                "patch_agent_plan_json": str(modify_payload.get("patch_agent", {}).get("plan_json_path", "")),
                "patch_agent_report_json": str(modify_payload.get("patch_agent", {}).get("report_json_path", "")),
                "patch_agent_rollback_json": str(modify_payload.get("patch_agent", {}).get("rollback_json_path", "")),
            },
            metrics={
                "added": len(modify_payload.get("added", [])),
                "updated": len(modify_payload.get("updated", [])),
                "skipped": len(modify_payload.get("skipped", [])),
                "decisions": len(run.decisions),
                "prompt_traces": len(run.prompt_traces),
                "audit_success": run.payload.get("audit", {}).get("success"),
                "build_attempted": modify_payload.get("build", {}).get("attempted"),
                "patch_agent_status": modify_payload.get("patch_agent", {}).get("status"),
            },
            warnings=_agent_warnings(run.to_dict()),
            errors=_agent_errors(run.to_dict()),
        )

    def _run_eval(
        self,
        run_id: str,
        config: AppConfig,
        planner_mode: str,
        llm_provider: str,
        eval_limit: int,
    ) -> ShowcaseStep:
        result = BenchmarkEvaluator(config).run(
            planner_mode=planner_mode,
            llm_provider=llm_provider,
            run_build=False,
            run_audit=True,
            run_name=f"{run_id}-eval",
            limit=eval_limit,
        )
        return ShowcaseStep(
            name="eval_smoke",
            status="pass" if result.success else "fail",
            summary="Ran the offline agent benchmark smoke suite.",
            artifacts={
                "eval_report_json": str(result.eval_report_json_path),
                "eval_report_md": str(result.eval_report_md_path),
            },
            metrics=result.metrics,
            warnings=[warning for case in result.cases for warning in case.warnings],
            errors=[error for case in result.cases for error in case.errors],
        )

    def _run_quality_gate(self, run_id: str, config: AppConfig) -> ShowcaseStep:
        result = QualityGateRunner(config).run(
            run_name=f"{run_id}-quality-gate",
            run_doctor=True,
            run_doctor_java=False,
            run_build_smoke=False,
        )
        return ShowcaseStep(
            name="quality_gate",
            status="pass" if result.success else "fail",
            summary="Ran the default fast quality gate inside the showcase workspace.",
            artifacts={
                "quality_gate_report_json": str(result.quality_gate_report_json_path),
                "quality_gate_report_md": str(result.quality_gate_report_md_path),
            },
            metrics={
                "passed": result.to_dict()["passed_count"],
                "failed": result.to_dict()["failed_count"],
                "skipped": result.to_dict()["skipped_count"],
            },
            errors=[check.summary for check in result.checks if check.status == "fail"],
        )

    def _skip_quality_gate(self) -> ShowcaseStep:
        return ShowcaseStep(
            name="quality_gate",
            status="skip",
            summary="Quality gate was not requested. Pass --quality-gate to include it.",
        )

    def _render_report_md(self, result: ShowcaseResult) -> str:
        payload = result.to_dict()
        lines = [
            "# Showcase Report",
            "",
            f"Success: {str(result.success).lower()}",
            f"Run ID: `{result.run_id}`",
            f"Showcase dir: `{result.showcase_dir}`",
            f"Passed: {payload['passed_count']}",
            f"Failed: {payload['failed_count']}",
            f"Skipped: {payload['skipped_count']}",
            "",
            "## Story",
            "",
            "This showcase run demonstrates the current agent pipeline:",
            "",
            "- environment doctor preflight",
            "- mock LLM multi-role agent generation",
            "- modify existing workspace with worldgen update",
            "- benchmark eval smoke",
            "- optional quality gate",
            "",
            "## Steps",
            "",
        ]
        for step in result.steps:
            lines.append(f"- `{step.name}` `{step.status}`: {step.summary}")
            for key, value in step.artifacts.items():
                if value:
                    lines.append(f"  - {key}: `{value}`")
            if step.metrics:
                lines.append(f"  - metrics: `{step.metrics}`")
            for warning in step.warnings:
                lines.append(f"  - warning: {warning}")
            for error in step.errors:
                lines.append(f"  - error: {error}")
        lines.append("")
        return "\n".join(lines)


def _agent_warnings(payload: dict[str, Any]) -> list[str]:
    return [
        str(warning)
        for step in payload.get("steps", [])
        for warning in step.get("warnings", [])
    ]


def _agent_errors(payload: dict[str, Any]) -> list[str]:
    return [
        str(error)
        for step in payload.get("steps", [])
        for error in step.get("errors", [])
    ]

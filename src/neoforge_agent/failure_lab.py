from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .auditor import WorkspaceAuditor
from .config import AppConfig
from .models import ModSpec
from .planner import ModProjectPlanner
from .repair_loop import AutoRepairRunner
from .repair_rag import RepairRAGAdvisor
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class FailureLabCaseSpec:
    identifier: str
    title: str
    prompt: str
    fault: str
    expected_issue_prefixes: list[str]
    expected_rag_capabilities: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FailureLabCaseResult:
    identifier: str
    title: str
    prompt: str
    fault: str
    workspace: Path | None = None
    success: bool = False
    generation_success: bool = False
    fault_injected: bool = False
    injected_paths: list[str] = field(default_factory=list)
    expected_issue_prefixes: list[str] = field(default_factory=list)
    expected_rag_capabilities: list[str] = field(default_factory=list)
    detected_issue_ids: list[str] = field(default_factory=list)
    detected_expected_failure: bool = False
    initial_audit_success: bool | None = None
    initial_audit_errors_count: int = 0
    initial_audit_report_path: str | None = None
    repair_rag_attempted: bool = False
    repair_rag_hits_count: int = 0
    repair_rag_knowledge_ids: list[str] = field(default_factory=list)
    repair_rag_capabilities: list[str] = field(default_factory=list)
    repair_rag_categories: list[str] = field(default_factory=list)
    repair_rag_relevant: bool = False
    repair_rag_report_json_path: str | None = None
    repair_rag_report_md_path: str | None = None
    repair_success: bool | None = None
    repair_attempts_count: int = 0
    repair_loop_report_json_path: str | None = None
    repair_loop_report_md_path: str | None = None
    final_audit_success: bool | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "title": self.title,
            "prompt": self.prompt,
            "fault": self.fault,
            "workspace": str(self.workspace) if self.workspace else None,
            "success": self.success,
            "generation_success": self.generation_success,
            "fault_injected": self.fault_injected,
            "injected_paths": list(self.injected_paths),
            "expected_issue_prefixes": list(self.expected_issue_prefixes),
            "expected_rag_capabilities": list(self.expected_rag_capabilities),
            "detected_issue_ids": list(self.detected_issue_ids),
            "detected_expected_failure": self.detected_expected_failure,
            "initial_audit_success": self.initial_audit_success,
            "initial_audit_errors_count": self.initial_audit_errors_count,
            "initial_audit_report_path": self.initial_audit_report_path,
            "repair_rag_attempted": self.repair_rag_attempted,
            "repair_rag_hits_count": self.repair_rag_hits_count,
            "repair_rag_knowledge_ids": list(self.repair_rag_knowledge_ids),
            "repair_rag_capabilities": list(self.repair_rag_capabilities),
            "repair_rag_categories": list(self.repair_rag_categories),
            "repair_rag_relevant": self.repair_rag_relevant,
            "repair_rag_report_json_path": self.repair_rag_report_json_path,
            "repair_rag_report_md_path": self.repair_rag_report_md_path,
            "repair_success": self.repair_success,
            "repair_attempts_count": self.repair_attempts_count,
            "repair_loop_report_json_path": self.repair_loop_report_json_path,
            "repair_loop_report_md_path": self.repair_loop_report_md_path,
            "final_audit_success": self.final_audit_success,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class FailureLabResult:
    success: bool
    run_id: str
    report_dir: Path
    cases: list[FailureLabCaseResult]
    failure_lab_report_json_path: Path
    failure_lab_report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        passed = sum(1 for case in self.cases if case.success)
        failed = len(self.cases) - passed
        return {
            "success": self.success,
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "cases": [case.to_dict() for case in self.cases],
            "cases_count": len(self.cases),
            "passed_count": passed,
            "failed_count": failed,
            "repair_rag_hits_count": sum(case.repair_rag_hits_count for case in self.cases),
            "failure_lab_report_json_path": str(self.failure_lab_report_json_path),
            "failure_lab_report_md_path": str(self.failure_lab_report_md_path),
        }


class FailureLabRunner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        case_ids: list[str] | None = None,
        limit: int | None = None,
        run_build: bool = False,
    ) -> FailureLabResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        run_root = ensure_directory(self.config.workspace_root / "failure-lab-runs" / run_id)
        report_dir = ensure_directory(run_root / ".agent")
        workspaces_root = ensure_directory(run_root / "workspaces")
        lab_config = replace(self.config, workspace_root=workspaces_root)

        cases = self._select_cases(case_ids=case_ids, limit=limit)
        results = [self._run_case(case, lab_config=lab_config, run_build=run_build) for case in cases]
        success = bool(results) and all(case.success for case in results)

        report_json = report_dir / "failure-lab-report.json"
        report_md = report_dir / "failure-lab-report.md"
        result = FailureLabResult(
            success=success,
            run_id=run_id,
            report_dir=report_dir,
            cases=results,
            failure_lab_report_json_path=report_json,
            failure_lab_report_md_path=report_md,
        )
        write_json(report_json, result.to_dict())
        write_text(report_md, self._render_markdown(result))
        return result

    def _run_case(
        self,
        case: FailureLabCaseSpec,
        *,
        lab_config: AppConfig,
        run_build: bool,
    ) -> FailureLabCaseResult:
        result = FailureLabCaseResult(
            identifier=case.identifier,
            title=case.title,
            prompt=case.prompt,
            fault=case.fault,
            expected_issue_prefixes=list(case.expected_issue_prefixes),
            expected_rag_capabilities=list(case.expected_rag_capabilities),
        )
        planner = ModProjectPlanner(lab_config)
        auditor = WorkspaceAuditor(lab_config)
        repair_runner = AutoRepairRunner(lab_config)
        repair_rag = RepairRAGAdvisor(lab_config)

        try:
            generation = planner.execute(
                case.prompt,
                workspace_name=case.identifier,
                overwrite=True,
                run_build=False,
            )
            result.workspace = generation.workspace_dir
            result.generation_success = generation.succeeded
            result.warnings.extend(generation.warnings)
            if not generation.succeeded:
                result.errors.append("Workspace generation failed before fault injection.")
                return result

            injected = self._inject_fault(case.identifier, generation.workspace_dir, generation.spec)
            result.fault_injected = bool(injected)
            result.injected_paths = [str(path) for path in injected]
            if not injected:
                result.errors.append("No matching generated artifact was found to inject the requested fault.")
                return result

            audit = auditor.audit_workspace(generation.workspace_dir)
            result.initial_audit_success = audit.success
            result.initial_audit_errors_count = len(audit.errors)
            result.initial_audit_report_path = audit.audit_report_path
            result.detected_issue_ids = [issue.id for issue in audit.errors]
            result.detected_expected_failure = _matches_expected(result.detected_issue_ids, case.expected_issue_prefixes)

            repair_plan = [
                {
                    "id": "regenerate_managed_files",
                    "summary": "Regenerate managed files from .agent/modspec.json, then rerun audit/build checks.",
                    "artifact": audit.audit_report_path or "",
                }
            ]
            rag = repair_rag.advise(
                generation.workspace_dir,
                root_causes=[issue.message for issue in audit.errors],
                repair_plan=repair_plan,
                build_payload={"attempted": False, "success": None},
                audit_payload={**audit.to_dict(), "attempted": True},
            )
            result.repair_rag_attempted = rag.attempted
            result.repair_rag_hits_count = rag.hits_count
            result.repair_rag_knowledge_ids = [str(hit.get("id")) for hit in rag.hits if hit.get("id")]
            result.repair_rag_capabilities = sorted({str(hit.get("capability")) for hit in rag.hits if hit.get("capability")})
            result.repair_rag_categories = sorted({str(hit.get("category")) for hit in rag.hits if hit.get("category")})
            result.repair_rag_relevant = _matches_expected(result.repair_rag_capabilities, case.expected_rag_capabilities)
            result.repair_rag_report_json_path = str(rag.report_json_path) if rag.report_json_path else None
            result.repair_rag_report_md_path = str(rag.report_md_path) if rag.report_md_path else None

            repair = repair_runner.run(generation.workspace_dir, max_attempts=1, run_build=run_build, run_audit=True)
            result.repair_success = repair.success
            result.repair_attempts_count = len(repair.attempts)
            result.repair_loop_report_json_path = str(repair.repair_loop_report_json_path)
            result.repair_loop_report_md_path = str(repair.repair_loop_report_md_path)
            result.final_audit_success = _final_audit_success(repair.to_dict())
            result.success = (
                result.generation_success
                and result.fault_injected
                and result.initial_audit_success is False
                and result.detected_expected_failure
                and result.repair_rag_attempted
                and result.repair_success is True
                and result.final_audit_success is True
            )
            if not result.success:
                result.errors.append("Failure lab case did not satisfy detect -> explain -> repair expectations.")
        except Exception as exc:  # Lab reports should survive individual case failures.
            result.errors.append(f"{type(exc).__name__}: {exc}")
        return result

    def _select_cases(self, *, case_ids: list[str] | None, limit: int | None) -> list[FailureLabCaseSpec]:
        cases = default_failure_lab_cases()
        if case_ids:
            requested = set(case_ids)
            cases = [case for case in cases if case.identifier in requested]
        if limit is not None:
            cases = cases[: max(0, limit)]
        return cases

    def _inject_fault(self, case_id: str, workspace: Path, spec: ModSpec) -> list[Path]:
        if case_id == "delete_texture":
            item = spec.items[0] if spec.items else spec.all_item_like()[0]
            return _delete_existing(workspace, workspace / "src" / "main" / "resources" / "assets" / spec.mod_id / "textures" / "item" / f"{item.identifier}.png")
        if case_id == "delete_model":
            item = spec.items[0] if spec.items else spec.all_item_like()[0]
            return _delete_existing(workspace, workspace / "src" / "main" / "resources" / "assets" / spec.mod_id / "models" / "item" / f"{item.identifier}.json")
        if case_id == "delete_worldgen_json":
            ore = spec.ores[0]
            return _delete_existing(workspace, workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "worldgen" / "configured_feature" / f"{ore.identifier}.json")
        if case_id == "delete_behavior_java":
            item = next(item for item in spec.items if item.behavior is not None)
            class_name = "".join(part.capitalize() for part in item.identifier.split("_")) + "Item"
            return _delete_existing(workspace, workspace / "src" / "main" / "java" / Path(*spec.package_name.split(".")) / "item" / f"{class_name}.java")
        if case_id == "break_recipe_reference":
            return self._break_recipe_reference(workspace, spec)
        return []

    def _break_recipe_reference(self, workspace: Path, spec: ModSpec) -> list[Path]:
        if not spec.recipes:
            return []
        recipe = spec.recipes[0]
        path = workspace / "src" / "main" / "resources" / "data" / spec.mod_id / "recipe" / f"{recipe.identifier}.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        bad_reference = f"{spec.mod_id}:missing_failure_lab_material"
        if isinstance(data.get("key"), dict) and data["key"]:
            first_key = next(iter(data["key"]))
            data["key"][first_key] = bad_reference
        elif isinstance(data.get("ingredients"), list) and data["ingredients"]:
            data["ingredients"][0] = bad_reference
        else:
            data["result"] = {"id": bad_reference, "count": 1}
        write_json(path, data)
        return [path]

    def _render_markdown(self, result: FailureLabResult) -> str:
        lines = [
            "# Failure Lab Report",
            "",
            f"Success: {str(result.success).lower()}",
            f"Run ID: `{result.run_id}`",
            f"Cases: `{len(result.cases)}`",
            f"Passed: `{sum(1 for case in result.cases if case.success)}`",
            f"Failed: `{sum(1 for case in result.cases if not case.success)}`",
            f"Repair RAG hits: `{sum(case.repair_rag_hits_count for case in result.cases)}`",
            "",
            "## Cases",
            "",
        ]
        for case in result.cases:
            lines.extend(
                [
                    f"### {case.identifier}",
                    "",
                    f"- title: {case.title}",
                    f"- success: `{str(case.success).lower()}`",
                    f"- injected: `{str(case.fault_injected).lower()}`",
                    f"- initial audit success: `{case.initial_audit_success}`",
                    f"- detected expected failure: `{str(case.detected_expected_failure).lower()}`",
                    f"- repair RAG hits: `{case.repair_rag_hits_count}`",
                    f"- repair RAG relevant: `{str(case.repair_rag_relevant).lower()}`",
                    f"- repair success: `{case.repair_success}`",
                    f"- final audit success: `{case.final_audit_success}`",
                    f"- workspace: `{case.workspace or ''}`",
                    f"- audit report: `{case.initial_audit_report_path or ''}`",
                    f"- repair RAG report: `{case.repair_rag_report_md_path or ''}`",
                    f"- repair loop report: `{case.repair_loop_report_md_path or ''}`",
                    "",
                ]
            )
            if case.detected_issue_ids:
                lines.append("Detected issues:")
                lines.extend(f"- `{issue_id}`" for issue_id in case.detected_issue_ids)
                lines.append("")
            if case.errors:
                lines.append("Errors:")
                lines.extend(f"- {error}" for error in case.errors)
                lines.append("")
        return "\n".join(lines)


def default_failure_lab_cases() -> list[FailureLabCaseSpec]:
    return [
        FailureLabCaseSpec(
            identifier="delete_texture",
            title="Delete generated item texture",
            prompt="Create a ruby mod with ruby.",
            fault="Delete src/main/resources/assets/<modid>/textures/item/ruby.png.",
            expected_issue_prefixes=["item:ruby:texture", "textures:manifest"],
            expected_rag_capabilities=["texture_audit", "procedural_textures", "assets_models_textures"],
        ),
        FailureLabCaseSpec(
            identifier="delete_model",
            title="Delete generated item model",
            prompt="Create a ruby mod with ruby.",
            fault="Delete src/main/resources/assets/<modid>/models/item/ruby.json.",
            expected_issue_prefixes=["item:ruby:model", "summary:"],
            expected_rag_capabilities=["assets_models_textures"],
        ),
        FailureLabCaseSpec(
            identifier="delete_worldgen_json",
            title="Delete ore worldgen configured feature",
            prompt="Create a ruby mod with ruby and ruby ore. Ruby ore drops ruby and generates in the overworld underground with Y -64 to 32, vein size 6, count 4.",
            fault="Delete data/<modid>/worldgen/configured_feature/ruby_ore.json.",
            expected_issue_prefixes=["ore:ruby_ore:configured_feature", "summary:"],
            expected_rag_capabilities=["overworld_ore"],
        ),
        FailureLabCaseSpec(
            identifier="delete_behavior_java",
            title="Delete behavior item Java class",
            prompt="Create a ruby mod with ruby charm, right click heal 4 health, cooldown 20 seconds.",
            fault="Delete generated RubyCharmItem.java.",
            expected_issue_prefixes=["item:ruby_charm:behavior_class", "summary:"],
            expected_rag_capabilities=["right_click_behavior"],
        ),
        FailureLabCaseSpec(
            identifier="break_recipe_reference",
            title="Break recipe JSON reference",
            prompt="Create a ruby mod with ruby tool set.",
            fault="Rewrite the first generated recipe JSON reference to <modid>:missing_failure_lab_material.",
            expected_issue_prefixes=["recipe:"],
            expected_rag_capabilities=["recipes_loot_tags"],
        ),
    ]


def _delete_existing(workspace: Path, path: Path) -> list[Path]:
    resolved = path.resolve()
    if workspace.resolve() not in resolved.parents:
        return []
    if not path.exists():
        return []
    path.unlink()
    return [path]


def _matches_expected(issue_ids: list[str], expected_prefixes: list[str]) -> bool:
    return any(any(issue_id.startswith(prefix) for prefix in expected_prefixes) for issue_id in issue_ids)


def _final_audit_success(repair_payload: dict[str, Any]) -> bool | None:
    attempts = repair_payload.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return None
    audit = attempts[-1].get("audit") if isinstance(attempts[-1], dict) else None
    if not isinstance(audit, dict) or not audit.get("attempted"):
        return None
    return audit.get("success")

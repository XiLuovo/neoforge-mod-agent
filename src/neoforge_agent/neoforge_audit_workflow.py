from __future__ import annotations

from dataclasses import dataclass

from .agent_models import AgentDecision, AgentStep
from .agent_runtime import AgentRuntimeRequest, AgentRuntimeStageResult
from .direct_code_agent import DirectCodeApplyResult
from .models import BuildResult
from .neoforge_runtime_workflow_ports import (
    NeoForgeRuntimeAuditPort,
    NeoForgeRuntimeDirectCodePort,
)


@dataclass(slots=True)
class NeoForgeAuditWorkflowDeps:
    audit: NeoForgeRuntimeAuditPort
    direct_code: NeoForgeRuntimeDirectCodePort


class NeoForgeAuditWorkflow:
    """NeoForge audit stage, including Direct Code finalize evidence."""

    def __init__(self, deps: NeoForgeAuditWorkflowDeps) -> None:
        self.deps = deps

    def run(
        self,
        request: AgentRuntimeRequest,
        plan: AgentRuntimeStageResult,
        execution: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        audit_port = self.deps.audit
        direct_code = self.deps.direct_code
        steps: list[AgentStep] = []
        decisions: list[AgentDecision] = []
        if execution.workspace is None:
            payload = {
                "attempted": request.run_audit,
                "success": False,
                "error": "Execution did not produce a workspace.",
            }
            return AgentRuntimeStageResult(success=False, steps=steps, decisions=decisions, payload=payload)

        direct_code_result = execution.state.get("direct_code") if isinstance(execution.state, dict) else None
        payload = audit_port.run_audit_step(
            execution.workspace,
            request.run_audit or isinstance(direct_code_result, DirectCodeApplyResult),
            steps,
            decisions,
        )
        if isinstance(direct_code_result, DirectCodeApplyResult):
            generation = execution.state.get("generation") if isinstance(execution.state, dict) else None
            build_result = (
                generation.build
                if getattr(generation, "build", None) is not None
                else BuildResult(
                    attempted=bool(execution.build_payload.get("attempted")),
                    success=execution.build_payload.get("success"),
                    command=[str(item) for item in execution.build_payload.get("command", [])],
                    return_code=execution.build_payload.get("return_code"),
                    summary=str(execution.build_payload.get("summary", "")),
                )
            )
            direct_code_success = (
                direct_code_result.success
                and build_result.attempted
                and build_result.success is True
                and audit_port.audit_success(payload)
            )
            direct_code.finalize_direct_code_report(
                execution.workspace,
                direct_code_result,
                build=build_result,
                audit_payload=payload,
                success=bool(direct_code_success),
            )
            execution.payload["direct_code"] = direct_code_result.to_dict()
            direct_code.update_generation_summary_direct_code(
                execution.workspace,
                direct_code_result,
                generated_files=list(execution.payload.get("generated_files", [])),
            )

        return AgentRuntimeStageResult(
            success=audit_port.audit_success(payload),
            steps=steps,
            decisions=decisions,
            payload=payload,
            workspace=execution.workspace,
        )

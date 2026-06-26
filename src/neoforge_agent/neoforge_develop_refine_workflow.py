from __future__ import annotations

from dataclasses import dataclass

from .agent_models import AgentDecision, AgentStep
from .agent_options import reviewer_requires_more_rag as _reviewer_requires_more_rag
from .agent_runtime import AgentRuntimeRequest, AgentRuntimeStageResult
from .models import ModSpec
from .neoforge_runtime_workflow_ports import NeoForgeRuntimeRepairPort


@dataclass(slots=True)
class NeoForgeDevelopRefineWorkflowDeps:
    repair: NeoForgeRuntimeRepairPort


class NeoForgeDevelopRefineWorkflow:
    """NeoForge develop-mode repair/refine workflow behind the runtime plugin."""

    def __init__(self, deps: NeoForgeDevelopRefineWorkflowDeps) -> None:
        self.deps = deps

    def run(
        self,
        request: AgentRuntimeRequest,
        execution: AgentRuntimeStageResult,
        audit: AgentRuntimeStageResult,
    ) -> AgentRuntimeStageResult:
        repair_port = self.deps.repair
        steps: list[AgentStep] = []
        decisions: list[AgentDecision] = []
        spec = execution.state.get("spec") if isinstance(execution.state, dict) else None
        intent_contract = execution.state.get("intent_contract") if isinstance(execution.state, dict) else None
        root_causes = repair_port.repair_root_causes(execution.build_payload, audit.payload)
        repair_plan = repair_port.repair_plan_actions(execution.build_payload, audit.payload, root_causes)
        try:
            baseline_reviewer = repair_port.run_reviewer(
                workspace=execution.workspace,
                user_goal=request.request,
                llm_provider=request.llm_provider,
                review_stage="develop_baseline",
                intent_contract=intent_contract if isinstance(intent_contract, dict) else None,
                modspec=spec.to_dict() if isinstance(spec, ModSpec) else None,
                rag={},
                tool_call_trace=[],
                changed_files=list(execution.payload.get("generated_files", [])),
                audit_result=audit.payload,
                build_result=execution.build_payload,
                steps=steps,
                decisions=decisions,
            )
            tool_result = repair_port.run_tool_calling_repair(
                execution.workspace,
                goal=request.request,
                llm_provider=request.llm_provider,
                max_iterations=int(request.options.get("max_iterations", 1) or 1),
                run_build=request.run_build,
                run_audit=request.run_audit,
                initial_build=execution.build_payload,
                initial_audit=audit.payload,
                root_causes=root_causes,
                repair_plan=repair_plan,
                loop_purpose="develop_refine",
                extra_context={
                    "mode": request.mode,
                    "baseline_modspec": spec.to_dict() if isinstance(spec, ModSpec) else None,
                    "intent_contract": intent_contract,
                    "baseline_generation": execution.payload,
                    "baseline_reviewer_observation": baseline_reviewer.to_dict(),
                },
                rag_mode=str(request.options.get("rag_mode", "auto")),
            )
            payload = tool_result.to_dict()
            steps.append(
                AgentStep(
                    role="repair_agent",
                    status="pass" if tool_result.success else "fail",
                    summary=(
                        "Executed LLM tool-calling develop refinement loop."
                        if tool_result.success
                        else "LLM tool-calling develop refinement loop did not pass requested gates."
                    ),
                    details={
                        "action": "tool_calling_develop_refine_loop",
                        "tool_calls_count": tool_result.iterations,
                        "repair_success": tool_result.repair_success,
                        "final_build": tool_result.final_build,
                        "final_audit": tool_result.final_audit,
                    },
                    errors=[]
                    if tool_result.success
                    else repair_port.repair_root_causes(tool_result.final_build, tool_result.final_audit),
                )
            )
            decisions.append(
                AgentDecision(
                    role="repair_agent",
                    decision="execute_tool_calling_develop_refine_loop",
                    rationale="Develop mode generated a deterministic baseline, then used the same constrained LLM tool loop to inspect, patch, and verify the workspace inside the generated-workspace boundary.",
                    status="pass" if tool_result.success else "fail",
                    inputs=["development_goal", "baseline_modspec", "build_observation", "audit_observation"],
                    outputs=[
                        f"tool_calls={tool_result.iterations}",
                        f"repair_executed={tool_result.repair_executed}",
                        f"repair_success={tool_result.repair_success}",
                    ],
                    knowledge_refs=repair_port.repair_knowledge_refs(payload.get("repair_rag") or {}),
                )
            )
            prompt_traces = [baseline_reviewer.prompt_trace, *tool_result.prompt_traces]
            final_reviewer = repair_port.run_reviewer(
                workspace=execution.workspace,
                user_goal=request.request,
                llm_provider=request.llm_provider,
                review_stage="develop_final",
                intent_contract=intent_contract if isinstance(intent_contract, dict) else None,
                modspec=spec.to_dict() if isinstance(spec, ModSpec) else None,
                rag=payload.get("repair_rag") or {},
                tool_call_trace=payload.get("tool_call_trace") or [],
                changed_files=repair_port.changed_files_from_repair_payload(payload),
                audit_result=payload.get("final_audit") or audit.payload,
                build_result=payload.get("final_build") or execution.build_payload,
                steps=steps,
                decisions=decisions,
                prior_reviewer_observation=baseline_reviewer.to_dict(),
            )
            payload["baseline_reviewer"] = baseline_reviewer.to_dict()
            payload["reviewer"] = final_reviewer.to_dict()
            prompt_traces.append(final_reviewer.prompt_trace)
            max_iterations = int(request.options.get("max_iterations", 1) or 1)
            if (
                (final_reviewer.decision == "needs_repair" or _reviewer_requires_more_rag(final_reviewer.to_dict()))
                and tool_result.iterations < max_iterations
            ):
                followup_result = repair_port.run_tool_calling_repair(
                    execution.workspace,
                    goal=request.request,
                    llm_provider=request.llm_provider,
                    max_iterations=max_iterations - tool_result.iterations,
                    run_build=request.run_build,
                    run_audit=request.run_audit,
                    initial_build=payload.get("final_build") or execution.build_payload,
                    initial_audit=payload.get("final_audit") or audit.payload,
                    root_causes=root_causes,
                    repair_plan=repair_plan,
                    loop_purpose="develop_refine",
                    extra_context={
                        "mode": request.mode,
                        "baseline_modspec": spec.to_dict() if isinstance(spec, ModSpec) else None,
                        "intent_contract": intent_contract,
                        "baseline_generation": execution.payload,
                        "reviewer_observation": final_reviewer.to_dict(),
                    },
                    rag_mode="on"
                    if _reviewer_requires_more_rag(final_reviewer.to_dict())
                    else str(request.options.get("rag_mode", "auto")),
                )
                payload["reviewer_requested_repair"] = followup_result.to_dict()
                payload["final_build"] = followup_result.final_build
                payload["final_audit"] = followup_result.final_audit
                payload["success"] = followup_result.success
                payload["repair_success"] = followup_result.repair_success
                combined_tool_trace = [
                    *list(payload.get("tool_call_trace") or []),
                    *list(followup_result.trace),
                ]
                payload["tool_call_trace"] = combined_tool_trace
                payload["tool_calls_count"] = len(combined_tool_trace)
                payload["iterations"] = len(combined_tool_trace)
                payload["repair_executed"] = bool(payload.get("repair_executed")) or followup_result.repair_executed
                if followup_result.structured_patch:
                    payload["structured_patch"] = followup_result.structured_patch
                if followup_result.repair_rag:
                    payload["repair_rag"] = followup_result.repair_rag
                if followup_result.rag_decision_trace:
                    payload["rag_decision_trace"] = [
                        *list(payload.get("rag_decision_trace") or []),
                        *list(followup_result.rag_decision_trace),
                    ]
                prompt_traces.extend(followup_result.prompt_traces)
                final_reviewer = repair_port.run_reviewer(
                    workspace=execution.workspace,
                    user_goal=request.request,
                    llm_provider=request.llm_provider,
                    review_stage="develop_final_after_repair",
                    intent_contract=intent_contract if isinstance(intent_contract, dict) else None,
                    modspec=spec.to_dict() if isinstance(spec, ModSpec) else None,
                    rag=payload.get("repair_rag") or {},
                    tool_call_trace=payload.get("tool_call_trace") or [],
                    changed_files=repair_port.changed_files_from_repair_payload(payload),
                    audit_result=payload.get("final_audit") or audit.payload,
                    build_result=payload.get("final_build") or execution.build_payload,
                    steps=steps,
                    decisions=decisions,
                    prior_reviewer_observation=final_reviewer.to_dict(),
                )
                payload["reviewer"] = final_reviewer.to_dict()
                prompt_traces.append(final_reviewer.prompt_trace)
            return AgentRuntimeStageResult(
                success=bool(payload.get("success")),
                steps=steps,
                decisions=decisions,
                prompt_traces=prompt_traces,
                payload=payload,
                workspace=execution.workspace,
            )
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            payload = {
                "attempted": True,
                "loop_purpose": "develop_refine",
                "repair_needed": bool(root_causes),
                "repair_executed": False,
                "repair_success": False,
                "root_causes": root_causes or [error_text],
                "repair_plan": repair_plan,
                "initial_build": execution.build_payload,
                "initial_audit": audit.payload,
                "final_build": execution.build_payload,
                "final_audit": audit.payload,
                "tool_call_trace": [
                    {
                        "iteration": 1,
                        "role": "repair_agent",
                        "source": "tool_error",
                        "action": "finish",
                        "args": {"status": "failed"},
                        "thought_summary": "Develop refinement tool loop could not start.",
                        "observation": {"success": False, "summary": error_text},
                    }
                ],
                "errors": [error_text],
            }
            steps.append(
                AgentStep(
                    role="repair_agent",
                    status="fail",
                    summary="Tool-calling develop refinement failed before completion.",
                    details=payload,
                    errors=[error_text],
                )
            )
            decisions.append(
                AgentDecision(
                    role="repair_agent",
                    decision="execute_tool_calling_develop_refine_loop",
                    rationale="Develop mode attempted to start the constrained LLM tool loop after baseline generation but encountered a normalized runtime failure.",
                    status="fail",
                    inputs=["development_goal", "baseline_modspec", "build_observation", "audit_observation"],
                    outputs=[error_text],
                )
            )
            return AgentRuntimeStageResult(
                success=False,
                steps=steps,
                decisions=decisions,
                payload=payload,
                workspace=execution.workspace,
            )

from __future__ import annotations

from typing import Any

from .agent_runtime import AgentRuntime
from .neoforge_audit_workflow import NeoForgeAuditWorkflow, NeoForgeAuditWorkflowDeps
from .neoforge_develop_refine_workflow import (
    NeoForgeDevelopRefineWorkflow,
    NeoForgeDevelopRefineWorkflowDeps,
)
from .neoforge_generate_execution_workflow import (
    NeoForgeGenerateExecutionWorkflow,
    NeoForgeGenerateExecutionWorkflowDeps,
)
from .neoforge_modify_workflow import (
    NeoForgeModifyDirectCodePort,
    NeoForgeModifyRepairPort,
    NeoForgeModifyReviewAuditPort,
    NeoForgeModifyTracePort,
    NeoForgeModifyWorkflow,
    NeoForgeModifyWorkflowDeps,
)
from .neoforge_planning_workflow import NeoForgePlanningWorkflow, NeoForgePlanningWorkflowDeps
from .neoforge_repair_workflow import (
    NeoForgeRepairObservationPort,
    NeoForgeRepairReviewPort,
    NeoForgeRepairToolLoopPort,
    NeoForgeRepairTracePort,
    NeoForgeRepairWorkflow,
    NeoForgeRepairWorkflowDeps,
)
from .neoforge_review_workflow import NeoForgeReviewWorkflow, NeoForgeReviewWorkflowDeps
from .neoforge_runtime_plugin import NeoForgeRuntimePlugin
from .neoforge_runtime_finalization_policy import (
    NeoForgeRuntimeFinalizationPolicy,
    NeoForgeRuntimeFinalizationPolicyDeps,
)
from .neoforge_runtime_repair_stage_workflow import (
    NeoForgeRuntimeRepairStageWorkflow,
    NeoForgeRuntimeRepairStageWorkflowDeps,
)
from .neoforge_runtime_plugin_ports import (
    NeoForgeRuntimeAuditWorkflowPort,
    NeoForgeRuntimeFinalizationPort,
    NeoForgeRuntimeGenerateExecutionPort,
    NeoForgeRuntimePlanningWorkflowPort,
    NeoForgeRuntimePluginDeps,
    NeoForgeRuntimeRepairStagePort,
    NeoForgeRuntimeReviewWorkflowPort,
)
from .neoforge_runtime_workflow_ports import (
    NeoForgeRuntimeAuditPort,
    NeoForgeRuntimeDevelopRefinePort,
    NeoForgeRuntimeDirectCodePort,
    NeoForgeRuntimeExecutionPort,
    NeoForgeRuntimePlanningPort,
    NeoForgeRuntimeRepairPort,
    NeoForgeRuntimeReviewPort,
)


def create_neoforge_modify_workflow(orchestrator: Any) -> NeoForgeModifyWorkflow:
    return NeoForgeModifyWorkflow(
        NeoForgeModifyWorkflowDeps(
            config=orchestrator.config,
            trace=NeoForgeModifyTracePort(
                trace_from_artifacts=orchestrator._trace_from_artifacts,
                write_agent_run=orchestrator._write_agent_run,
                planner_trace=orchestrator._planner_trace,
                planner_knowledge_refs=orchestrator._knowledge_refs_from_planner_artifacts,
            ),
            review_audit=NeoForgeModifyReviewAuditPort(
                review_spec=orchestrator._review_spec,
                decision_from_review=orchestrator._decision_from_review,
                execution_errors=orchestrator._execution_errors,
                run_audit_step=orchestrator._run_audit_step,
                audit_success=orchestrator._audit_success,
            ),
            direct_code=NeoForgeModifyDirectCodePort(
                should_use_direct_code=orchestrator._direct_code_requested,
                execute_direct_code_lane=orchestrator._execute_direct_code_lane,
                build_workspace=orchestrator.planner.builder.build,
                finalize_direct_code_report=orchestrator.direct_code_agent.finalize_report,
                update_generation_summary_direct_code=orchestrator._update_generation_summary_direct_code,
            ),
            repair=NeoForgeModifyRepairPort(
                run_analysis_step=orchestrator._run_repair_analysis_step,
            ),
        )
    )


def create_neoforge_repair_workflow(orchestrator: Any) -> NeoForgeRepairWorkflow:
    return NeoForgeRepairWorkflow(
        NeoForgeRepairWorkflowDeps(
            observation=NeoForgeRepairObservationPort(
                build_workspace=lambda workspace, *, repair: orchestrator.planner.builder.build(
                    workspace,
                    repair=repair,
                ),
                run_audit_step=orchestrator._run_audit_step,
                repair_root_causes=orchestrator._repair_root_causes,
                repair_plan_actions=orchestrator._repair_plan_actions,
            ),
            tool_loop=NeoForgeRepairToolLoopPort(
                run_tool_calling_repair=lambda workspace, **kwargs: orchestrator.tool_calling_repair_agent.run(
                    workspace,
                    **kwargs,
                ),
            ),
            review=NeoForgeRepairReviewPort(
                repair_knowledge_refs=orchestrator._knowledge_refs_from_repair_rag,
                run_reviewer=orchestrator._run_llm_reviewer,
                load_modspec_dict=orchestrator._load_modspec_dict,
                changed_files_from_repair_payload=orchestrator._changed_files_from_repair_payload,
            ),
            trace=NeoForgeRepairTracePort(
                write_agent_run=orchestrator._write_agent_run,
            ),
        )
    )


def create_neoforge_runtime(orchestrator: Any) -> AgentRuntime:
    return AgentRuntime(
        NeoForgeRuntimePlugin(create_neoforge_runtime_plugin_deps(orchestrator)),
        orchestrator.trace_writer,
    )


def create_neoforge_runtime_plugin_deps(orchestrator: Any) -> NeoForgeRuntimePluginDeps:
    planning_port = create_neoforge_runtime_planning_port(orchestrator)
    execution_port = create_neoforge_runtime_execution_port(orchestrator)
    audit_port = create_neoforge_runtime_audit_port(orchestrator)
    direct_code_port = create_neoforge_runtime_direct_code_port(orchestrator)
    review_port = create_neoforge_runtime_review_port(orchestrator)
    planning_workflow = NeoForgePlanningWorkflow(
        NeoForgePlanningWorkflowDeps(
            domain_name=NeoForgeRuntimePlugin.domain_name,
            domain_spec_metadata=NeoForgeRuntimePlugin.domain_spec_plugin.metadata.to_dict(),
            planning=planning_port,
            direct_code=direct_code_port,
        )
    )
    generate_execution_workflow = NeoForgeGenerateExecutionWorkflow(
        NeoForgeGenerateExecutionWorkflowDeps(
            config=orchestrator.config,
            domain_name="neoforge",
            execution=execution_port,
            direct_code=direct_code_port,
        )
    )
    audit_workflow = NeoForgeAuditWorkflow(
        NeoForgeAuditWorkflowDeps(
            audit=audit_port,
            direct_code=direct_code_port,
        )
    )
    review_workflow = NeoForgeReviewWorkflow(
        NeoForgeReviewWorkflowDeps(review=review_port)
    )
    repair_port = create_neoforge_runtime_repair_port(orchestrator)
    develop_refine_workflow = NeoForgeDevelopRefineWorkflow(
        NeoForgeDevelopRefineWorkflowDeps(repair=repair_port)
    )
    develop_refine_port = NeoForgeRuntimeDevelopRefinePort(run=develop_refine_workflow.run)
    repair_stage_workflow = NeoForgeRuntimeRepairStageWorkflow(
        NeoForgeRuntimeRepairStageWorkflowDeps(
            repair=repair_port,
            develop_refine=develop_refine_port,
        )
    )
    finalization_policy = NeoForgeRuntimeFinalizationPolicy(
        NeoForgeRuntimeFinalizationPolicyDeps(
            domain_name=NeoForgeRuntimePlugin.domain_name,
            domain_spec_metadata=NeoForgeRuntimePlugin.domain_spec_plugin.metadata.to_dict(),
            audit=audit_port,
        )
    )
    return NeoForgeRuntimePluginDeps(
        planning_workflow=NeoForgeRuntimePlanningWorkflowPort(run=planning_workflow.run),
        review_workflow=NeoForgeRuntimeReviewWorkflowPort(run=review_workflow.run),
        generate_execution=NeoForgeRuntimeGenerateExecutionPort(run=generate_execution_workflow.run),
        audit_workflow=NeoForgeRuntimeAuditWorkflowPort(run=audit_workflow.run),
        repair_stage=NeoForgeRuntimeRepairStagePort(run=repair_stage_workflow.run),
        finalization=NeoForgeRuntimeFinalizationPort(
            final_success=finalization_policy.final_success,
            final_payload=finalization_policy.final_payload,
            review_failure_payload=finalization_policy.review_failure_payload,
        ),
    )


def create_neoforge_runtime_review_port(orchestrator: Any) -> NeoForgeRuntimeReviewPort:
    return NeoForgeRuntimeReviewPort(
        review_spec=orchestrator._review_spec,
        decision_from_review=orchestrator._decision_from_review,
    )


def create_neoforge_runtime_planning_port(orchestrator: Any) -> NeoForgeRuntimePlanningPort:
    return NeoForgeRuntimePlanningPort(
        plan_generate=orchestrator._plan_generate,
        trace_from_artifacts=orchestrator._trace_from_artifacts,
        intent_contract=orchestrator._intent_contract,
        planner_knowledge_refs=orchestrator._knowledge_refs_from_planner_artifacts,
        planner_trace=orchestrator._planner_trace,
    )


def create_neoforge_runtime_execution_port(orchestrator: Any) -> NeoForgeRuntimeExecutionPort:
    return NeoForgeRuntimeExecutionPort(
        execute_spec=lambda spec, **kwargs: orchestrator.planner.execute_spec(spec, **kwargs),
        execution_errors=orchestrator._execution_errors,
    )


def create_neoforge_runtime_audit_port(orchestrator: Any) -> NeoForgeRuntimeAuditPort:
    return NeoForgeRuntimeAuditPort(
        run_audit_step=orchestrator._run_audit_step,
        audit_success=orchestrator._audit_success,
    )


def create_neoforge_runtime_direct_code_port(orchestrator: Any) -> NeoForgeRuntimeDirectCodePort:
    return NeoForgeRuntimeDirectCodePort(
        should_use_direct_code=orchestrator._direct_code_requested,
        execute_direct_code_lane=orchestrator._execute_direct_code_lane,
        build_workspace=lambda workspace, *, repair: orchestrator.planner.builder.build(
            workspace,
            repair=repair,
        ),
        finalize_direct_code_report=orchestrator.direct_code_agent.finalize_report,
        update_generation_summary_direct_code=orchestrator._update_generation_summary_direct_code,
    )


def create_neoforge_runtime_repair_port(orchestrator: Any) -> NeoForgeRuntimeRepairPort:
    return NeoForgeRuntimeRepairPort(
        repair_root_causes=orchestrator._repair_root_causes,
        repair_plan_actions=orchestrator._repair_plan_actions,
        run_reviewer=orchestrator._run_llm_reviewer,
        run_tool_calling_repair=lambda workspace, **kwargs: orchestrator.tool_calling_repair_agent.run(
            workspace,
            **kwargs,
        ),
        repair_knowledge_refs=orchestrator._knowledge_refs_from_repair_rag,
        changed_files_from_repair_payload=orchestrator._changed_files_from_repair_payload,
        run_analysis_step=orchestrator._run_repair_analysis_step,
    )

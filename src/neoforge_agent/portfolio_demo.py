from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .capabilities import CapabilityCatalog
from .config import AppConfig
from .dashboard import WebDashboardRunner
from .doctor import EnvironmentDoctor
from .evidence_chain_report import EvidenceChainReportRunner
from .llm_eval_report import RealLLMEvalReportRunner
from .showcase import ShowcaseRunner
from .tools import ensure_directory, write_json, write_text
from .web_demo import WebDemoRunner


@dataclass(slots=True)
class PortfolioDemoStep:
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
class PortfolioDemoResult:
    success: bool
    run_id: str
    portfolio_dir: Path
    steps: list[PortfolioDemoStep]
    portfolio_report_json_path: Path
    portfolio_report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        passed = sum(1 for step in self.steps if step.status == "pass")
        failed = sum(1 for step in self.steps if step.status == "fail")
        skipped = sum(1 for step in self.steps if step.status == "skip")
        return {
            "success": self.success,
            "run_id": self.run_id,
            "portfolio_dir": str(self.portfolio_dir),
            "steps": [step.to_dict() for step in self.steps],
            "passed_count": passed,
            "failed_count": failed,
            "skipped_count": skipped,
            "steps_count": len(self.steps),
            "portfolio_report_json_path": str(self.portfolio_report_json_path),
            "portfolio_report_md_path": str(self.portfolio_report_md_path),
        }


class PortfolioDemoRunner:
    """Run a one-command, offline-friendly portfolio demo flow."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        planner_mode: str = "llm",
        llm_provider: str = "mock",
        candidate_provider: str = "mock",
        eval_limit: int = 2,
        run_build: bool = False,
        run_quality_gate: bool = False,
    ) -> PortfolioDemoResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        portfolio_dir = ensure_directory(self.config.workspace_root / "portfolio-runs" / run_id)
        agent_dir = ensure_directory(portfolio_dir / ".agent")
        scoped_config = replace(self.config, workspace_root=ensure_directory(portfolio_dir / "runs"))

        steps = [
            self._run_doctor(run_id, scoped_config),
            self._run_showcase(
                run_id,
                scoped_config,
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                eval_limit=eval_limit,
                run_build=run_build,
                run_quality_gate=run_quality_gate,
            ),
            self._run_dashboard(
                run_id,
                scoped_config,
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                eval_limit=eval_limit,
            ),
            self._run_llm_eval_report(
                run_id,
                scoped_config,
                candidate_provider=candidate_provider,
                eval_limit=eval_limit,
                run_build=run_build,
            ),
            self._run_evidence_chain_report(run_id, scoped_config, eval_limit=eval_limit),
            self._run_web_demo_smoke(scoped_config, planner_mode=planner_mode, llm_provider=llm_provider),
            self._run_capabilities(run_id, scoped_config),
        ]

        success = all(step.status in {"pass", "skip"} for step in steps)
        result = PortfolioDemoResult(
            success=success,
            run_id=run_id,
            portfolio_dir=portfolio_dir,
            steps=steps,
            portfolio_report_json_path=agent_dir / "portfolio-demo-report.json",
            portfolio_report_md_path=agent_dir / "portfolio-demo-report.md",
        )
        write_json(result.portfolio_report_json_path, result.to_dict())
        write_text(result.portfolio_report_md_path, self._render_markdown(result))
        return result

    def _run_doctor(self, run_id: str, config: AppConfig) -> PortfolioDemoStep:
        try:
            result = EnvironmentDoctor(config).run(run_name=f"{run_id}-doctor", check_java=False)
            payload = result.to_dict()
            return PortfolioDemoStep(
                name="doctor",
                status="pass" if result.success else "fail",
                summary="完成本地环境预检，确认 Python、模板、workspace、文档与 CI 基础条件。",
                artifacts={
                    "doctor_report_json": str(result.doctor_report_json_path),
                    "doctor_report_md": str(result.doctor_report_md_path),
                },
                metrics={
                    "passed": payload["passed_count"],
                    "warnings": payload["warnings_count"],
                    "failed": payload["failed_count"],
                    "skipped": payload["skipped_count"],
                },
                warnings=[check.message for check in result.checks if check.status == "warning"],
                errors=[check.message for check in result.checks if check.status == "fail"],
            )
        except Exception as exc:
            return _failed_step("doctor", "环境预检执行失败。", exc)

    def _run_showcase(
        self,
        run_id: str,
        config: AppConfig,
        *,
        planner_mode: str,
        llm_provider: str,
        eval_limit: int,
        run_build: bool,
        run_quality_gate: bool,
    ) -> PortfolioDemoStep:
        try:
            result = ShowcaseRunner(config).run(
                run_name=f"{run_id}-showcase",
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                run_build=run_build,
                run_quality_gate=run_quality_gate,
                eval_limit=eval_limit,
            )
            payload = result.to_dict()
            return PortfolioDemoStep(
                name="showcase",
                status="pass" if result.success else "fail",
                summary="跑通展示主线：doctor、多角色 agent generate、modify、eval smoke 与可选 quality gate。",
                artifacts={
                    "showcase_dir": str(result.showcase_dir),
                    "showcase_report_json": str(result.showcase_report_json_path),
                    "showcase_report_md": str(result.showcase_report_md_path),
                },
                metrics={
                    "passed": payload["passed_count"],
                    "failed": payload["failed_count"],
                    "skipped": payload["skipped_count"],
                    "steps": payload["steps_count"],
                },
                warnings=[warning for step in result.steps for warning in step.warnings],
                errors=[error for step in result.steps for error in step.errors],
            )
        except Exception as exc:
            return _failed_step("showcase", "作品集 showcase 流程执行失败。", exc)

    def _run_dashboard(
        self,
        run_id: str,
        config: AppConfig,
        *,
        planner_mode: str,
        llm_provider: str,
        eval_limit: int,
    ) -> PortfolioDemoStep:
        try:
            result = WebDashboardRunner(config).run(
                run_name=f"{run_id}-dashboard",
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                eval_limit=eval_limit,
                run_showcase=True,
                run_quality_gate=False,
            )
            data = result.to_dict()
            return PortfolioDemoStep(
                name="dashboard",
                status="pass" if result.success else "fail",
                summary="生成静态 Web Dashboard，用一个 HTML 页面展示能力矩阵、RAG 命中、agent trace、repair 与内容覆盖率。",
                artifacts={
                    "dashboard_dir": str(result.dashboard_dir),
                    "dashboard_index": str(result.index_path),
                    "dashboard_data": str(result.dashboard_data_path),
                    "dashboard_report_md": str(result.dashboard_report_md_path),
                },
                metrics={
                    "steps": data["steps_count"],
                },
                warnings=list(result.warnings),
                errors=[step["summary"] for step in result.steps if step.get("status") == "fail"],
            )
        except Exception as exc:
            return _failed_step("dashboard", "静态 dashboard 生成失败。", exc)

    def _run_llm_eval_report(
        self,
        run_id: str,
        config: AppConfig,
        *,
        candidate_provider: str,
        eval_limit: int,
        run_build: bool,
    ) -> PortfolioDemoStep:
        try:
            result = RealLLMEvalReportRunner(config).run(
                run_name=f"{run_id}-llm-eval",
                limit=eval_limit,
                baseline_provider="mock",
                candidate_provider=candidate_provider,
                run_build=run_build,
                run_audit=True,
                require_real=False,
            )
            return PortfolioDemoStep(
                name="llm_eval_report",
                status="pass" if result.success else "fail",
                summary="生成 mock baseline 与候选 LLM provider 的规划质量对比报告，默认完全离线可跑。",
                artifacts={
                    "llm_eval_report_json": str(result.llm_eval_report_json_path),
                    "llm_eval_report_md": str(result.llm_eval_report_md_path),
                    "baseline_eval": str(result.baseline_eval_report_path or ""),
                    "candidate_eval": str(result.candidate_eval_report_path or ""),
                    "eval_compare": str(result.eval_compare_report_path or ""),
                },
                metrics={
                    "baseline_status": result.baseline_status,
                    "candidate_status": result.candidate_status,
                    "comparison_status": result.comparison_status,
                    **result.metrics_summary,
                },
                warnings=list(result.warnings),
                errors=list(result.errors),
            )
        except Exception as exc:
            return _failed_step("llm_eval_report", "LLM 评测对比报告生成失败。", exc)

    def _run_web_demo_smoke(
        self,
        config: AppConfig,
        *,
        planner_mode: str,
        llm_provider: str,
    ) -> PortfolioDemoStep:
        try:
            planner_selection = _web_demo_planner_selection(planner_mode, llm_provider)
            payload = WebDemoRunner(config).smoke(planner_selection=planner_selection)
            return PortfolioDemoStep(
                name="web_demo_smoke",
                status="pass" if payload.get("success") else "fail",
                summary="执行 Web Demo 后端 smoke：生成、加载 workspace、modify、日志区域、知识库与 repair 视图基础检查。",
                artifacts={
                    "workspace": str(payload.get("workspace") or ""),
                },
                metrics={
                    "planner_selection": planner_selection,
                    "features": payload.get("modspec_feature_count"),
                    "generated_files": payload.get("generated_files_count"),
                    "workspaces": payload.get("workspaces_count"),
                    "agent_roles": payload.get("agent_roles_count"),
                    "knowledge_entries": payload.get("knowledge_entries_count"),
                    "audit_success": payload.get("audit_success"),
                    "modify_added": len(payload.get("modify_added", [])),
                    "modify_updated": len(payload.get("modify_updated", [])),
                    "modify_skipped": len(payload.get("modify_skipped", [])),
                },
                errors=[] if payload.get("success") else [str(payload.get("error") or "Web Demo smoke failed.")],
            )
        except Exception as exc:
            return _failed_step("web_demo_smoke", "Web Demo smoke 执行失败。", exc)

    def _run_evidence_chain_report(self, run_id: str, config: AppConfig, *, eval_limit: int) -> PortfolioDemoStep:
        try:
            result = EvidenceChainReportRunner(config).run(
                run_name=f"{run_id}-evidence-chain",
                eval_limit=eval_limit,
                repair_limit=1,
            )
            return PortfolioDemoStep(
                name="evidence_chain_report",
                status="pass" if result.success else "fail",
                summary="汇总稳定 ModSpec、Behavior DSL 与受控 patch-agent 三层证据链，记录成功率、失败样例、恢复率、生成文件数和 runtime 验证。",
                artifacts={
                    "evidence_chain_json": str(result.evidence_chain_report_json_path),
                    "evidence_chain_md": str(result.evidence_chain_report_md_path),
                },
                metrics=dict(result.metrics),
            )
        except Exception as exc:
            return _failed_step("evidence_chain_report", "三层证据链报告生成失败。", exc)

    def _run_capabilities(self, run_id: str, config: AppConfig) -> PortfolioDemoStep:
        try:
            result = CapabilityCatalog(config).build(run_name=f"{run_id}-capabilities")
            return PortfolioDemoStep(
                name="capabilities",
                status="pass" if result.success else "fail",
                summary="导出能力矩阵，作为 README、Dashboard 和当前能力快照。",
                artifacts={
                    "capabilities_json": str(result.capability_report_json_path),
                    "capabilities_md": str(result.capability_report_md_path),
                },
                metrics={
                    "version": result.version,
                    "sections": len(result.sections),
                    "capabilities": sum(len(section.capabilities) for section in result.sections),
                },
            )
        except Exception as exc:
            return _failed_step("capabilities", "能力矩阵导出失败。", exc)

    def _render_markdown(self, result: PortfolioDemoResult) -> str:
        payload = result.to_dict()
        lines = [
            "# V4.0 作品集级一键演示报告",
            "",
            f"成功: `{str(result.success).lower()}`",
            f"运行 ID: `{result.run_id}`",
            f"演示目录: `{result.portfolio_dir}`",
            f"步骤: `{payload['passed_count']} passed / {payload['failed_count']} failed / {payload['skipped_count']} skipped`",
            "",
            "## 一句话项目介绍",
            "",
            "这是一个面向 NeoForge 的 Mod Agent：用户输入自然语言后，系统通过 rules 或 LLM planner 生成 ModSpec，再由确定性生成器产出 Java、JSON 和 PNG 资源，并用 audit、build、repair、eval 与 dashboard 做可靠性闭环。",
            "",
            "## 一键演示链路",
            "",
            "- `doctor`: 检查本地环境与项目资源。",
            "- `showcase`: 演示多角色 agent 的 generate、modify、audit、eval 主流程。",
            "- `dashboard`: 生成静态 Web Dashboard，展示能力矩阵、RAG、agent trace、repair 与覆盖率。",
            "- `llm_eval_report`: 对比 mock baseline 与候选 LLM provider 的规划质量。",
            "- `evidence_chain_report`: 汇总 Stable ModSpec、Behavior DSL、controlled patch-agent 三层可量化证据。",
            "- `web_demo_smoke`: 验证交互式 Web Demo 的生成、修改、workspace 管理和可视化入口。",
            "- `capabilities`: 输出当前能力矩阵，便于复述。",
            "",
            "## 讲解重点",
            "",
            "- LLM 不直接写 Java、JSON 或 PNG，只输出受 schema 约束的 ModSpec 或修复计划。",
            "- 生成器是 deterministic 的，因此同一个 ModSpec 可以稳定复现项目结构。",
            "- audit/build/repair/eval/dashboard 形成闭环，不只是能生成，还能验收、诊断、展示和对比。",
            "- mock LLM 让演示默认离线可跑，真实 OpenAI-compatible provider 可以作为可选增强接入。",
            "",
            "## 关键产物",
            "",
            f"- 组合报告 JSON: `{result.portfolio_report_json_path}`",
            f"- 组合报告 Markdown: `{result.portfolio_report_md_path}`",
            "",
            "## 步骤详情",
            "",
        ]
        for step in result.steps:
            lines.append(f"### {step.name} `{step.status}`")
            lines.append("")
            lines.append(step.summary)
            lines.append("")
            if step.artifacts:
                lines.append("产物:")
                for key, value in step.artifacts.items():
                    if value:
                        lines.append(f"- `{key}`: `{value}`")
                lines.append("")
            if step.metrics:
                lines.append("指标:")
                for key, value in step.metrics.items():
                    lines.append(f"- `{key}`: {value}")
                lines.append("")
            if step.warnings:
                lines.append("警告:")
                lines.extend(f"- {warning}" for warning in step.warnings)
                lines.append("")
            if step.errors:
                lines.append("错误:")
                lines.extend(f"- {error}" for error in step.errors)
                lines.append("")
        lines.extend(
            [
                "## 下一步如何展示",
                "",
                "1. 打开上面 `dashboard_index` 对应的 `index.html`，作为静态演示页。",
                "2. 如果需要交互演示，运行 `py -3.11 -m agent.cli web-demo --planner mock-llm`。",
                "3. 先讲 ModSpec 边界，再展示 dashboard 的 trace、audit、repair 和 eval 报告。",
                "",
            ]
        )
        return "\n".join(lines)


def _failed_step(name: str, summary: str, exc: Exception) -> PortfolioDemoStep:
    return PortfolioDemoStep(
        name=name,
        status="fail",
        summary=summary,
        errors=[f"{type(exc).__name__}: {exc}"],
    )


def _web_demo_planner_selection(planner_mode: str, llm_provider: str) -> str:
    planner = planner_mode.strip().lower()
    provider = llm_provider.strip().lower()
    if planner == "rules":
        return "rules"
    if planner == "auto":
        return "auto-real" if provider == "openai-compatible" else "auto-mock"
    return "real-llm" if provider == "openai-compatible" else "mock-llm"

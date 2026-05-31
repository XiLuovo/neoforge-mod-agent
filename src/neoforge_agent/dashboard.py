from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field, replace
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from .capabilities import CapabilityCatalog
from .config import AppConfig
from .evaluator import default_eval_cases
from .knowledge_base import KnowledgeQueryRunner
from .showcase import ShowcaseRunner
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class DashboardResult:
    success: bool
    run_id: str
    dashboard_dir: Path
    index_path: Path
    dashboard_data_path: Path
    dashboard_report_md_path: Path
    steps: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "run_id": self.run_id,
            "dashboard_dir": str(self.dashboard_dir),
            "index_path": str(self.index_path),
            "dashboard_index_path": str(self.index_path),
            "dashboard_data_path": str(self.dashboard_data_path),
            "dashboard_report_md_path": str(self.dashboard_report_md_path),
            "steps": list(self.steps),
            "warnings": list(self.warnings),
            "steps_count": len(self.steps),
        }


class WebDashboardRunner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        planner_mode: str = "llm",
        llm_provider: str = "mock",
        eval_limit: int = 2,
        run_showcase: bool = True,
        run_quality_gate: bool = False,
    ) -> DashboardResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        dashboard_dir = ensure_directory(self.config.workspace_root / "dashboard-runs" / run_id)
        agent_dir = ensure_directory(dashboard_dir / ".agent")
        scoped_config = replace(self.config, workspace_root=ensure_directory(dashboard_dir / "runs"))

        steps: list[dict[str, Any]] = []
        warnings: list[str] = []

        capabilities = CapabilityCatalog(scoped_config).build(run_name=f"{run_id}-capabilities")
        steps.append(
            {
                "name": "capabilities",
                "status": "pass" if capabilities.success else "fail",
                "summary": "Exported capability matrix for dashboard rendering.",
                "artifact": str(capabilities.capability_report_json_path),
            }
        )

        knowledge_queries = [
            ("worldgen", "ruby ore worldgen overworld configured_feature placed_feature biome modifier"),
            ("textures", "programmatic textures texture manifest 16x16 rgba audit"),
            ("behavior", "right click heal item behavior custom item class cooldown"),
        ]
        knowledge_results = []
        for label, query in knowledge_queries:
            result = KnowledgeQueryRunner(scoped_config).query(
                query,
                limit=4,
                run_name=f"{run_id}-knowledge-{label}",
            )
            knowledge_results.append(result)
            steps.append(
                {
                    "name": f"knowledge_{label}",
                    "status": "pass" if result.success else "fail",
                    "summary": f"Retrieved {len(result.hits)} knowledge snippet(s) for {label}.",
                    "artifact": str(result.report_json_path),
                }
            )

        showcase = None
        if run_showcase:
            showcase = ShowcaseRunner(scoped_config).run(
                run_name=f"{run_id}-showcase",
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                run_build=False,
                run_quality_gate=run_quality_gate,
                eval_limit=eval_limit,
            )
            steps.append(
                {
                    "name": "showcase",
                    "status": "pass" if showcase.success else "fail",
                    "summary": "Ran showcase flow for the dashboard.",
                    "artifact": str(showcase.showcase_report_json_path),
                }
            )
        else:
            steps.append(
                {
                    "name": "showcase",
                    "status": "skip",
                    "summary": "Showcase flow skipped by --no-showcase.",
                    "artifact": "",
                }
            )

        data = self._dashboard_data(
            run_id=run_id,
            dashboard_dir=dashboard_dir,
            capabilities=capabilities.to_dict(),
            knowledge=[result.to_dict() for result in knowledge_results],
            showcase=showcase.to_dict() if showcase else None,
            steps=steps,
            warnings=warnings,
        )
        data_path = agent_dir / "dashboard-data.json"
        index_path = dashboard_dir / "index.html"
        report_md_path = agent_dir / "dashboard-report.md"
        write_json(data_path, data)
        write_text(index_path, self._render_html(data, dashboard_dir))
        write_text(report_md_path, self._render_markdown(data))

        success = all(step["status"] in {"pass", "skip"} for step in steps)
        result = DashboardResult(
            success=success,
            run_id=run_id,
            dashboard_dir=dashboard_dir,
            index_path=index_path,
            dashboard_data_path=data_path,
            dashboard_report_md_path=report_md_path,
            steps=steps,
            warnings=warnings,
        )
        write_json(data_path, {**data, "result": result.to_dict()})
        return result

    def _dashboard_data(
        self,
        *,
        run_id: str,
        dashboard_dir: Path,
        capabilities: dict[str, Any],
        knowledge: list[dict[str, Any]],
        showcase: dict[str, Any] | None,
        steps: list[dict[str, Any]],
        warnings: list[str],
    ) -> dict[str, Any]:
        capability_count = int(capabilities.get("capabilities_count", 0))
        sections_count = int(capabilities.get("sections_count", 0))
        knowledge_hits = sum(int(item.get("hits_count", 0)) for item in knowledge)
        showcase_steps = int(showcase.get("steps_count", 0)) if showcase else 0
        showcase_failed = int(showcase.get("failed_count", 0)) if showcase else 0
        content_coverage = self._content_coverage(capabilities)
        agent_traces = self._agent_traces(showcase)
        agent_roles = sum(len(item.get("roles", [])) for item in agent_traces)
        agent_decisions = sum(int(item.get("decisions_count", 0)) for item in agent_traces)
        prompt_traces = sum(int(item.get("prompt_traces_count", 0)) for item in agent_traces)
        rag_summary = self._rag_summary(knowledge, agent_traces)
        repair_summary = self._repair_summary(agent_traces)
        rag_reference_chains = self._rag_reference_chains(agent_traces)
        resource_preview = self._resource_preview(agent_traces, dashboard_dir)
        return {
            "schema_version": 1,
            "title": "NeoForge Mod Agent Web Demo Dashboard",
            "version": self._project_version(),
            "run_id": run_id,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "dashboard_dir": str(dashboard_dir),
            "project": {
                "loader": self.config.loader,
                "neo_version": self.config.neo_version,
                "java_version": self.config.java_version,
                "template": self.config.template_name,
            },
            "metrics": {
                "capabilities": capability_count,
                "capability_sections": sections_count,
                "knowledge_hits": knowledge_hits,
                "showcase_steps": showcase_steps,
                "showcase_failed": showcase_failed,
                "pipeline_steps": len(steps),
                "content_capabilities_total": content_coverage["total"],
                "content_capabilities_covered": content_coverage["covered"],
                "content_coverage_rate": content_coverage["rate"],
                "agent_runs": len(agent_traces),
                "agent_roles": agent_roles,
                "agent_decisions": agent_decisions,
                "prompt_traces": prompt_traces,
                "rag_categories": len(rag_summary["categories"]),
                "rag_capabilities": len(rag_summary["capabilities"]),
                "repair_runs": repair_summary["runs"],
                "repair_needed": repair_summary["needed"],
                "repair_executed": repair_summary["executed"],
                "repair_success": repair_summary["success"],
                "repair_attempts": repair_summary["attempts"],
                "repair_rag_runs": repair_summary["rag_runs"],
                "repair_rag_hits": repair_summary["rag_hits"],
                "rag_reference_chains": len(rag_reference_chains),
                "decision_knowledge_refs": sum(len(item.get("knowledge_refs", []) or []) for item in rag_reference_chains),
                "resource_preview_runs": resource_preview["runs_count"],
                "resource_textures": resource_preview["textures"],
                "resource_model_variants": resource_preview["model_variants"],
                "resource_structure_previews": resource_preview["structure_previews"],
            },
            "content_coverage": content_coverage,
            "agent_traces": agent_traces,
            "rag_summary": rag_summary,
            "rag_reference_chains": rag_reference_chains,
            "repair_summary": repair_summary,
            "resource_preview": resource_preview,
            "steps": steps,
            "capabilities": capabilities,
            "knowledge": knowledge,
            "showcase": showcase,
            "warnings": warnings,
        }

    def _project_version(self) -> str:
        pyproject_path = self.config.project_root / "pyproject.toml"
        if not pyproject_path.exists():
            return "unknown"
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        return str(data.get("project", {}).get("version", "unknown"))

    def _render_html(self, data: dict[str, Any], dashboard_dir: Path) -> str:
        metrics = data["metrics"]
        steps = data["steps"]
        sections = data["capabilities"].get("sections", [])
        knowledge = data.get("knowledge", [])
        showcase = data.get("showcase") or {}
        showcase_steps = showcase.get("steps", [])
        content_coverage = data.get("content_coverage", {})
        raw_json = escape(json.dumps(data, ensure_ascii=False, indent=2))

        step_cards = "\n".join(self._step_card(step) for step in steps)
        capability_cards = "\n".join(self._capability_section(section) for section in sections)
        coverage_cards = self._content_coverage_cards(content_coverage)
        agent_trace_cards = self._agent_trace_cards(data.get("agent_traces", []))
        repair_cards = self._repair_summary_cards(data.get("repair_summary", {}), data.get("agent_traces", []))
        knowledge_chain_cards = self._knowledge_reference_chain_cards(data.get("rag_reference_chains", []))
        resource_preview_cards = self._resource_preview_cards(data.get("resource_preview", {}), dashboard_dir)
        knowledge_cards = self._rag_summary_cards(data.get("rag_summary", {})) + "\n" + "\n".join(self._knowledge_card(item) for item in knowledge)
        showcase_cards = "\n".join(self._showcase_step_card(step) for step in showcase_steps) or '<p class="muted">Showcase flow was skipped.</p>'
        artifact_links = self._artifact_links(data, dashboard_dir)

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(data['title'])}</title>
  <style>
    :root {{
      --paper: #f4efe1;
      --ink: #17211d;
      --muted: #65736f;
      --line: rgba(23, 33, 29, 0.16);
      --teal: #14796f;
      --teal-dark: #0e4f49;
      --ember: #d86c32;
      --gold: #d8a934;
      --clay: #b85b42;
      --card: rgba(255, 252, 242, 0.78);
      --shadow: 0 22px 70px rgba(36, 46, 40, 0.16);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Trebuchet MS", "Gill Sans", Verdana, sans-serif;
      background:
        radial-gradient(circle at 12% 10%, rgba(216,169,52,0.35), transparent 28rem),
        radial-gradient(circle at 88% 4%, rgba(20,121,111,0.22), transparent 26rem),
        linear-gradient(145deg, #f8f1df 0%, #e7dbc2 52%, #d9d0bd 100%);
      min-height: 100vh;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(23,33,29,0.045) 1px, transparent 1px),
        linear-gradient(90deg, rgba(23,33,29,0.04) 1px, transparent 1px);
      background-size: 42px 42px;
      mask-image: linear-gradient(to bottom, rgba(0,0,0,0.6), transparent 70%);
    }}
    header, main {{ position: relative; z-index: 1; }}
    header {{
      padding: 56px min(7vw, 88px) 28px;
    }}
    .eyebrow {{
      display: inline-flex;
      gap: 10px;
      align-items: center;
      padding: 8px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,0.45);
      color: var(--teal-dark);
      font-weight: 700;
      letter-spacing: .08em;
      text-transform: uppercase;
      font-size: 12px;
    }}
    h1 {{
      max-width: 980px;
      margin: 22px 0 12px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(42px, 7vw, 92px);
      line-height: .92;
      letter-spacing: -0.06em;
    }}
    .hero-copy {{
      max-width: 780px;
      color: var(--muted);
      font-size: 18px;
      line-height: 1.65;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 14px;
      margin-top: 30px;
    }}
    .metric {{
      grid-column: span 1;
      min-height: 128px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 28px;
      background: var(--card);
      box-shadow: var(--shadow);
      backdrop-filter: blur(8px);
    }}
    .metric strong {{
      display: block;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 42px;
      line-height: 1;
      letter-spacing: -0.04em;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      margin-top: 10px;
      font-size: 13px;
      line-height: 1.4;
    }}
    main {{
      display: grid;
      gap: 22px;
      padding: 0 min(7vw, 88px) 72px;
    }}
    section {{
      border: 1px solid var(--line);
      border-radius: 34px;
      background: rgba(255,252,242,0.68);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 20px;
      padding: 26px 28px 12px;
      border-bottom: 1px solid var(--line);
    }}
    h2 {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(25px, 3vw, 42px);
      letter-spacing: -0.04em;
    }}
    .section-note {{
      max-width: 460px;
      margin: 4px 0 0;
      color: var(--muted);
      line-height: 1.55;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      padding: 20px;
    }}
    .card {{
      padding: 18px;
      border-radius: 24px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.46);
    }}
    .card h3 {{
      margin: 0 0 8px;
      font-size: 18px;
      letter-spacing: -0.02em;
    }}
    .card p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
      font-size: 14px;
    }}
    .pill {{
      display: inline-flex;
      padding: 5px 9px;
      margin-bottom: 12px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .06em;
    }}
    .pass {{ color: #0f5f39; background: rgba(42, 151, 93, .15); }}
    .fail {{ color: #8d2f25; background: rgba(216, 82, 62, .16); }}
    .skip {{ color: #725318; background: rgba(216, 169, 52, .2); }}
    .capability-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
    }}
    .tag {{
      border: 1px solid var(--line);
      background: rgba(20, 121, 111, .08);
      color: var(--teal-dark);
      padding: 6px 9px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
    }}
    .artifact-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      padding: 20px;
    }}
    a {{
      color: var(--teal-dark);
      font-weight: 800;
      text-decoration-color: rgba(20,121,111,0.35);
      text-underline-offset: 4px;
    }}
    .artifact {{
      padding: 15px;
      border-radius: 18px;
      background: rgba(20, 121, 111, .08);
      border: 1px solid rgba(20, 121, 111, .16);
      overflow-wrap: anywhere;
    }}
    .resource-preview {{
      width: 100%;
      image-rendering: pixelated;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(23,33,29,0.08);
      margin: 10px 0 12px;
    }}
    details {{
      margin: 20px;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(23,33,29,0.05);
      overflow: hidden;
    }}
    summary {{
      cursor: pointer;
      padding: 16px 18px;
      font-weight: 800;
    }}
    pre {{
      margin: 0;
      padding: 18px;
      max-height: 420px;
      overflow: auto;
      background: #17211d;
      color: #f4efe1;
      font-size: 12px;
      line-height: 1.5;
    }}
    .muted {{ color: var(--muted); }}
    @media (max-width: 1060px) {{
      .hero-grid, .cards, .artifact-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .metric {{ grid-column: span 1; }}
    }}
    @media (max-width: 700px) {{
      header {{ padding: 34px 18px 20px; }}
      main {{ padding: 0 18px 44px; }}
      .hero-grid, .cards, .artifact-grid {{ grid-template-columns: 1fr; }}
      .section-head {{ display: block; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="eyebrow">V2.5 Web Demo Dashboard · offline static report</div>
    <h1>NeoForge Mod Agent, shown like a product.</h1>
    <p class="hero-copy">A local dashboard for demo day: generation, multi-role agent traces, audit, RAG retrieval, procedural textures, benchmark smoke, and capability coverage in one self-contained HTML page.</p>
    <div class="hero-grid">
      <div class="metric"><strong>{metrics['capabilities']}</strong><span>capabilities exported</span></div>
      <div class="metric"><strong>{metrics['capability_sections']}</strong><span>capability sections</span></div>
      <div class="metric"><strong>{metrics['knowledge_hits']}</strong><span>RAG snippets retrieved</span></div>
      <div class="metric"><strong>{metrics['showcase_steps']}</strong><span>showcase steps</span></div>
      <div class="metric"><strong>{metrics['showcase_failed']}</strong><span>showcase failures</span></div>
      <div class="metric"><strong>{metrics['content_capabilities_covered']}/{metrics['content_capabilities_total']}</strong><span>content capabilities covered</span></div>
      <div class="metric"><strong>{metrics['agent_roles']}</strong><span>agent role traces</span></div>
      <div class="metric"><strong>{metrics['repair_executed']}/{metrics['repair_runs']}</strong><span>self-healing repair loops executed</span></div>
      <div class="metric"><strong>{metrics['repair_rag_hits']}</strong><span>repair RAG knowledge hits</span></div>
      <div class="metric"><strong>{metrics['resource_textures']}</strong><span>profiled texture previews</span></div>
    </div>
  </header>
  <main>
    <section>
      <div class="section-head"><div><h2>Pipeline Status</h2><p class="section-note">Each card is generated from real local commands or deterministic report builders.</p></div></div>
      <div class="cards">{step_cards}</div>
    </section>
    <section>
      <div class="section-head"><div><h2>Showcase Run</h2><p class="section-note">Doctor, agent generate, agent modify, eval smoke, and optional quality gate.</p></div></div>
      <div class="cards">{showcase_cards}</div>
    </section>
    <section>
      <div class="section-head"><div><h2>Multi-Agent Trace</h2><p class="section-note">Planner, reviewer, executor, auditor, and repair roles with recorded inputs, outputs, decisions, and prompt traces.</p></div></div>
      <div class="cards">{agent_trace_cards}</div>
    </section>
    <section>
      <div class="section-head"><div><h2>RAG Citation Chain</h2><p class="section-note">Decision-level evidence links: which planner or repair decision used which bundled knowledge ids.</p></div></div>
      <div class="cards">{knowledge_chain_cards}</div>
    </section>
    <section>
      <div class="section-head"><div><h2>Self-Healing Repair</h2><p class="section-note">Repair Agent summary: root causes, safe repair-loop attempts, RAG advice, success state, and repair artifacts.</p></div></div>
      <div class="cards">{repair_cards}</div>
    </section>
    <section>
      <div class="section-head"><div><h2>Resource Preview</h2><p class="section-note">V8 resource quality reports: texture profile atlas, model variant coverage, and schematic structure previews from generated workspaces.</p></div></div>
      <div class="cards">{resource_preview_cards}</div>
    </section>
    <section>
      <div class="section-head"><div><h2>Content Coverage</h2><p class="section-note">Default eval and golden checks cover the content features this Agent claims to generate.</p></div></div>
      <div class="cards">{coverage_cards}</div>
    </section>
    <section>
      <div class="section-head"><div><h2>Capability Matrix</h2><p class="section-note">Machine-readable project abilities rendered for inspection.</p></div></div>
      <div class="cards">{capability_cards}</div>
    </section>
    <section>
      <div class="section-head"><div><h2>RAG Knowledge</h2><p class="section-note">Bundled NeoForge knowledge retrieval that constrains LLM planning without allowing free-form Java.</p></div></div>
      <div class="cards">{knowledge_cards}</div>
    </section>
    <section>
      <div class="section-head"><div><h2>Artifacts</h2><p class="section-note">Open the raw reports behind this dashboard.</p></div></div>
      <div class="artifact-grid">{artifact_links}</div>
      <details><summary>Embedded dashboard-data.json</summary><pre>{raw_json}</pre></details>
    </section>
  </main>
</body>
</html>
"""

    def _step_card(self, step: dict[str, Any]) -> str:
        status = str(step.get("status", "skip"))
        return (
            f'<article class="card"><span class="pill {escape(status)}">{escape(status)}</span>'
            f"<h3>{escape(str(step.get('name', 'step')).replace('_', ' ').title())}</h3>"
            f"<p>{escape(str(step.get('summary', '')))}</p></article>"
        )

    def _showcase_step_card(self, step: dict[str, Any]) -> str:
        status = str(step.get("status", "skip"))
        metrics = step.get("metrics") or {}
        metric_text = ", ".join(f"{key}={value}" for key, value in metrics.items())
        return (
            f'<article class="card"><span class="pill {escape(status)}">{escape(status)}</span>'
            f"<h3>{escape(str(step.get('name', 'step')).replace('_', ' ').title())}</h3>"
            f"<p>{escape(str(step.get('summary', '')))}</p>"
            f'<p class="muted">{escape(metric_text)}</p></article>'
        )

    def _agent_trace_cards(self, traces: list[dict[str, Any]]) -> str:
        if not traces:
            return '<article class="card"><span class="pill skip">skip</span><h3>No Agent Trace</h3><p>Run dashboard with showcase enabled to render multi-agent trace cards.</p></article>'
        cards: list[str] = []
        for trace in traces:
            status = "pass" if trace.get("success") else "fail"
            roles = trace.get("roles", [])
            role_tags = "".join(f'<span class="tag">{escape(str(role.get("role", "")))}</span>' for role in roles)
            repair = trace.get("repair") or {}
            repair_text = (
                f"repair_needed={repair.get('repair_needed')}, "
                f"repair_executed={repair.get('repair_executed')}, "
                f"repair_success={repair.get('repair_success')}, "
                f"repair_rag_hits={repair.get('repair_rag_hits_count', 0)}"
            )
            cards.append(
                '<article class="card">'
                f'<span class="pill {escape(status)}">{escape(status)}</span>'
                f"<h3>{escape(str(trace.get('name', 'agent run')).replace('_', ' ').title())}</h3>"
                f"<p>{escape(str(trace.get('request', '')))}</p>"
                f'<p class="muted">decisions={escape(str(trace.get("decisions_count", 0)))}, prompt_traces={escape(str(trace.get("prompt_traces_count", 0)))}</p>'
                f'<p class="muted">{escape(repair_text)}</p>'
                f'<div class="capability-list">{role_tags}</div>'
                "</article>"
            )
            for role in roles:
                role_status = str(role.get("status", "skip"))
                inputs = ", ".join(str(item) for item in role.get("inputs", [])[:3]) or "none"
                outputs = ", ".join(str(item) for item in role.get("outputs", [])[:3]) or "none"
                rationale = ""
                decisions = role.get("decisions") or []
                if decisions:
                    rationale = str(decisions[0].get("rationale", ""))
                knowledge_ids = sorted(
                    {
                        str(item)
                        for decision in decisions
                        for item in decision.get("knowledge_ids", [])
                        if item
                    }
                )
                knowledge_text = ", ".join(knowledge_ids[:5]) or "none"
                cards.append(
                    '<article class="card">'
                    f'<span class="pill {escape(role_status)}">{escape(role_status)}</span>'
                    f"<h3>{escape(str(role.get('role', 'agent')))}</h3>"
                    f"<p>{escape(str(role.get('summary', '')))}</p>"
                    f'<p class="muted">inputs: {escape(inputs)}</p>'
                    f'<p class="muted">outputs: {escape(outputs)}</p>'
                    f'<p class="muted">knowledge ids: {escape(knowledge_text)}</p>'
                    f'<p class="muted">why: {escape(rationale)}</p>'
                    "</article>"
                )
        return "\n".join(cards)

    def _repair_summary_cards(self, summary: dict[str, Any], traces: list[dict[str, Any]]) -> str:
        if not traces:
            return '<article class="card"><span class="pill skip">skip</span><h3>No Repair Trace</h3><p>Run dashboard with showcase enabled to render repair-agent summaries.</p></article>'
        status = "pass" if int(summary.get("failures", 0)) == 0 else "fail"
        rag_capability_tags = "".join(
            f'<span class="tag">{escape(str(key))}={escape(str(value))}</span>'
            for key, value in (summary.get("rag_capabilities") or {}).items()
        ) or '<span class="tag">none</span>'
        cards = [
            '<article class="card">'
            f'<span class="pill {escape(status)}">self-healing</span>'
            "<h3>Repair Agent Summary</h3>"
            f"<p>{escape(str(summary.get('runs', 0)))} agent run(s), {escape(str(summary.get('needed', 0)))} needing repair, {escape(str(summary.get('executed', 0)))} safe loop(s) executed.</p>"
            "</article>",
            '<article class="card">'
            "<h3>Repair Loop Attempts</h3>"
            f"<p>attempts={escape(str(summary.get('attempts', 0)))}, success={escape(str(summary.get('success', 0)))}, failures={escape(str(summary.get('failures', 0)))}</p>"
            "</article>",
            '<article class="card">'
            "<h3>Repair RAG Advice</h3>"
            f"<p>runs={escape(str(summary.get('rag_runs', 0)))}, hits={escape(str(summary.get('rag_hits', 0)))}</p>"
            f'<div class="capability-list">{rag_capability_tags}</div>'
            "</article>",
        ]
        for trace in traces:
            repair = trace.get("repair") or {}
            root_causes = repair.get("root_causes") or []
            actions = repair.get("repair_plan") or []
            repair_rag = repair.get("repair_rag") or {}
            rag_query = str(repair.get("repair_rag_query") or repair_rag.get("query") or "")
            tags = "".join(f'<span class="tag">{escape(str(action.get("id", "action")))}</span>' for action in actions[:6])
            rag_tags = "".join(
                f'<span class="tag">rag:{escape(str(hit.get("id", "")))}</span>'
                for hit in (repair_rag.get("hits") or [])[:4]
            )
            if not tags:
                tags = '<span class="tag">no repair action needed</span>'
            cards.append(
                '<article class="card">'
                f'<span class="pill {"pass" if repair.get("repair_success") or repair.get("repair_needed") is False else "skip"}">repair</span>'
                f"<h3>{escape(str(trace.get('name', 'agent run')).replace('_', ' ').title())}</h3>"
                f"<p>needed={escape(str(repair.get('repair_needed')))}, executed={escape(str(repair.get('repair_executed')))}, success={escape(str(repair.get('repair_success')))}, attempts={escape(str(repair.get('attempts_count', 0)))}, rag_hits={escape(str(repair.get('repair_rag_hits_count', 0)))}</p>"
                f"<p class=\"muted\">root causes: {escape('; '.join(str(item) for item in root_causes) or 'none')}</p>"
                f"<p class=\"muted\">RAG query: {escape(rag_query[:220] or 'none')}</p>"
                f'<div class="capability-list">{tags}{rag_tags}</div>'
                "</article>"
            )
            for link in repair.get("repair_rag_links", [])[:4]:
                knowledge_tags = "".join(f'<span class="tag">{escape(str(item))}</span>' for item in link.get("knowledge_ids", [])[:5])
                if not knowledge_tags:
                    knowledge_tags = '<span class="tag">no RAG hit</span>'
                cards.append(
                    '<article class="card">'
                    '<span class="pill pass">why</span>'
                    f"<h3>{escape(str(link.get('action_id') or 'repair evidence'))}</h3>"
                    f"<p>{escape(str(link.get('root_cause') or 'No root cause recorded.'))}</p>"
                    f"<p class=\"muted\">action: {escape(str(link.get('action_summary') or 'No repair action recorded.'))}</p>"
                    f"<p class=\"muted\">query: {escape(str(link.get('query') or '')[:180])}</p>"
                    f'<div class="capability-list">{knowledge_tags}</div>'
                    "</article>"
                )
        return "\n".join(cards)

    def _capability_section(self, section: dict[str, Any]) -> str:
        capabilities = section.get("capabilities", [])
        tags = "".join(f'<span class="tag">{escape(str(item.get("id", "")))}</span>' for item in capabilities[:8])
        if len(capabilities) > 8:
            tags += f'<span class="tag">+{len(capabilities) - 8} more</span>'
        return (
            '<article class="card">'
            f"<h3>{escape(str(section.get('title', 'Section')))}</h3>"
            f"<p>{escape(str(section.get('summary', '')))}</p>"
            f'<div class="capability-list">{tags}</div>'
            "</article>"
        )

    def _content_coverage_cards(self, coverage: dict[str, Any]) -> str:
        covered = coverage.get("covered_capabilities", [])
        missing = coverage.get("missing_capabilities", [])
        rate = coverage.get("rate", 0)
        covered_tags = "".join(f'<span class="tag">{escape(str(item))}</span>' for item in covered)
        missing_tags = "".join(f'<span class="tag">{escape(str(item))}</span>' for item in missing) or '<span class="tag">none</span>'
        return "\n".join(
            [
                '<article class="card">',
                '<span class="pill pass">coverage</span>',
                f"<h3>{int(round(float(rate) * 100))}% covered</h3>",
                f"<p>{coverage.get('covered', 0)} of {coverage.get('total', 0)} generated-content capabilities are covered by default eval/golden expectations.</p>",
                "</article>",
                '<article class="card">',
                "<h3>Covered Content</h3>",
                '<div class="capability-list">' + covered_tags + "</div>",
                "</article>",
                '<article class="card">',
                "<h3>Missing Content</h3>",
                '<div class="capability-list">' + missing_tags + "</div>",
                "</article>",
            ]
        )

    def _resource_preview_cards(self, preview: dict[str, Any], dashboard_dir: Path) -> str:
        runs = preview.get("runs") if isinstance(preview, dict) else []
        if not runs:
            return '<article class="card"><span class="pill skip">skip</span><h3>No Resource Preview</h3><p>Run dashboard with showcase enabled to render V8 texture atlas and resource quality cards.</p></article>'
        profile_tags = "".join(
            f'<span class="tag">{escape(str(key))}={escape(str(value))}</span>'
            for key, value in (preview.get("texture_profiles") or {}).items()
        ) or '<span class="tag">none</span>'
        cards = [
            '<article class="card">'
            '<span class="pill pass">v8</span>'
            "<h3>Resource Quality Summary</h3>"
            f"<p>{escape(str(preview.get('textures', 0)))} texture(s), {escape(str(preview.get('model_variants', 0)))} model variant file(s), {escape(str(preview.get('structure_previews', 0)))} structure preview(s).</p>"
            f'<div class="capability-list">{profile_tags}</div>'
            "</article>"
        ]
        for run in runs[:4]:
            atlas_path = str(run.get("atlas_path", ""))
            atlas_href = self._relative_href(Path(atlas_path), dashboard_dir) if atlas_path else ""
            cards.append(
                '<article class="card">'
                '<span class="pill pass">atlas</span>'
                f"<h3>{escape(str(run.get('run', 'resource run')).replace('_', ' ').title())}</h3>"
                + (f'<img class="resource-preview" src="{escape(atlas_href)}" alt="Texture atlas for {escape(str(run.get("run", "resource run")))}">' if atlas_href else "")
                + f"<p>{escape(str((run.get('summary') or {}).get('textures', 0)))} profiled texture(s), {escape(str((run.get('summary') or {}).get('model_variants', 0)))} model variant file(s).</p>"
                + f'<p class="muted"><a href="{escape(self._relative_href(Path(str(run.get("report_path", ""))), dashboard_dir))}">resource-quality-report.json</a></p>'
                "</article>"
            )
            for structure in (run.get("structure_previews") or [])[:2]:
                structure_path = str(structure.get("path_abs", ""))
                structure_href = self._relative_href(Path(structure_path), dashboard_dir) if structure_path else ""
                cards.append(
                    '<article class="card">'
                    '<span class="pill pass">structure</span>'
                    f"<h3>{escape(str(structure.get('id', 'structure')).replace('_', ' ').title())}</h3>"
                    + (f'<img class="resource-preview" src="{escape(structure_href)}" alt="Structure preview for {escape(str(structure.get("id", "structure")))}">' if structure_href else "")
                    + f"<p>{escape(str(structure.get('projection', 'top_down_schematic')))} preview for `{escape(str(structure.get('structure_kind', 'structure')))}`.</p>"
                    "</article>"
                )
        return "\n".join(cards)

    def _knowledge_card(self, item: dict[str, Any]) -> str:
        query = escape(str(item.get("query", "")))
        hits = item.get("hits", [])
        hit_items = "".join(f'<span class="tag">{escape(str(hit.get("id", "")))}</span>' for hit in hits[:5])
        category_items = "".join(f'<span class="tag">{escape(str(key))}={escape(str(value))}</span>' for key, value in (item.get("categories") or {}).items())
        return (
            '<article class="card">'
            f"<h3>{query}</h3>"
            f"<p>{escape(str(item.get('hits_count', 0)))} snippet(s) retrieved.</p>"
            f'<div class="capability-list">{hit_items}</div>'
            f'<div class="capability-list">{category_items}</div>'
            "</article>"
        )

    def _rag_summary_cards(self, summary: dict[str, Any]) -> str:
        categories = summary.get("categories", {})
        capabilities = summary.get("capabilities", {})
        category_tags = "".join(f'<span class="tag">{escape(str(key))}={escape(str(value))}</span>' for key, value in categories.items()) or '<span class="tag">none</span>'
        capability_tags = "".join(f'<span class="tag">{escape(str(key))}={escape(str(value))}</span>' for key, value in capabilities.items()) or '<span class="tag">none</span>'
        return "\n".join(
            [
                '<article class="card">',
                '<span class="pill pass">rag</span>',
                "<h3>RAG Hit Summary</h3>",
                f"<p>{summary.get('hits_count', 0)} retrieved knowledge hit(s) across dashboard queries and agent planner traces.</p>",
                "</article>",
                '<article class="card">',
                "<h3>RAG Categories</h3>",
                '<div class="capability-list">' + category_tags + "</div>",
                "</article>",
                '<article class="card">',
                "<h3>RAG Capabilities</h3>",
                '<div class="capability-list">' + capability_tags + "</div>",
                "</article>",
            ]
        )

    def _knowledge_reference_chain_cards(self, chains: list[dict[str, Any]]) -> str:
        if not chains:
            return '<article class="card"><span class="pill skip">skip</span><h3>No RAG Citation Chain</h3><p>No planner or repair decision recorded knowledge references in this dashboard run.</p></article>'
        cards: list[str] = []
        for chain in chains[:12]:
            status = str(chain.get("status", "recorded"))
            pill_status = status if status in {"pass", "fail", "skip"} else "pass"
            knowledge_refs = chain.get("knowledge_refs") or []
            knowledge_tags = "".join(
                f'<span class="tag">{escape(str(item.get("id", "")))}</span>'
                for item in knowledge_refs[:6]
                if isinstance(item, dict) and item.get("id")
            ) or '<span class="tag">no knowledge id</span>'
            capability_tags = "".join(
                f'<span class="tag">{escape(str(item.get("capability", "")))}</span>'
                for item in knowledge_refs[:4]
                if isinstance(item, dict) and item.get("capability")
            )
            cards.append(
                '<article class="card">'
                f'<span class="pill {escape(pill_status)}">{escape(str(chain.get("role", "agent")))}</span>'
                f"<h3>{escape(str(chain.get('decision', 'decision')))}</h3>"
                f"<p>{escape(str(chain.get('rationale', '')))}</p>"
                f'<p class="muted">run: {escape(str(chain.get("run", "")))}</p>'
                f'<p class="muted">knowledge refs: {escape(str(len(knowledge_refs)))}</p>'
                f'<div class="capability-list">{knowledge_tags}{capability_tags}</div>'
                "</article>"
            )
        return "\n".join(cards)

    def _artifact_links(self, data: dict[str, Any], dashboard_dir: Path) -> str:
        links: list[tuple[str, str]] = [
            ("Dashboard data", str(dashboard_dir / ".agent" / "dashboard-data.json")),
            ("Dashboard report", str(dashboard_dir / ".agent" / "dashboard-report.md")),
            ("Capabilities JSON", data["capabilities"].get("capability_report_json_path", "")),
            ("Capabilities Markdown", data["capabilities"].get("capability_report_md_path", "")),
        ]
        showcase = data.get("showcase") or {}
        if showcase:
            links.append(("Showcase JSON", showcase.get("showcase_report_json_path", "")))
            links.append(("Showcase Markdown", showcase.get("showcase_report_md_path", "")))
        for index, item in enumerate(data.get("knowledge", []), start=1):
            links.append((f"RAG query {index}", item.get("report_json_path", "")))
        for index, item in enumerate(data.get("agent_traces", []), start=1):
            links.append((f"Agent run {index}", item.get("agent_run_json_path", "")))
            links.append((f"Agent trace summary {index}", item.get("agent_trace_summary_json_path", "")))
            links.append((f"Prompt trace {index}", item.get("prompt_trace_json_path", "")))
            repair = item.get("repair") or {}
            links.append((f"Agent repair plan {index}", repair.get("agent_repair_plan_json_path", "")))
            links.append((f"Repair loop report {index}", repair.get("repair_loop_report_json_path", "")))
            links.append((f"Repair RAG context {index}", repair.get("repair_rag_report_json_path", "")))
        for index, item in enumerate((data.get("resource_preview") or {}).get("runs", []), start=1):
            links.append((f"Resource quality report {index}", item.get("report_path", "")))
            links.append((f"Texture atlas {index}", item.get("atlas_path", "")))
        rendered = []
        for label, target in links:
            if not target:
                continue
            href = self._relative_href(Path(target), dashboard_dir)
            rendered.append(f'<div class="artifact"><a href="{escape(href)}">{escape(label)}</a><br><span class="muted">{escape(target)}</span></div>')
        return "\n".join(rendered)

    def _relative_href(self, path: Path, dashboard_dir: Path) -> str:
        try:
            return path.resolve().relative_to(dashboard_dir.resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    def _render_markdown(self, data: dict[str, Any]) -> str:
        metrics = data["metrics"]
        lines = [
            "# Web Demo Dashboard",
            "",
            f"Run ID: `{data['run_id']}`",
            f"Version: `{data['version']}`",
            f"Generated at: `{data['generated_at']}`",
            "",
            "## Metrics",
            "",
        ]
        for key, value in metrics.items():
            lines.append(f"- `{key}`: {value}")
        lines.extend(["", "## Steps", ""])
        for step in data["steps"]:
            lines.append(f"- `{step['name']}` `{step['status']}`: {step['summary']}")
        coverage = data.get("content_coverage", {})
        if coverage:
            lines.extend(
                [
                    "",
                    "## Content Coverage",
                    "",
                    f"- covered: `{coverage.get('covered', 0)}/{coverage.get('total', 0)}`",
                    f"- rate: `{coverage.get('rate', 0)}`",
                    f"- capabilities: `{', '.join(coverage.get('covered_capabilities', []))}`",
                ]
            )
        traces = data.get("agent_traces", [])
        if traces:
            lines.extend(["", "## Multi-Agent Trace", ""])
            for trace in traces:
                lines.append(f"- `{trace.get('name')}`: roles `{len(trace.get('roles', []))}`, decisions `{trace.get('decisions_count', 0)}`, prompt traces `{trace.get('prompt_traces_count', 0)}`")
        resource_preview = data.get("resource_preview", {})
        if resource_preview:
            lines.extend(
                [
                    "",
                    "## Resource Preview",
                    "",
                    f"- runs: `{resource_preview.get('runs_count', 0)}`",
                    f"- textures: `{resource_preview.get('textures', 0)}`",
                    f"- model variants: `{resource_preview.get('model_variants', 0)}`",
                    f"- structure previews: `{resource_preview.get('structure_previews', 0)}`",
                ]
            )
        repair_summary = data.get("repair_summary", {})
        if repair_summary:
            lines.extend(
                [
                    "",
                    "## Self-Healing Repair",
                    "",
                    f"- runs: `{repair_summary.get('runs', 0)}`",
                    f"- needed: `{repair_summary.get('needed', 0)}`",
                    f"- executed: `{repair_summary.get('executed', 0)}`",
                    f"- success: `{repair_summary.get('success', 0)}`",
                    f"- attempts: `{repair_summary.get('attempts', 0)}`",
                    f"- repair RAG runs: `{repair_summary.get('rag_runs', 0)}`",
                    f"- repair RAG hits: `{repair_summary.get('rag_hits', 0)}`",
                ]
            )
        rag_summary = data.get("rag_summary", {})
        if rag_summary:
            lines.extend(
                [
                    "",
                    "## RAG Hit Summary",
                    "",
                    f"- hits: `{rag_summary.get('hits_count', 0)}`",
                    f"- categories: `{rag_summary.get('categories', {})}`",
                    f"- capabilities: `{rag_summary.get('capabilities', {})}`",
                ]
            )
        chains = data.get("rag_reference_chains", [])
        if chains:
            lines.extend(["", "## RAG Citation Chain", ""])
            for chain in chains:
                lines.append(
                    f"- `{chain.get('role')}` `{chain.get('decision')}` -> "
                    f"`{', '.join(chain.get('knowledge_ids', []))}`"
                )
        lines.extend(["", "## Artifacts", "", f"- index: `{data['dashboard_dir']}/index.html`", ""])
        return "\n".join(lines)

    def _agent_traces(self, showcase: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not showcase:
            return []
        traces: list[dict[str, Any]] = []
        for step in showcase.get("steps", []):
            artifacts = step.get("artifacts") or {}
            agent_run_path = artifacts.get("agent_run_json")
            if not agent_run_path:
                continue
            run_path = Path(str(agent_run_path))
            if not run_path.exists():
                continue
            try:
                run_payload = json.loads(run_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            used_knowledge = [
                item
                for trace in run_payload.get("prompt_traces", [])
                for item in trace.get("used_knowledge", [])
                if isinstance(item, dict)
            ]
            decisions = [decision for decision in run_payload.get("decisions", []) if isinstance(decision, dict)]
            decision_knowledge_refs = [
                item
                for decision in decisions
                for item in decision.get("knowledge_refs", [])
                if isinstance(item, dict)
            ]

            summary_path = run_payload.get("agent_trace_summary_json_path") or artifacts.get("agent_trace_summary_json")
            summary_payload: dict[str, Any] = {}
            if summary_path and Path(str(summary_path)).exists():
                try:
                    summary_payload = json.loads(Path(str(summary_path)).read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    summary_payload = {}
            roles = summary_payload.get("roles") or self._roles_from_agent_run(run_payload)
            repair = self._repair_from_agent_run(run_payload)
            traces.append(
                {
                    "name": step.get("name", run_payload.get("mode", "agent_run")),
                    "success": run_payload.get("success", False),
                    "mode": run_payload.get("mode", ""),
                    "request": run_payload.get("request", ""),
                    "workspace": run_payload.get("workspace", ""),
                    "roles": roles,
                    "repair": repair,
                    "used_knowledge": used_knowledge,
                    "decision_knowledge_refs": decision_knowledge_refs,
                    "knowledge_reference_chains": _decision_knowledge_chains(step.get("name", run_payload.get("mode", "agent_run")), decisions),
                    "rag_categories": _count_values(item.get("category", "") for item in used_knowledge),
                    "rag_capabilities": _count_values(item.get("capability", item.get("category", "")) for item in used_knowledge),
                    "decisions_count": len(decisions),
                    "prompt_traces_count": len(run_payload.get("prompt_traces", [])),
                    "agent_run_json_path": str(run_path),
                    "agent_decisions_md_path": run_payload.get("agent_decisions_md_path", ""),
                    "agent_trace_summary_json_path": summary_path or "",
                    "prompt_trace_json_path": run_payload.get("prompt_trace_json_path", ""),
                }
            )
        return traces

    def _resource_preview(self, traces: list[dict[str, Any]], dashboard_dir: Path) -> dict[str, Any]:
        runs: list[dict[str, Any]] = []
        total_textures = 0
        total_model_variants = 0
        total_structure_previews = 0
        profile_counts: dict[str, int] = {}
        for trace in traces:
            workspace_value = trace.get("workspace")
            if not workspace_value:
                continue
            workspace = Path(str(workspace_value))
            report_path = workspace / ".agent" / "resource-quality-report.json"
            if not report_path.exists():
                continue
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
            total_textures += int(summary.get("textures", 0) or 0)
            total_model_variants += int(summary.get("model_variants", 0) or 0)
            total_structure_previews += int(summary.get("structure_previews", 0) or 0)
            for key, value in (summary.get("texture_profiles") or {}).items():
                profile_counts[str(key)] = profile_counts.get(str(key), 0) + int(value or 0)
            atlas = (report.get("preview_artifacts") or {}).get("texture_atlas") if isinstance(report.get("preview_artifacts"), dict) else {}
            atlas_path = str(workspace / str((atlas or {}).get("path", ""))) if isinstance(atlas, dict) and atlas.get("path") else ""
            structure_previews = []
            for preview in report.get("structure_previews", []) if isinstance(report.get("structure_previews"), list) else []:
                if not isinstance(preview, dict):
                    continue
                path_value = preview.get("path")
                structure_previews.append(
                    {
                        **preview,
                        "path_abs": str(workspace / str(path_value)) if path_value else "",
                    }
                )
            runs.append(
                {
                    "run": trace.get("name", "agent run"),
                    "workspace": str(workspace),
                    "report_path": str(report_path),
                    "report_md_path": str(workspace / ".agent" / "resource-quality-report.md"),
                    "atlas_path": atlas_path,
                    "summary": summary,
                    "structure_previews": structure_previews,
                }
            )
        return {
            "available": bool(runs),
            "runs_count": len(runs),
            "textures": total_textures,
            "model_variants": total_model_variants,
            "structure_previews": total_structure_previews,
            "texture_profiles": dict(sorted(profile_counts.items())),
            "runs": runs,
            "dashboard_dir": str(dashboard_dir),
        }

    def _repair_from_agent_run(self, run_payload: dict[str, Any]) -> dict[str, Any]:
        payload = run_payload.get("payload", {}) if isinstance(run_payload, dict) else {}
        repair = payload.get("repair", {}) if isinstance(payload, dict) else {}
        if not isinstance(repair, dict):
            repair = {}
        loop = repair.get("repair_loop") if isinstance(repair.get("repair_loop"), dict) else {}
        repair_rag = repair.get("repair_rag") if isinstance(repair.get("repair_rag"), dict) else {}
        root_causes = repair.get("root_causes") if isinstance(repair.get("root_causes"), list) else []
        repair_plan = repair.get("repair_plan") if isinstance(repair.get("repair_plan"), list) else []
        attempts = loop.get("attempts") if isinstance(loop.get("attempts"), list) else []
        workspace = Path(str(run_payload.get("workspace") or "")) if run_payload.get("workspace") else None
        agent_dir = workspace / ".agent" if workspace else None
        return {
            "available": bool(repair),
            "repair_needed": repair.get("repair_needed"),
            "repair_executed": repair.get("repair_executed"),
            "repair_success": repair.get("repair_success"),
            "root_causes": root_causes,
            "root_causes_count": len(root_causes),
            "repair_plan": repair_plan,
            "repair_actions_count": len(repair_plan),
            "repair_rag": repair_rag,
            "repair_rag_hits_count": int(repair_rag.get("hits_count", 0) or 0),
            "repair_rag_categories": repair_rag.get("categories", {}),
            "repair_rag_capabilities": repair_rag.get("capabilities", {}),
            "repair_rag_query": repair_rag.get("query", ""),
            "repair_rag_links": _repair_rag_links(root_causes, repair_plan, repair_rag),
            "repair_rag_report_json_path": repair_rag.get("report_json_path", ""),
            "repair_rag_report_md_path": repair_rag.get("report_md_path", ""),
            "attempts": attempts,
            "attempts_count": int(loop.get("attempts_count", len(attempts)) or 0),
            "repaired": loop.get("repaired"),
            "agent_repair_plan_json_path": str(agent_dir / "agent-repair-plan.json") if agent_dir else "",
            "agent_repair_plan_md_path": str(agent_dir / "agent-repair-plan.md") if agent_dir else "",
            "repair_loop_report_json_path": repair.get("repair_loop_report_json_path") or loop.get("repair_loop_report_json_path") or (str(agent_dir / "repair-loop-report.json") if agent_dir else ""),
            "repair_loop_report_md_path": repair.get("repair_loop_report_md_path") or loop.get("repair_loop_report_md_path") or (str(agent_dir / "repair-loop-report.md") if agent_dir else ""),
        }

    def _repair_summary(self, traces: list[dict[str, Any]]) -> dict[str, Any]:
        repairs = [trace.get("repair") or {} for trace in traces if trace.get("repair")]
        needed = sum(1 for item in repairs if item.get("repair_needed") is True)
        executed = sum(1 for item in repairs if item.get("repair_executed") is True)
        success = sum(1 for item in repairs if item.get("repair_success") is True)
        failures = sum(1 for item in repairs if item.get("repair_success") is False)
        attempts = sum(int(item.get("attempts_count", 0) or 0) for item in repairs)
        rag_runs = sum(1 for item in repairs if (item.get("repair_rag") or {}).get("attempted") is True)
        rag_hits = sum(int(item.get("repair_rag_hits_count", 0) or 0) for item in repairs)
        rag_categories: dict[str, int] = {}
        rag_capabilities: dict[str, int] = {}
        for item in repairs:
            _merge_counts(rag_categories, item.get("repair_rag_categories") or {})
            _merge_counts(rag_capabilities, item.get("repair_rag_capabilities") or {})
        return {
            "runs": len(repairs),
            "needed": needed,
            "executed": executed,
            "success": success,
            "failures": failures,
            "attempts": attempts,
            "rag_runs": rag_runs,
            "rag_hits": rag_hits,
            "rag_categories": dict(sorted(rag_categories.items())),
            "rag_capabilities": dict(sorted(rag_capabilities.items())),
        }

    def _roles_from_agent_run(self, run_payload: dict[str, Any]) -> list[dict[str, Any]]:
        decisions_by_role: dict[str, list[dict[str, Any]]] = {}
        for decision in run_payload.get("decisions", []):
            decisions_by_role.setdefault(str(decision.get("role", "")), []).append(decision)
        roles = []
        for step in run_payload.get("steps", []):
            role = str(step.get("role", ""))
            decisions = decisions_by_role.get(role, [])
            knowledge_refs = [
                item
                for decision in decisions
                for item in decision.get("knowledge_refs", [])
                if isinstance(item, dict)
            ]
            knowledge_ids = sorted({str(item.get("id", "")) for item in knowledge_refs if item.get("id")})
            roles.append(
                {
                    "role": role,
                    "status": step.get("status", ""),
                    "summary": step.get("summary", ""),
                    "inputs": sorted({item for decision in decisions for item in decision.get("inputs", [])}),
                    "outputs": sorted({item for decision in decisions for item in decision.get("outputs", [])}),
                    "decisions": decisions,
                    "knowledge_ids": knowledge_ids,
                    "knowledge_refs": knowledge_refs,
                    "knowledge_refs_count": len(knowledge_refs),
                    "prompt_traces_count": sum(1 for trace in run_payload.get("prompt_traces", []) if trace.get("role") == role),
                }
            )
        return roles

    def _rag_reference_chains(self, traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
        chains: list[dict[str, Any]] = []
        for trace in traces:
            for chain in trace.get("knowledge_reference_chains", []) or []:
                if isinstance(chain, dict):
                    chains.append(chain)
        return chains

    def _rag_summary(self, knowledge: list[dict[str, Any]], agent_traces: list[dict[str, Any]]) -> dict[str, Any]:
        categories: dict[str, int] = {}
        capabilities: dict[str, int] = {}
        hits_count = 0
        for result in knowledge:
            hits = result.get("hits", [])
            hits_count += len(hits)
            _merge_counts(categories, result.get("categories") or _count_values(hit.get("category", "") for hit in hits if isinstance(hit, dict)))
            _merge_counts(capabilities, result.get("capabilities") or _count_values(hit.get("capability", hit.get("category", "")) for hit in hits if isinstance(hit, dict)))
        for trace in agent_traces:
            used = trace.get("used_knowledge", [])
            hits_count += len(used)
            _merge_counts(categories, trace.get("rag_categories") or {})
            _merge_counts(capabilities, trace.get("rag_capabilities") or {})
        return {
            "hits_count": hits_count,
            "categories": dict(sorted(categories.items())),
            "capabilities": dict(sorted(capabilities.items())),
        }

    def _content_coverage(self, capabilities: dict[str, Any]) -> dict[str, Any]:
        content_capabilities = self._content_capability_ids(capabilities)
        covered = self._covered_content_capabilities()
        covered_content = sorted(content_capabilities & covered)
        missing = sorted(content_capabilities - covered)
        return {
            "total": len(content_capabilities),
            "covered": len(covered_content),
            "rate": round(len(covered_content) / len(content_capabilities), 4) if content_capabilities else 0.0,
            "covered_capabilities": covered_content,
            "missing_capabilities": missing,
        }

    def _content_capability_ids(self, capabilities: dict[str, Any]) -> set[str]:
        for section in capabilities.get("sections", []):
            if section.get("id") == "content":
                return {str(item.get("id")) for item in section.get("capabilities", []) if item.get("id")}
        return set()

    def _covered_content_capabilities(self) -> set[str]:
        covered: set[str] = {"loot_tag_lang_model", "procedural_textures", "resource_quality_profiles", "texture_atlas_preview", "model_variant_report", "pack_mcmeta"}
        for case in default_eval_cases():
            categories = set(case.expected_categories)
            features = set(case.expected_features)
            covered.update(category for category in categories if category in {"item", "block", "ore", "food", "sword", "tool", "armor", "recipe", "block_variants", "interactive_blocks"})
            if {"ruby_pickaxe", "ruby_axe", "ruby_shovel", "ruby_hoe"} & features or {"ruby_helmet", "ruby_chestplate", "ruby_leggings", "ruby_boots"} & features:
                covered.add("equipment_sets")
                covered.add("equipment_recipes")
            if "ruby_shrine" in features:
                covered.add("structure_preview")
        return covered


def _count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "")
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def _merge_counts(target: dict[str, int], source: dict[str, Any]) -> None:
    for key, value in source.items():
        target[str(key)] = target.get(str(key), 0) + int(value or 0)


def _decision_knowledge_chains(run_name: Any, decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chains: list[dict[str, Any]] = []
    for decision in decisions:
        refs = [item for item in decision.get("knowledge_refs", []) if isinstance(item, dict)]
        if not refs:
            continue
        chains.append(
            {
                "run": str(run_name),
                "role": str(decision.get("role", "")),
                "decision": str(decision.get("decision", "")),
                "status": str(decision.get("status", "")),
                "rationale": str(decision.get("rationale", "")),
                "knowledge_ids": [str(item.get("id", "")) for item in refs if item.get("id")],
                "knowledge_refs": refs,
            }
        )
    return chains


def _repair_rag_links(
    root_causes: list[Any],
    repair_plan: list[dict[str, Any]],
    repair_rag: dict[str, Any],
) -> list[dict[str, Any]]:
    hits = repair_rag.get("hits") if isinstance(repair_rag, dict) else []
    if not isinstance(hits, list):
        hits = []
    query = str(repair_rag.get("query", "")) if isinstance(repair_rag, dict) else ""
    causes = [str(item) for item in root_causes] or ["No classified root cause recorded."]
    actions = repair_plan or [{"id": "review_repair_context", "summary": "Review repair context and related RAG evidence."}]
    top_hits = [hit for hit in hits if isinstance(hit, dict)][:5]
    knowledge_ids = [str(hit.get("id", "")) for hit in top_hits if hit.get("id")]
    knowledge_titles = [str(hit.get("title", "")) for hit in top_hits if hit.get("title")]
    links: list[dict[str, Any]] = []
    for index, cause in enumerate(causes):
        action = actions[min(index, len(actions) - 1)]
        links.append(
            {
                "root_cause": cause,
                "action_id": str(action.get("id", "action")),
                "action_summary": str(action.get("summary", "")),
                "query": query,
                "knowledge_ids": list(knowledge_ids),
                "knowledge_titles": list(knowledge_titles),
                "hits_count": len(top_hits),
            }
        )
    return links

from __future__ import annotations

import json
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .agent_orchestrator import AgentOrchestrator
from .config import AppConfig
from .evaluator import BenchmarkEvaluator
from .knowledge_base import NeoForgeKnowledgeBase
from .models import RequestOverrides
from .tools import resolve_workspace_child, slugify_mod_id


@dataclass(slots=True)
class WebDemoServerResult:
    success: bool
    host: str
    port: int
    url: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "host": self.host,
            "port": self.port,
            "url": self.url,
            "web_demo_url": self.url,
            "message": self.message,
        }


@dataclass(slots=True)
class WebDemoJob:
    identifier: str
    kind: str
    status: str
    created_at: str
    updated_at: str
    workspace: str | None = None
    build_log_paths: dict[str, str] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": True,
            "job_id": self.identifier,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "workspace": self.workspace,
            "build_log_paths": dict(self.build_log_paths),
            "logs": [dict(entry) for entry in self.logs],
            "result": self.result,
            "error": self.error,
            "error_type": self.error_type,
        }


class WebDemoRunner:
    """Interactive demo facade around the existing deterministic agent workflow."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()
        self._jobs: dict[str, WebDemoJob] = {}
        self._jobs_lock = threading.Lock()
        self.knowledge_base = NeoForgeKnowledgeBase()

    def health(self) -> dict[str, Any]:
        return {
            "success": True,
            "name": "NeoForge Mod Agent Web Demo",
            "version": self._project_version(),
            "workspace_root": str(self.config.workspace_root),
            "planner_options": [
                "rules",
                "mock-llm",
                "real-llm",
                "auto-mock",
                "auto-real",
            ],
            "knowledge_entries_count": len(self.knowledge_base.entries),
        }

    def run_generate(
        self,
        request: str,
        *,
        planner_selection: str = "mock-llm",
        workspace_name: str | None = None,
        overwrite: bool = True,
        run_build: bool = False,
        run_audit: bool = True,
    ) -> dict[str, Any]:
        request = request.strip()
        if not request:
            return {
                "success": False,
                "error": "Prompt is required.",
                "error_type": "ValueError",
            }

        planner_mode, llm_provider = self._planner_selection(planner_selection)
        workspace_name = workspace_name.strip() if workspace_name else self._workspace_name_from_request(request)
        started = time.perf_counter()
        try:
            run = AgentOrchestrator(self.config).run_generate(
                request,
                overrides=RequestOverrides(),
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                workspace_name=workspace_name,
                overwrite=overwrite,
                run_build=run_build,
                run_audit=run_audit,
                repair=True,
            )
            payload = run.to_dict()
            return self._demo_generate_payload(
                payload,
                planner_selection=planner_selection,
                duration_seconds=round(time.perf_counter() - started, 3),
            )
        except Exception as exc:  # The Web Demo should report failures as data, not crash the server.
            return {
                "success": False,
                "request": request,
                "planner_selection": planner_selection,
                "planner_mode": planner_mode,
                "llm_provider": llm_provider,
            "workspace_name": workspace_name,
                "duration_seconds": round(time.perf_counter() - started, 3),
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

    def list_workspaces(self) -> dict[str, Any]:
        root = self.config.workspace_root
        workspaces = []
        if root.exists():
            for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
                if child.is_dir() and (child / ".agent" / "modspec.json").exists():
                    workspaces.append(self._workspace_summary(child))
        workspaces.sort(key=lambda item: item.get("modified_at", ""), reverse=True)
        return {
            "success": True,
            "workspace_root": str(root),
            "workspaces": workspaces,
            "workspaces_count": len(workspaces),
        }

    def get_workspace(self, workspace_name: str) -> dict[str, Any]:
        try:
            workspace = self._resolve_workspace(workspace_name)
            agent_dir = workspace / ".agent"
            modspec = self._load_json(agent_dir / "modspec.json")
            summary = self._load_json(agent_dir / "generation-summary.json", default={})
            audit = self._load_json(agent_dir / "audit-report.json", default={})
            trace = self._load_json(agent_dir / "agent-trace-summary.json", default={})
            repair_plan = self._load_json(agent_dir / "agent-repair-plan.json", default={})
            repair_loop = self._load_json(agent_dir / "repair-loop-report.json", default={})
            repair_rag = self._load_json(agent_dir / "repair-rag-context.json", default={})
            self_healing = self._repair_summary_from_workspace(
                workspace,
                repair_plan=repair_plan,
                repair_loop=repair_loop,
                repair_rag=repair_rag,
            )
            console = self._workspace_console_summary(workspace)
            return {
                "success": True,
                "workspace": str(workspace),
                "name": workspace.name,
                "summary": self._workspace_summary(workspace),
                "modspec": modspec,
                "generation_summary": summary,
                "audit": audit,
                "agent_trace_summary": trace,
                "repair_plan": repair_plan,
                "repair_loop": repair_loop,
                "repair_rag": repair_rag,
                "self_healing": self_healing,
                "evidence": console["evidence"],
                "direct_code": console["direct_code"],
                "resource_preview": console["resource_preview"],
                "harvest_summary": console["harvest_summary"],
            }
        except Exception as exc:
            return {
                "success": False,
                "workspace": workspace_name,
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

    def start_generate_job(
        self,
        request: str,
        *,
        planner_selection: str = "mock-llm",
        workspace_name: str | None = None,
        overwrite: bool = True,
        run_build: bool = False,
        run_audit: bool = True,
    ) -> dict[str, Any]:
        request = request.strip()
        workspace_name = workspace_name.strip() if workspace_name else self._workspace_name_from_request(request)
        workspace_path = resolve_workspace_child(self.config.workspace_root, workspace_name)
        job = self._create_job(
            "generate",
            workspace=str(workspace_path),
            build_log_paths=self._expected_build_log_paths(workspace_path),
        )
        self._append_job_log(job.identifier, "queued", "Generate job queued.")
        thread = threading.Thread(
            target=self._execute_generate_job,
            args=(job.identifier, request),
            kwargs={
                "planner_selection": planner_selection,
                "workspace_name": workspace_name,
                "overwrite": overwrite,
                "run_build": run_build,
                "run_audit": run_audit,
            },
            daemon=True,
        )
        thread.start()
        return self.get_job(job.identifier)

    def start_modify_job(
        self,
        workspace_name: str,
        change_request: str,
        *,
        planner_selection: str = "mock-llm",
        run_build: bool = False,
        run_audit: bool = True,
    ) -> dict[str, Any]:
        workspace = self._resolve_workspace(workspace_name)
        job = self._create_job(
            "modify",
            workspace=str(workspace),
            build_log_paths=self._expected_build_log_paths(workspace),
        )
        self._append_job_log(job.identifier, "queued", "Modify job queued.")
        thread = threading.Thread(
            target=self._execute_modify_job,
            args=(job.identifier, workspace.name, change_request),
            kwargs={
                "planner_selection": planner_selection,
                "run_build": run_build,
                "run_audit": run_audit,
            },
            daemon=True,
        )
        thread.start()
        return self.get_job(job.identifier)

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return {
                    "success": False,
                    "error": f"Job not found: {job_id}",
                    "error_type": "FileNotFoundError",
                }
            payload = job.to_dict()
        payload["live_build_output"] = self._build_output_preview_from_paths(payload.get("build_log_paths", {}))
        return payload

    def list_knowledge_entries(
        self,
        *,
        query: str = "",
        category: str = "",
        capability: str = "",
        tag: str = "",
        limit: int = 50,
    ) -> dict[str, Any]:
        query = query.strip()
        category = category.strip()
        capability = capability.strip()
        tag = tag.strip()
        limit = max(1, min(int(limit), 100))

        if query:
            hit_by_id = {hit.entry.identifier: hit for hit in self.knowledge_base.query(query, limit=12)}
            entries = [hit.entry for hit in hit_by_id.values()]
        else:
            hit_by_id = {}
            entries = list(self.knowledge_base.entries)

        filtered = []
        for entry in entries:
            entry_capability = entry.capability or entry.category
            if category and entry.category != category:
                continue
            if capability and entry_capability != capability:
                continue
            if tag and tag not in entry.tags:
                continue
            hit = hit_by_id.get(entry.identifier)
            filtered.append(
                {
                    **entry.to_dict(),
                    "score": hit.score if hit else None,
                    "matched_terms": list(hit.matched_terms) if hit else [],
                    "snippet": hit.snippet if hit else entry.summary,
                }
            )

        if query:
            filtered.sort(key=lambda item: (-(item.get("score") or 0), item["id"]))
        else:
            filtered.sort(key=lambda item: item["id"])
        filtered = filtered[:limit]
        options = self._knowledge_filter_options()
        return {
            "success": True,
            "query": query,
            "category": category,
            "capability": capability,
            "tag": tag,
            "limit": limit,
            "entries": filtered,
            "entries_count": len(filtered),
            "total_entries": len(self.knowledge_base.entries),
            "categories": options["categories"],
            "capabilities": options["capabilities"],
            "tags": options["tags"],
            "filters": {
                "category": category,
                "capability": capability,
                "tag": tag,
            },
        }

    def run_modify(
        self,
        workspace_name: str,
        change_request: str,
        *,
        planner_selection: str = "mock-llm",
        run_build: bool = False,
        run_audit: bool = True,
    ) -> dict[str, Any]:
        change_request = change_request.strip()
        if not change_request:
            return {
                "success": False,
                "error": "Change request is required.",
                "error_type": "ValueError",
            }

        planner_mode, llm_provider = self._planner_selection(planner_selection)
        started = time.perf_counter()
        try:
            workspace = self._resolve_workspace(workspace_name)
            before = self._load_json(workspace / ".agent" / "modspec.json")
            run = AgentOrchestrator(self.config).run_modify(
                workspace,
                change_request,
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                run_build=run_build,
                run_audit=run_audit,
                repair=True,
            )
            after = self._load_json(workspace / ".agent" / "modspec.json")
            return self._demo_modify_payload(
                run.to_dict(),
                before_modspec=before,
                after_modspec=after,
                planner_selection=planner_selection,
                duration_seconds=round(time.perf_counter() - started, 3),
            )
        except Exception as exc:
            return {
                "success": False,
                "workspace": workspace_name,
                "change_request": change_request,
                "planner_selection": planner_selection,
                "planner_mode": planner_mode,
                "llm_provider": llm_provider,
                "duration_seconds": round(time.perf_counter() - started, 3),
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

    def run_eval(
        self,
        *,
        planner_selection: str = "mock-llm",
        limit: int = 3,
        run_build: bool = False,
        run_audit: bool = True,
        run_name: str | None = None,
    ) -> dict[str, Any]:
        planner_mode, llm_provider = self._planner_selection(planner_selection)
        started = time.perf_counter()
        try:
            result = BenchmarkEvaluator(self.config).run(
                planner_mode=planner_mode,
                llm_provider=llm_provider,
                run_build=run_build,
                run_audit=run_audit,
                limit=max(1, int(limit)),
                run_name=run_name or f"v33-web-demo-eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            )
            payload = result.to_dict()
            return {
                "success": result.success,
                "planner_selection": planner_selection,
                "planner_mode": planner_mode,
                "llm_provider": llm_provider,
                "duration_seconds": round(time.perf_counter() - started, 3),
                "summary": {
                    "cases": payload.get("metrics", {}).get("total_cases", 0),
                    "success_rate": payload.get("metrics", {}).get("success_rate", 0),
                    "audit_success_rate": payload.get("metrics", {}).get("audit_success_rate", 0),
                    "rag_hit_rate": payload.get("metrics", {}).get("rag_hit_rate", 0),
                },
                "eval": payload,
            }
        except Exception as exc:
            return {
                "success": False,
                "planner_selection": planner_selection,
                "planner_mode": planner_mode,
                "llm_provider": llm_provider,
                "duration_seconds": round(time.perf_counter() - started, 3),
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

    def _execute_generate_job(
        self,
        job_id: str,
        request: str,
        *,
        planner_selection: str,
        workspace_name: str,
        overwrite: bool,
        run_build: bool,
        run_audit: bool,
    ) -> None:
        self._mark_job_running(job_id, f"Starting generate for workspace '{workspace_name}'.")
        self._append_job_log(job_id, "info", f"Planner selection: {planner_selection}.")
        self._append_job_log(job_id, "info", f"Audit: {run_audit}; build: {run_build}; overwrite: {overwrite}.")
        if run_build:
            self._append_job_log(job_id, "info", "Gradle build enabled; build stdout/stderr will appear as soon as log files are created.")
        try:
            result = self.run_generate(
                request,
                planner_selection=planner_selection,
                workspace_name=workspace_name,
                overwrite=overwrite,
                run_build=run_build,
                run_audit=run_audit,
            )
            result["run_log"] = self._job_logs_snapshot(job_id)
            result["build_output"] = self._build_output_preview(result.get("build", {}))
            status = "succeeded" if result.get("success") else "failed"
            self._finish_job(job_id, status, result=result, message=f"Generate job {status}.")
        except Exception as exc:  # Defensive guard for background threads.
            self._finish_job(
                job_id,
                "failed",
                error=str(exc),
                error_type=type(exc).__name__,
                message=f"Generate job failed: {exc}",
            )

    def _execute_modify_job(
        self,
        job_id: str,
        workspace_name: str,
        change_request: str,
        *,
        planner_selection: str,
        run_build: bool,
        run_audit: bool,
    ) -> None:
        self._mark_job_running(job_id, f"Starting modify for workspace '{workspace_name}'.")
        self._append_job_log(job_id, "info", f"Planner selection: {planner_selection}.")
        self._append_job_log(job_id, "info", f"Audit: {run_audit}; build: {run_build}.")
        if run_build:
            self._append_job_log(job_id, "info", "Gradle build enabled; polling will include build log tails.")
        try:
            result = self.run_modify(
                workspace_name,
                change_request,
                planner_selection=planner_selection,
                run_build=run_build,
                run_audit=run_audit,
            )
            result["run_log"] = self._job_logs_snapshot(job_id)
            result["build_output"] = self._build_output_preview(result.get("build", {}))
            status = "succeeded" if result.get("success") else "failed"
            self._finish_job(job_id, status, result=result, message=f"Modify job {status}.")
        except Exception as exc:  # Defensive guard for background threads.
            self._finish_job(
                job_id,
                "failed",
                error=str(exc),
                error_type=type(exc).__name__,
                message=f"Modify job failed: {exc}",
            )

    def smoke(self, *, planner_selection: str = "mock-llm") -> dict[str, Any]:
        html = self.render_index_html()
        generate = self.run_generate(
            "Create a ruby mod with ruby.",
            planner_selection=planner_selection,
            workspace_name="v35-web-demo-smoke",
            overwrite=True,
            run_build=False,
            run_audit=True,
        )
        workspaces = self.list_workspaces()
        selected = self.get_workspace("v35-web-demo-smoke")
        modify = self.run_modify(
            "v35-web-demo-smoke",
            "Add a ruby charm item that heals 4 health on right click with 20 seconds cooldown.",
            planner_selection=planner_selection,
            run_build=False,
            run_audit=True,
        )
        return {
            "success": bool(generate.get("success")) and bool(modify.get("success")) and "api/generate" in html and "api/modify" in html,
            "web_demo_smoke": True,
            "html_contains_form": "promptInput" in html,
            "html_contains_generate_api": "api/generate" in html,
            "html_contains_modify_api": "api/modify" in html,
            "html_contains_job_api": "api/jobs/generate" in html and "api/job" in html,
            "html_contains_workspace_select": "workspaceSelect" in html,
            "html_contains_run_log": "runLogOutput" in html,
            "html_contains_build_output": "buildLogOutput" in html,
            "html_contains_project_console": "Project Console" in html,
            "html_contains_evidence_view": "evidenceView" in html and "Evidence" in html,
            "html_contains_direct_code_view": "directCodeView" in html and "Direct Code" in html,
            "html_contains_resources_view": "resourcesView" in html and "Resources" in html,
            "html_contains_knowledge_base": "knowledgeOutput" in html and "api/knowledge" in html,
            "html_contains_self_healing": "repairView" in html and "Self-Healing" in html,
            "generate_success": bool(generate.get("success")),
            "modify_success": bool(modify.get("success")),
            "workspace": generate.get("workspace"),
            "workspaces_count": workspaces.get("workspaces_count", 0),
            "workspace_load_success": bool(selected.get("success")),
            "modspec_feature_count": generate.get("summary", {}).get("features_count", 0),
            "generated_files_count": generate.get("summary", {}).get("generated_files_count", 0),
            "audit_success": generate.get("audit", {}).get("success"),
            "modify_added": modify.get("merge", {}).get("added", []),
            "modify_updated": modify.get("merge", {}).get("updated", []),
            "modify_skipped": modify.get("merge", {}).get("skipped", []),
            "modify_diff": modify.get("modspec_diff", {}),
            "agent_roles_count": generate.get("agent_trace", {}).get("roles_count", 0),
            "build_output_available": bool(generate.get("build_output", {}).get("available")),
            "repair_needed": generate.get("repair", {}).get("repair_needed"),
            "repair_executed": generate.get("repair", {}).get("repair_executed"),
            "direct_code_used": generate.get("summary", {}).get("direct_code_used"),
            "rollback_recommended": generate.get("summary", {}).get("rollback_recommended"),
            "knowledge_entries_count": self.list_knowledge_entries().get("entries_count", 0),
        }

    def _create_job(
        self,
        kind: str,
        *,
        workspace: str | None = None,
        build_log_paths: dict[str, str] | None = None,
    ) -> WebDemoJob:
        now = self._now()
        job = WebDemoJob(
            identifier=f"{kind}-{uuid.uuid4().hex[:12]}",
            kind=kind,
            status="queued",
            created_at=now,
            updated_at=now,
            workspace=workspace,
            build_log_paths=build_log_paths or {},
        )
        with self._jobs_lock:
            self._jobs[job.identifier] = job
        return job

    def _mark_job_running(self, job_id: str, message: str) -> None:
        with self._jobs_lock:
            job = self._jobs[job_id]
            job.status = "running"
            job.updated_at = self._now()
        self._append_job_log(job_id, "running", message)

    def _finish_job(
        self,
        job_id: str,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        error_type: str | None = None,
        message: str,
    ) -> None:
        with self._jobs_lock:
            job = self._jobs[job_id]
            job.status = status
            job.updated_at = self._now()
            job.logs.append(
                {
                    "time": job.updated_at,
                    "level": "success" if status == "succeeded" else "error",
                    "message": message,
                }
            )
            if result is not None:
                result["run_log"] = [dict(entry) for entry in job.logs]
            job.result = result
            job.error = error
            job.error_type = error_type
            if result and result.get("workspace"):
                job.workspace = str(result.get("workspace"))

    def _append_job_log(self, job_id: str, level: str, message: str) -> None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.logs.append(
                {
                    "time": self._now(),
                    "level": level,
                    "message": message,
                }
            )
            job.updated_at = self._now()

    def _job_logs_snapshot(self, job_id: str) -> list[dict[str, Any]]:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return []
            return [dict(entry) for entry in job.logs]

    def _expected_build_log_paths(self, workspace: Path) -> dict[str, str]:
        logs_dir = self.config.logs_dir_for(workspace)
        task = self.config.gradle_task
        return {
            "log_path": str(logs_dir / f"gradle-{task}.log"),
            "stdout_path": str(logs_dir / f"gradle-{task}.stdout.log"),
            "stderr_path": str(logs_dir / f"gradle-{task}.stderr.log"),
        }

    def _build_output_preview(self, build: dict[str, Any], *, max_lines: int = 80) -> dict[str, Any]:
        if not isinstance(build, dict):
            return {"attempted": False, "available": False, "max_lines": max_lines}
        paths = {
            "log_path": str(build.get("log_path") or ""),
            "stdout_path": str(build.get("stdout_path") or ""),
            "stderr_path": str(build.get("stderr_path") or ""),
        }
        preview = self._build_output_preview_from_paths(paths, max_lines=max_lines)
        preview.update(
            {
                "attempted": build.get("attempted", preview.get("attempted", False)),
                "success": build.get("success"),
                "summary": build.get("summary", ""),
                "return_code": build.get("return_code", build.get("exit_code")),
                "command": list(build.get("command", [])) if isinstance(build.get("command"), list) else [],
            }
        )
        return preview

    def _build_output_preview_from_paths(
        self,
        paths: dict[str, str],
        *,
        max_lines: int = 80,
    ) -> dict[str, Any]:
        log_path = Path(paths.get("log_path") or "")
        stdout_path = Path(paths.get("stdout_path") or "")
        stderr_path = Path(paths.get("stderr_path") or "")
        log_tail = self._tail_text(log_path, max_lines=max_lines) if paths.get("log_path") else ""
        stdout_tail = self._tail_text(stdout_path, max_lines=max_lines) if paths.get("stdout_path") else ""
        stderr_tail = self._tail_text(stderr_path, max_lines=max_lines) if paths.get("stderr_path") else ""
        return {
            "attempted": bool(log_tail or stdout_tail or stderr_tail),
            "available": bool(log_tail or stdout_tail or stderr_tail),
            "max_lines": max_lines,
            "log_path": str(log_path) if paths.get("log_path") else "",
            "stdout_path": str(stdout_path) if paths.get("stdout_path") else "",
            "stderr_path": str(stderr_path) if paths.get("stderr_path") else "",
            "log_tail": log_tail,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
        }

    def _tail_text(self, path: Path, *, max_lines: int = 80) -> str:
        if not path.exists() or not path.is_file():
            return ""
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-max_lines:])

    def _repair_summary_from_agent_payload(
        self,
        payload: dict[str, Any],
        *,
        workspace: Path | None = None,
    ) -> dict[str, Any]:
        agent_payload = payload.get("payload", {}) if isinstance(payload, dict) else {}
        repair_payload = agent_payload.get("repair", {}) if isinstance(agent_payload, dict) else {}
        return self._repair_summary_from_repair_payload(repair_payload, workspace=workspace)

    def _repair_summary_from_workspace(
        self,
        workspace: Path,
        *,
        repair_plan: dict[str, Any] | None = None,
        repair_loop: dict[str, Any] | None = None,
        repair_rag: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        repair_payload = dict(repair_plan or {})
        if repair_loop and "repair_loop" not in repair_payload:
            repair_payload["repair_loop"] = repair_loop
        if repair_rag and "repair_rag" not in repair_payload:
            repair_payload["repair_rag"] = repair_rag
        return self._repair_summary_from_repair_payload(repair_payload, workspace=workspace)

    def _repair_summary_from_repair_payload(
        self,
        repair_payload: dict[str, Any] | None,
        *,
        workspace: Path | None = None,
    ) -> dict[str, Any]:
        repair = repair_payload if isinstance(repair_payload, dict) else {}
        loop = repair.get("repair_loop") if isinstance(repair.get("repair_loop"), dict) else {}
        repair_rag = repair.get("repair_rag") if isinstance(repair.get("repair_rag"), dict) else {}
        root_causes = repair.get("root_causes") if isinstance(repair.get("root_causes"), list) else []
        repair_plan = repair.get("repair_plan") if isinstance(repair.get("repair_plan"), list) else []
        attempts = loop.get("attempts") if isinstance(loop.get("attempts"), list) else []
        rag_hits = repair_rag.get("hits") if isinstance(repair_rag.get("hits"), list) else []
        paths = self._repair_artifact_paths(workspace)
        summary = {
            "available": bool(repair) or any(item.get("exists") for item in paths.values()),
            "repair_needed": repair.get("repair_needed"),
            "repair_executed": repair.get("repair_executed"),
            "repair_success": repair.get("repair_success"),
            "root_causes": root_causes,
            "root_causes_count": len(root_causes),
            "repair_plan": repair_plan,
            "repair_actions_count": len(repair_plan),
            "repair_rag": repair_rag,
            "repair_rag_query": repair_rag.get("query", ""),
            "repair_rag_hits": rag_hits,
            "repair_rag_hits_count": int(repair_rag.get("hits_count", len(rag_hits)) or 0),
            "repair_rag_categories": repair_rag.get("categories", {}),
            "repair_rag_capabilities": repair_rag.get("capabilities", {}),
            "repair_rag_links": _repair_rag_links(root_causes, repair_plan, repair_rag),
            "repair_rag_report_json_path": repair_rag.get("report_json_path") or paths["repair_rag_context_json_path"]["path"],
            "repair_rag_report_md_path": repair_rag.get("report_md_path") or paths["repair_rag_context_md_path"]["path"],
            "attempts_count": int(loop.get("attempts_count", len(attempts)) or 0),
            "repaired": loop.get("repaired"),
            "attempts": attempts,
            "repair_loop_report_json_path": repair.get("repair_loop_report_json_path") or loop.get("repair_loop_report_json_path") or paths["repair_loop_report_json_path"]["path"],
            "repair_loop_report_md_path": repair.get("repair_loop_report_md_path") or loop.get("repair_loop_report_md_path") or paths["repair_loop_report_md_path"]["path"],
            "agent_repair_plan_json_path": paths["agent_repair_plan_json_path"]["path"],
            "agent_repair_plan_md_path": paths["agent_repair_plan_md_path"]["path"],
            "artifacts": paths,
        }
        return summary

    def _repair_artifact_paths(self, workspace: Path | None) -> dict[str, dict[str, Any]]:
        names = {
            "agent_repair_plan_json_path": "agent-repair-plan.json",
            "agent_repair_plan_md_path": "agent-repair-plan.md",
            "repair_loop_report_json_path": "repair-loop-report.json",
            "repair_loop_report_md_path": "repair-loop-report.md",
            "repair_rag_context_json_path": "repair-rag-context.json",
            "repair_rag_context_md_path": "repair-rag-context.md",
        }
        result: dict[str, dict[str, Any]] = {}
        if workspace is None:
            return {key: {"path": "", "exists": False} for key in names}
        agent_dir = workspace / ".agent"
        for key, filename in names.items():
            path = agent_dir / filename
            result[key] = {"path": str(path), "exists": path.exists()}
        return result

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _knowledge_filter_options(self) -> dict[str, list[dict[str, Any]]]:
        categories: dict[str, int] = {}
        capabilities: dict[str, int] = {}
        tags: dict[str, int] = {}
        for entry in self.knowledge_base.entries:
            categories[entry.category] = categories.get(entry.category, 0) + 1
            capability = entry.capability or entry.category
            capabilities[capability] = capabilities.get(capability, 0) + 1
            for tag in entry.tags:
                tags[tag] = tags.get(tag, 0) + 1
        return {
            "categories": [{"id": key, "count": value} for key, value in sorted(categories.items())],
            "capabilities": [{"id": key, "count": value} for key, value in sorted(capabilities.items())],
            "tags": [{"id": key, "count": value} for key, value in sorted(tags.items())],
        }

    def render_index_html(self) -> str:
        version = escape(self._project_version())
        return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NeoForge Mod Agent Project Console</title>
  <style>
    :root {
      --bg: #121914;
      --ink: #f4efd9;
      --muted: #aab7a6;
      --panel: rgba(246, 239, 213, 0.08);
      --panel-strong: rgba(246, 239, 213, 0.14);
      --line: rgba(246, 239, 213, 0.16);
      --accent: #7ed7a6;
      --accent-2: #f2b15e;
      --danger: #ff8577;
      --ok: #7ed7a6;
      --shadow: 0 24px 80px rgba(0, 0, 0, 0.34);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      font-family: "Trebuchet MS", "Gill Sans", Verdana, sans-serif;
      background:
        radial-gradient(circle at 12% 8%, rgba(126, 215, 166, 0.24), transparent 26rem),
        radial-gradient(circle at 82% 16%, rgba(242, 177, 94, 0.22), transparent 30rem),
        linear-gradient(145deg, #111914 0%, #1b281f 50%, #151a18 100%);
      min-height: 100vh;
    }
    header, main { position: relative; z-index: 1; }
    header {
      padding: 48px min(6vw, 76px) 24px;
      display: grid;
      grid-template-columns: 1.2fr .8fr;
      gap: 28px;
      align-items: end;
    }
    .eyebrow {
      color: var(--accent);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .12em;
      text-transform: uppercase;
    }
    h1 {
      margin: 12px 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(42px, 7vw, 88px);
      line-height: .92;
      letter-spacing: -0.06em;
    }
    .lead {
      max-width: 780px;
      color: var(--muted);
      line-height: 1.7;
      font-size: 17px;
    }
    main {
      display: grid;
      grid-template-columns: 420px minmax(0, 1fr);
      gap: 20px;
      padding: 0 min(6vw, 76px) 72px;
    }
    .panel {
      border: 1px solid var(--line);
      border-radius: 30px;
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
      overflow: hidden;
    }
    .panel h2 {
      margin: 0;
      padding: 22px 24px 8px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 30px;
      letter-spacing: -0.04em;
    }
    .panel p {
      margin: 0;
      padding: 0 24px 18px;
      color: var(--muted);
      line-height: 1.55;
    }
    .form {
      display: grid;
      gap: 14px;
      padding: 20px 24px 24px;
    }
    label {
      display: grid;
      gap: 8px;
      color: var(--muted);
      font-weight: 700;
      font-size: 13px;
    }
    textarea, input, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 13px 14px;
      color: var(--ink);
      background: rgba(0, 0, 0, 0.22);
      outline: none;
      font: inherit;
    }
    textarea { min-height: 152px; resize: vertical; }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .checks {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }
    .checks label {
      display: flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 10px;
      background: rgba(255,255,255,.04);
    }
    .checks input { width: auto; }
    button {
      border: 0;
      border-radius: 18px;
      padding: 13px 16px;
      cursor: pointer;
      color: #102015;
      background: linear-gradient(135deg, var(--accent), #c4f0c2);
      font-weight: 900;
      letter-spacing: .02em;
    }
    button.secondary {
      color: var(--ink);
      background: rgba(242, 177, 94, 0.18);
      border: 1px solid rgba(242, 177, 94, 0.36);
    }
    .results {
      display: grid;
      gap: 20px;
    }
    .status {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      padding: 18px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 16px;
      background: var(--panel-strong);
    }
    .metric strong {
      display: block;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 34px;
      line-height: 1;
    }
    .metric span {
      display: block;
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
    }
    .tabs {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      padding: 0 18px 18px;
    }
    .tab {
      color: var(--ink);
      border: 1px solid var(--line);
      background: rgba(255,255,255,.05);
      padding: 9px 12px;
      border-radius: 999px;
    }
    .tab.active { background: rgba(126, 215, 166, .18); border-color: rgba(126, 215, 166, .5); }
    .view { display: none; padding: 0 18px 18px; }
    .view.active { display: block; }
    pre {
      margin: 0;
      max-height: 520px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(0, 0, 0, .34);
      padding: 16px;
      color: #eef8e9;
      font-size: 12px;
      line-height: 1.5;
      white-space: pre-wrap;
    }
    .list {
      display: grid;
      gap: 9px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .list li {
      border: 1px solid var(--line);
      border-radius: 15px;
      padding: 10px 12px;
      background: rgba(255,255,255,.04);
      overflow-wrap: anywhere;
    }
    .ok { color: var(--ok); }
    .fail { color: var(--danger); }
    .muted { color: var(--muted); }
    @media (max-width: 1050px) {
      header, main { grid-template-columns: 1fr; }
      .status { grid-template-columns: repeat(2, 1fr); }
    }
    @media (max-width: 680px) {
      header, main { padding-left: 18px; padding-right: 18px; }
      .row, .checks, .status { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <div class="eyebrow">Local Project Console</div>
      <div class="eyebrow">ModSpec-first / Controlled Patch Evidence / Audit</div>
      <h1>NeoForge Mod Agent 控制台</h1>
      <p class="lead">本地打开、现场操作：生成或修改 workspace，查看 audit/build、Direct Code Lane review / snapshot / rollback evidence、RAG / repair 和资源预览。它不是通用 Coding Agent；Direct Code 只接受结构化 workspace patch。</p>
    </div>
    <div class="panel">
      <h2>运行状态</h2>
      <p>当前版本：__VERSION__。默认不跑 Gradle build，适合快速本地控制；需要强验证时勾选 build。</p>
    </div>
  </header>
  <main>
    <section class="panel">
      <h2>Run</h2>
      <p>用 mock LLM 离线复现；真实 LLM 使用 OpenAI-compatible provider，需要提前配置环境变量。</p>
      <div class="form">
        <label>输入 Prompt
          <textarea id="promptInput">Create a ruby mod with a ruby charm item.</textarea>
        </label>
        <div class="row">
          <label>Planner
            <select id="plannerSelect">
              <option value="mock-llm">Mock LLM（离线推荐）</option>
              <option value="rules">Rules</option>
              <option value="real-llm">Real LLM（OpenAI-compatible）</option>
              <option value="auto-mock">Auto + Mock LLM</option>
              <option value="auto-real">Auto + Real LLM</option>
            </select>
          </label>
          <label>Workspace 名称
            <input id="workspaceInput" value="v35-web-demo-run">
          </label>
        </div>
        <div class="checks">
          <label><input id="auditCheck" type="checkbox" checked> audit</label>
          <label><input id="buildCheck" type="checkbox"> build</label>
          <label><input id="overwriteCheck" type="checkbox" checked> overwrite</label>
        </div>
        <button id="generateButton">生成 Mod 工作区</button>
        <div class="row">
          <label>已有 Workspace
            <select id="workspaceSelect"></select>
          </label>
          <button class="secondary" id="refreshWorkspacesButton">刷新 Workspace</button>
        </div>
        <button class="secondary" id="loadWorkspaceButton">读取当前 Workspace</button>
        <label>Modify Request
          <textarea id="modifyInput">Add a ruby charm item that heals 4 health on right click with 20 seconds cooldown.</textarea>
        </label>
        <button class="secondary" id="modifyButton">修改当前 Workspace</button>
        <div class="row">
          <button class="secondary" id="evalButton">运行 Eval Smoke</button>
          <label>Eval case 数
            <input id="evalLimit" type="number" min="1" max="12" value="3">
          </label>
        </div>
        <label>RAG 知识库搜索
          <input id="knowledgeSearchInput" value="worldgen ore">
        </label>
        <div class="row">
          <label>知识分类
            <select id="knowledgeCategorySelect"></select>
          </label>
          <label>能力筛选
            <select id="knowledgeCapabilitySelect"></select>
          </label>
        </div>
        <div class="row">
          <label>标签筛选
            <select id="knowledgeTagSelect"></select>
          </label>
          <button class="secondary" id="knowledgeRefreshButton">筛选知识库</button>
        </div>
        <p id="message" class="muted">等待输入。</p>
      </div>
    </section>
    <section class="results">
      <div class="panel">
        <div class="status">
          <div class="metric"><strong id="successMetric">-</strong><span>success</span></div>
          <div class="metric"><strong id="featureMetric">0</strong><span>features</span></div>
          <div class="metric"><strong id="fileMetric">0</strong><span>files</span></div>
          <div class="metric"><strong id="auditMetric">-</strong><span>audit/build/patch</span></div>
        </div>
      </div>
      <div class="panel">
        <h2>Workspace Console</h2>
        <p>切换标签查看当前 workspace 的运行结果和证据链。</p>
        <div class="tabs">
          <button class="tab active" data-view="overviewView">Overview</button>
          <button class="tab" data-view="runView">Run</button>
          <button class="tab" data-view="evidenceView">Evidence</button>
          <button class="tab" data-view="directCodeView">Direct Code</button>
          <button class="tab" data-view="repairView">RAG / Repair</button>
          <button class="tab" data-view="resourcesView">Resources</button>
          <button class="tab" data-view="rawView">Raw JSON</button>
        </div>
        <div id="overviewView" class="view active">
          <pre id="workspaceOutput">暂无 workspace 信息。</pre>
          <pre id="specOutput">暂无 ModSpec。</pre>
        </div>
        <div id="runView" class="view">
          <pre id="runLogOutput">暂无运行日志。</pre>
          <pre id="buildLogOutput">暂无 build 输出。勾选 build 后会显示 Gradle stdout/stderr/log 尾部。</pre>
          <pre id="checksOutput">暂无 audit/build/eval 结果。</pre>
        </div>
        <div id="evidenceView" class="view"><pre id="evidenceOutput">暂无 evidence。</pre><ul class="list" id="filesOutput"></ul></div>
        <div id="directCodeView" class="view"><pre id="directCodeOutput">Direct Code Lane 未使用或暂无数据。</pre><pre id="diffOutput">暂无 diff。</pre></div>
        <div id="repairView" class="view">
          <pre id="repairStatus">Self-Healing Repair Agent: No repair data yet.</pre>
          <ul class="list" id="repairAttempts"></ul>
          <ul class="list" id="knowledgeOutput"></ul>
          <pre id="knowledgeDetailOutput">暂无知识条目详情。</pre>
        </div>
        <div id="resourcesView" class="view"><pre id="resourcesOutput">暂无 resource preview。</pre></div>
        <div id="traceView" class="view"><pre id="traceOutput">暂无 agent trace。</pre></div>
        <div id="rawView" class="view"><pre id="rawOutput">暂无 raw JSON。</pre></div>
      </div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    let lastPayload = null;
    const terminalJobStatuses = new Set(["succeeded", "failed"]);
    const legacySyncApis = ["/api/generate", "/api/modify"];
    const asyncJobApis = ["/api/jobs/generate", "/api/jobs/modify", "/api/job"];

    function setMessage(text, ok = true) {
      $("message").textContent = text;
      $("message").className = ok ? "ok" : "fail";
    }

    function sleep(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    }

    async function postJson(url, body) {
      const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || response.statusText);
      }
      return payload;
    }

    async function getJson(url) {
      const response = await fetch(url, {headers: {"Accept": "application/json"}});
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || response.statusText);
      }
      return payload;
    }

    function renderJob(job) {
      const logs = job.logs || [];
      $("runLogOutput").textContent = logs.length
        ? logs.map((entry) => `${entry.time || ""} [${entry.level || "info"}] ${entry.message || ""}`).join("\\n")
        : "暂无运行日志。";
      renderBuildOutput(job.live_build_output || job.result?.build_output || null);
      if (job.status) {
        setMessage(`Job ${job.job_id}：${job.status}`, job.status !== "failed");
      }
    }

    function renderBuildOutput(output) {
      if (!output || !output.available) {
        $("buildLogOutput").textContent = "暂无 build 输出。勾选 build 后会显示 Gradle stdout/stderr/log 尾部。";
        return;
      }
      const sections = [
        `attempted: ${output.attempted}`,
        `success: ${output.success ?? "running/unknown"}`,
        `summary: ${output.summary || ""}`,
        `return_code: ${output.return_code ?? ""}`,
        `log_path: ${output.log_path || ""}`,
        `stdout_path: ${output.stdout_path || ""}`,
        `stderr_path: ${output.stderr_path || ""}`,
        "",
        "----- combined log tail -----",
        output.log_tail || "(empty)",
        "",
        "----- stdout tail -----",
        output.stdout_tail || "(empty)",
        "",
        "----- stderr tail -----",
        output.stderr_tail || "(empty)",
      ];
      $("buildLogOutput").textContent = sections.join("\\n");
    }

    function renderRepair(repair) {
      const payload = repair || {};
      const available = payload.available !== false && Object.keys(payload).length > 0;
      const lines = [
        "Self-Healing",
        "Repair Agent",
        "Repair Loop",
        `available: ${available}`,
        `repair_needed: ${payload.repair_needed ?? "unknown"}`,
        `repair_executed: ${payload.repair_executed ?? "unknown"}`,
        `repair_success: ${payload.repair_success ?? "unknown"}`,
        `root_causes_count: ${payload.root_causes_count ?? 0}`,
        `repair_actions_count: ${payload.repair_actions_count ?? 0}`,
        `attempts_count: ${payload.attempts_count ?? 0}`,
        "",
        "Repair RAG",
        `repair_rag_query: ${payload.repair_rag_query || ""}`,
        `repair_rag_hits_count: ${payload.repair_rag_hits_count ?? 0}`,
        `repair_rag_categories: ${JSON.stringify(payload.repair_rag_categories || {})}`,
        `repair_rag_capabilities: ${JSON.stringify(payload.repair_rag_capabilities || {})}`,
        `repair_rag_report_json_path: ${payload.repair_rag_report_json_path || ""}`,
        `agent_repair_plan_json_path: ${payload.agent_repair_plan_json_path || ""}`,
        `repair_loop_report_json_path: ${payload.repair_loop_report_json_path || ""}`,
      ];
      if (!available || payload.repair_needed === false) {
        lines.push("No repair needed for the latest healthy run.");
      }
      $("repairStatus").textContent = lines.join("\\n");
      const list = $("repairAttempts");
      list.innerHTML = "";
      const causes = payload.root_causes || [];
      for (const cause of causes) {
        const item = document.createElement("li");
        item.textContent = `Root cause: ${cause}`;
        list.appendChild(item);
      }
      const attempts = payload.attempts || [];
      const actions = payload.repair_plan || [];
      const ragHits = payload.repair_rag_hits || payload.repair_rag?.hits || [];
      const ragLinks = payload.repair_rag_links || [];
      for (const attempt of attempts) {
        const item = document.createElement("li");
        item.textContent = `Attempt ${attempt.index}: ${attempt.phase} / ${attempt.action} / success=${attempt.success}`;
        list.appendChild(item);
      }
      for (const action of actions) {
        const item = document.createElement("li");
        item.textContent = `Repair action: ${action.id || "action"} - ${action.summary || ""}`;
        list.appendChild(item);
      }
      for (const hit of ragHits.slice(0, 8)) {
        const item = document.createElement("li");
        item.textContent = `RAG hit: ${hit.id || ""} score=${hit.score ?? ""} / ${hit.category || ""} / ${hit.capability || ""} - ${hit.title || hit.summary || ""}`;
        list.appendChild(item);
      }
      for (const link of ragLinks.slice(0, 6)) {
        const item = document.createElement("li");
        item.textContent = `Why mapping: root="${link.root_cause || ""}" -> action="${link.action_id || ""}" -> knowledge=[${(link.knowledge_ids || []).join(", ")}]`;
        list.appendChild(item);
      }
      if (!causes.length && !attempts.length && !actions.length && !ragHits.length) {
        const item = document.createElement("li");
        item.textContent = payload.repair_needed ? "Repair was needed, but no loop attempts were recorded." : "No repair needed.";
        list.appendChild(item);
      }
    }

    function renderKnowledgeFilters(payload) {
      const fill = (select, items, placeholder) => {
        const current = select.value;
        select.innerHTML = "";
        const empty = document.createElement("option");
        empty.value = "";
        empty.textContent = placeholder;
        select.appendChild(empty);
        for (const item of items || []) {
          const option = document.createElement("option");
          option.value = item.id;
          option.textContent = `${item.id} (${item.count})`;
          select.appendChild(option);
        }
        if ([...select.options].some((option) => option.value === current)) {
          select.value = current;
        }
      };
      fill($("knowledgeCategorySelect"), payload.categories, "全部分类");
      fill($("knowledgeCapabilitySelect"), payload.capabilities, "全部能力");
      fill($("knowledgeTagSelect"), payload.tags, "全部标签");
    }

    function renderKnowledge(payload) {
      renderKnowledgeFilters(payload);
      const list = $("knowledgeOutput");
      list.innerHTML = "";
      const entries = payload.entries || [];
      if (!entries.length) {
        const item = document.createElement("li");
        item.textContent = "没有匹配的知识条目。";
        list.appendChild(item);
        $("knowledgeDetailOutput").textContent = JSON.stringify(payload, null, 2);
        return;
      }
      for (const entry of entries) {
        const item = document.createElement("li");
        const score = entry.score === null || entry.score === undefined ? "" : ` score=${entry.score}`;
        item.textContent = `${entry.id}${score} · ${entry.category} / ${entry.capability} · ${entry.title}\n${entry.summary}`;
        item.addEventListener("click", () => {
          $("knowledgeDetailOutput").textContent = JSON.stringify(entry, null, 2);
        });
        list.appendChild(item);
      }
      $("knowledgeDetailOutput").textContent = JSON.stringify(entries[0], null, 2);
    }

    async function loadKnowledge() {
      const params = new URLSearchParams();
      params.set("query", $("knowledgeSearchInput").value || "");
      params.set("category", $("knowledgeCategorySelect").value || "");
      params.set("capability", $("knowledgeCapabilitySelect").value || "");
      params.set("tag", $("knowledgeTagSelect").value || "");
      params.set("limit", "50");
      const payload = await getJson(`/api/knowledge?${params.toString()}`);
      renderKnowledge(payload);
      return payload;
    }

    async function startAndPollJob(kind, body) {
      const started = await postJson(`/api/jobs/${kind}`, body);
      renderJob(started);
      let current = started;
      while (!terminalJobStatuses.has(current.status)) {
        await sleep(900);
        current = await getJson(`/api/job?id=${encodeURIComponent(started.job_id)}`);
        renderJob(current);
      }
      if (current.result) {
        renderPayload(current.result);
      }
      return current;
    }

    function renderPayload(payload) {
      lastPayload = payload;
      const summary = payload.summary || {};
      $("successMetric").textContent = payload.success ? "yes" : "no";
      $("successMetric").className = payload.success ? "ok" : "fail";
      $("featureMetric").textContent = summary.features_count ?? payload.eval?.metrics?.total_cases ?? 0;
      $("fileMetric").textContent = summary.generated_files_count ?? payload.eval?.metrics?.generated_files_total ?? 0;
      const audit = payload.audit || {};
      const build = payload.build || {};
      const direct = payload.direct_code || {};
      const directStatus = direct.used ? (direct.rollback_recommended ? "rollback" : "used") : "none";
      $("auditMetric").textContent = `${audit.success === undefined ? "-" : audit.success}/${build.success === undefined ? "skip" : build.success}/${directStatus}`;
      $("specOutput").textContent = JSON.stringify(payload.modspec || payload.eval?.cases || {}, null, 2);
      $("workspaceOutput").textContent = JSON.stringify({
        workspace: payload.workspace || null,
        summary: payload.summary || null,
        evidence: payload.evidence || null,
        harvest_summary: payload.harvest_summary || null,
      }, null, 2);
      $("diffOutput").textContent = JSON.stringify({
        merge: payload.merge || null,
        modspec_diff: payload.modspec_diff || null,
        direct_code_diff: payload.direct_code?.artifacts?.direct_code_diff_md_path || null,
      }, null, 2);
      renderFiles(payload.generated_files || []);
      $("checksOutput").textContent = JSON.stringify({
        audit: payload.audit || null,
        build: payload.build || null,
        eval: payload.eval || null,
        repair: payload.repair || payload.self_healing || null,
        summary: payload.summary || null,
      }, null, 2);
      $("evidenceOutput").textContent = JSON.stringify({
        evidence: payload.evidence || null,
        artifacts: payload.artifacts || null,
        agent_trace: payload.agent_trace || payload.eval?.cases || null,
      }, null, 2);
      $("directCodeOutput").textContent = JSON.stringify(payload.direct_code || {used: false, status: "not_used"}, null, 2);
      $("resourcesOutput").textContent = JSON.stringify({
        resource_preview: payload.resource_preview || null,
        harvest_summary: payload.harvest_summary || null,
      }, null, 2);
      $("traceOutput").textContent = JSON.stringify(payload.agent_trace || payload.eval?.cases || {}, null, 2);
      if (payload.run_log) {
        $("runLogOutput").textContent = payload.run_log.map((entry) => `${entry.time || ""} [${entry.level || "info"}] ${entry.message || ""}`).join("\\n");
      }
      renderBuildOutput(payload.build_output || null);
      renderRepair(payload.repair || payload.self_healing || null);
      $("rawOutput").textContent = JSON.stringify(payload, null, 2);
    }

    function renderFiles(files) {
      const list = $("filesOutput");
      list.innerHTML = "";
      if (!files.length) {
        const item = document.createElement("li");
        item.textContent = "暂无生成文件。";
        list.appendChild(item);
        return;
      }
      for (const file of files) {
        const item = document.createElement("li");
        item.textContent = file;
        list.appendChild(item);
      }
    }

    function renderWorkspaceOptions(payload) {
      const select = $("workspaceSelect");
      const current = select.value;
      select.innerHTML = "";
      const workspaces = payload.workspaces || [];
      if (!workspaces.length) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "暂无可用 workspace";
        select.appendChild(option);
        return;
      }
      for (const workspace of workspaces) {
        const option = document.createElement("option");
        option.value = workspace.name;
        option.textContent = `${workspace.name} (${workspace.features_count || 0} features)`;
        select.appendChild(option);
      }
      if (current && workspaces.some((workspace) => workspace.name === current)) {
        select.value = current;
      }
    }

    async function loadWorkspaces() {
      const payload = await getJson("/api/workspaces");
      renderWorkspaceOptions(payload);
      $("workspaceOutput").textContent = JSON.stringify(payload, null, 2);
      return payload;
    }

    async function loadSelectedWorkspace() {
      const name = $("workspaceSelect").value || $("workspaceInput").value;
      if (!name) {
        setMessage("请先选择或输入 workspace。", false);
        return;
      }
      const payload = await getJson(`/api/workspace?name=${encodeURIComponent(name)}`);
      $("workspaceInput").value = payload.name || name;
      renderPayload({
        success: payload.success,
        workspace: payload.workspace,
        modspec: payload.modspec,
        generated_files: payload.generation_summary?.generated_files || [],
        audit: payload.audit || null,
        build: {},
        repair: payload.self_healing || {},
        self_healing: payload.self_healing || {},
        evidence: payload.evidence || {},
        direct_code: payload.direct_code || {},
        resource_preview: payload.resource_preview || {},
        harvest_summary: payload.harvest_summary || {},
        summary: payload.summary,
        agent_trace: payload.agent_trace_summary || {},
        artifacts: {
          modspec: `${payload.workspace}/.agent/modspec.json`,
          generation_summary: `${payload.workspace}/.agent/generation-summary.json`,
          agent_repair_plan: `${payload.workspace}/.agent/agent-repair-plan.json`,
          repair_loop_report: `${payload.workspace}/.agent/repair-loop-report.json`,
          ...(payload.direct_code?.artifacts || {}),
        },
        raw: payload,
      });
      setMessage(`已读取 workspace：${payload.name}`);
    }

    $("generateButton").addEventListener("click", async () => {
      setMessage("正在运行 agent generate，这一步会真实生成 workspace...");
      $("generateButton").disabled = true;
      try {
        const job = await startAndPollJob("generate", {
          request: $("promptInput").value,
          planner: $("plannerSelect").value,
          workspace_name: $("workspaceInput").value,
          audit: $("auditCheck").checked,
          build: $("buildCheck").checked,
          overwrite: $("overwriteCheck").checked,
        });
        const payload = job.result || {};
        renderPayload(payload);
        await loadWorkspaces();
        if (payload.workspace) {
          $("workspaceSelect").value = payload.workspace.split(/[\\\\/]/).pop();
        }
        setMessage(payload.success ? `生成完成：${payload.workspace}` : `生成失败：${payload.error}`, payload.success);
      } catch (error) {
        setMessage(`请求失败：${error.message}`, false);
      } finally {
        $("generateButton").disabled = false;
      }
    });

    $("refreshWorkspacesButton").addEventListener("click", async () => {
      try {
        const payload = await loadWorkspaces();
        setMessage(`已刷新 workspace：${payload.workspaces_count || 0} 个`);
      } catch (error) {
        setMessage(`刷新失败：${error.message}`, false);
      }
    });

    $("loadWorkspaceButton").addEventListener("click", async () => {
      try {
        await loadSelectedWorkspace();
      } catch (error) {
        setMessage(`读取失败：${error.message}`, false);
      }
    });

    $("modifyButton").addEventListener("click", async () => {
      const workspaceName = $("workspaceSelect").value || $("workspaceInput").value;
      if (!workspaceName) {
        setMessage("请先选择一个 workspace。", false);
        return;
      }
      setMessage("正在运行 agent modify，这一步会重生成受控文件...");
      $("modifyButton").disabled = true;
      try {
        const job = await startAndPollJob("modify", {
          workspace: workspaceName,
          change_request: $("modifyInput").value,
          planner: $("plannerSelect").value,
          audit: $("auditCheck").checked,
          build: $("buildCheck").checked,
        });
        const payload = job.result || {};
        renderPayload(payload);
        await loadWorkspaces();
        $("workspaceSelect").value = workspaceName;
        setMessage(payload.success ? `修改完成：${workspaceName}` : `修改失败：${payload.error}`, payload.success);
      } catch (error) {
        setMessage(`请求失败：${error.message}`, false);
      } finally {
        $("modifyButton").disabled = false;
      }
    });

    $("evalButton").addEventListener("click", async () => {
      setMessage("正在运行 eval smoke...");
      $("evalButton").disabled = true;
      try {
        const payload = await postJson("/api/eval", {
          planner: $("plannerSelect").value,
          limit: Number($("evalLimit").value || 3),
          audit: $("auditCheck").checked,
          build: $("buildCheck").checked,
        });
        renderPayload(payload);
        setMessage(payload.success ? "Eval 完成。" : `Eval 失败：${payload.error}`, payload.success);
      } catch (error) {
        setMessage(`请求失败：${error.message}`, false);
      } finally {
        $("evalButton").disabled = false;
      }
    });

    $("knowledgeRefreshButton").addEventListener("click", async () => {
      try {
        const payload = await loadKnowledge();
        setMessage(`知识库筛选完成：${payload.entries_count || 0}/${payload.total_entries || 0} 条`);
      } catch (error) {
        setMessage(`知识库读取失败：${error.message}`, false);
      }
    });

    for (const button of document.querySelectorAll(".tab")) {
      button.addEventListener("click", () => {
        for (const item of document.querySelectorAll(".tab")) item.classList.remove("active");
        for (const item of document.querySelectorAll(".view")) item.classList.remove("active");
        button.classList.add("active");
        $(button.dataset.view).classList.add("active");
      });
    }

    fetch("/api/health")
      .then((response) => response.json())
      .then(async (payload) => {
        await loadWorkspaces();
        await loadKnowledge();
        setMessage(`Project Console 已就绪：${payload.version}`);
      })
      .catch(() => setMessage("Project Console 后端未响应。", false));
  </script>
</body>
</html>
""".replace("__VERSION__", version)

    def _demo_generate_payload(
        self,
        payload: dict[str, Any],
        *,
        planner_selection: str,
        duration_seconds: float,
    ) -> dict[str, Any]:
        generation = payload.get("payload", {}).get("generation", {})
        audit = payload.get("payload", {}).get("audit", {})
        build = generation.get("build", {})
        modspec = generation.get("spec") or self._spec_from_steps(payload)
        generated_files = list(generation.get("generated_files", []))
        prompt_traces = payload.get("prompt_traces", [])
        workspace_path = Path(str(payload.get("workspace"))) if payload.get("workspace") else None
        repair_summary = self._repair_summary_from_agent_payload(payload, workspace=workspace_path)
        console = self._workspace_console_summary(workspace_path)
        return {
            "success": bool(payload.get("success")),
            "request": payload.get("request", ""),
            "planner_selection": planner_selection,
            "planner_mode": payload.get("planner_mode", ""),
            "llm_provider": payload.get("llm_provider", ""),
            "duration_seconds": duration_seconds,
            "workspace": payload.get("workspace"),
            "modspec": modspec,
            "generated_files": generated_files,
            "audit": audit,
            "build": build,
            "build_output": self._build_output_preview(build),
            "repair": repair_summary,
            "self_healing": repair_summary,
            "evidence": console["evidence"],
            "direct_code": console["direct_code"],
            "resource_preview": console["resource_preview"],
            "harvest_summary": console["harvest_summary"],
            "summary": {
                "features_count": len((modspec or {}).get("features", [])) if isinstance(modspec, dict) else 0,
                "generated_files_count": len(generated_files),
                "audit_success": audit.get("success"),
                "audit_errors_count": len(audit.get("errors", [])) if isinstance(audit, dict) else 0,
                "build_attempted": build.get("attempted"),
                "build_success": build.get("success"),
                "repair_needed": repair_summary.get("repair_needed"),
                "repair_executed": repair_summary.get("repair_executed"),
                "repair_success": repair_summary.get("repair_success"),
                "repair_rag_hits_count": repair_summary.get("repair_rag_hits_count", 0),
                "prompt_traces_count": len(prompt_traces),
                "decisions_count": len(payload.get("decisions", [])),
                "direct_code_used": console["direct_code"].get("used", False),
                "rollback_recommended": console["direct_code"].get("rollback_recommended", False),
            },
            "agent_trace": {
                "steps": payload.get("steps", []),
                "decisions": payload.get("decisions", []),
                "prompt_traces": prompt_traces,
                "roles_count": len(payload.get("steps", [])),
                "prompt_traces_count": len(prompt_traces),
                "agent_run_json_path": payload.get("agent_run_json_path"),
                "agent_decisions_md_path": payload.get("agent_decisions_md_path"),
                "prompt_trace_json_path": payload.get("prompt_trace_json_path"),
                "agent_trace_summary_json_path": payload.get("agent_trace_summary_json_path"),
            },
            "artifacts": {
                "agent_run_json_path": payload.get("agent_run_json_path"),
                "agent_run_md_path": payload.get("agent_run_md_path"),
                "agent_decisions_md_path": payload.get("agent_decisions_md_path"),
                "prompt_trace_json_path": payload.get("prompt_trace_json_path"),
                "agent_trace_summary_json_path": payload.get("agent_trace_summary_json_path"),
                "audit_report_path": audit.get("audit_report_path") if isinstance(audit, dict) else None,
                "agent_repair_plan_json_path": repair_summary.get("agent_repair_plan_json_path"),
                "agent_repair_plan_md_path": repair_summary.get("agent_repair_plan_md_path"),
                "repair_loop_report_json_path": repair_summary.get("repair_loop_report_json_path"),
                "repair_loop_report_md_path": repair_summary.get("repair_loop_report_md_path"),
                "repair_rag_context_json_path": repair_summary.get("repair_rag_report_json_path"),
                "repair_rag_context_md_path": repair_summary.get("repair_rag_report_md_path"),
                **console["direct_code"].get("artifacts", {}),
            },
            "raw": payload,
        }

    def _demo_modify_payload(
        self,
        payload: dict[str, Any],
        *,
        before_modspec: dict[str, Any],
        after_modspec: dict[str, Any],
        planner_selection: str,
        duration_seconds: float,
    ) -> dict[str, Any]:
        modify = payload.get("payload", {}).get("modify", {})
        audit = payload.get("payload", {}).get("audit", {})
        build = modify.get("build", {})
        workspace = Path(str(payload.get("workspace") or modify.get("workspace") or ""))
        generated_files = []
        if workspace.exists():
            summary = self._load_json(workspace / ".agent" / "generation-summary.json", default={})
            generated_files = list(summary.get("generated_files", [])) if isinstance(summary, dict) else []
        prompt_traces = payload.get("prompt_traces", [])
        diff = self._modspec_diff(before_modspec, after_modspec)
        workspace_path = workspace if workspace.exists() else None
        repair_summary = self._repair_summary_from_agent_payload(payload, workspace=workspace_path)
        console = self._workspace_console_summary(workspace_path)
        return {
            "success": bool(payload.get("success")),
            "mode": "modify",
            "request": payload.get("request", ""),
            "planner_selection": planner_selection,
            "planner_mode": payload.get("planner_mode", ""),
            "llm_provider": payload.get("llm_provider", ""),
            "duration_seconds": duration_seconds,
            "workspace": str(workspace) if workspace else payload.get("workspace"),
            "before_modspec": before_modspec,
            "modspec": after_modspec,
            "modspec_diff": diff,
            "generated_files": generated_files,
            "merge": {
                "added": list(modify.get("added", [])),
                "updated": list(modify.get("updated", [])),
                "skipped": list(modify.get("skipped", [])),
                "warnings": list(modify.get("warnings", [])),
            },
            "patch_agent": modify.get("patch_agent", {}),
            "audit": audit,
            "build": build,
            "build_output": self._build_output_preview(build),
            "repair": repair_summary,
            "self_healing": repair_summary,
            "evidence": console["evidence"],
            "direct_code": console["direct_code"],
            "resource_preview": console["resource_preview"],
            "harvest_summary": console["harvest_summary"],
            "summary": {
                "features_count": len((after_modspec or {}).get("features", [])) if isinstance(after_modspec, dict) else 0,
                "generated_files_count": len(generated_files),
                "added_count": len(modify.get("added", [])),
                "updated_count": len(modify.get("updated", [])),
                "skipped_count": len(modify.get("skipped", [])),
                "audit_success": audit.get("success") if isinstance(audit, dict) else None,
                "build_attempted": build.get("attempted") if isinstance(build, dict) else None,
                "build_success": build.get("success") if isinstance(build, dict) else None,
                "repair_needed": repair_summary.get("repair_needed"),
                "repair_executed": repair_summary.get("repair_executed"),
                "repair_success": repair_summary.get("repair_success"),
                "repair_rag_hits_count": repair_summary.get("repair_rag_hits_count", 0),
                "prompt_traces_count": len(prompt_traces),
                "decisions_count": len(payload.get("decisions", [])),
                "direct_code_used": console["direct_code"].get("used", False),
                "rollback_recommended": console["direct_code"].get("rollback_recommended", False),
            },
            "agent_trace": {
                "steps": payload.get("steps", []),
                "decisions": payload.get("decisions", []),
                "prompt_traces": prompt_traces,
                "roles_count": len(payload.get("steps", [])),
                "prompt_traces_count": len(prompt_traces),
                "agent_run_json_path": payload.get("agent_run_json_path"),
                "agent_decisions_md_path": payload.get("agent_decisions_md_path"),
                "prompt_trace_json_path": payload.get("prompt_trace_json_path"),
                "agent_trace_summary_json_path": payload.get("agent_trace_summary_json_path"),
            },
            "artifacts": {
                "agent_run_json_path": payload.get("agent_run_json_path"),
                "agent_run_md_path": payload.get("agent_run_md_path"),
                "agent_decisions_md_path": payload.get("agent_decisions_md_path"),
                "prompt_trace_json_path": payload.get("prompt_trace_json_path"),
                "agent_trace_summary_json_path": payload.get("agent_trace_summary_json_path"),
                "audit_report_path": audit.get("audit_report_path") if isinstance(audit, dict) else None,
                "modify_summary_path": modify.get("modify_summary_path"),
                "patch_agent_plan_json_path": modify.get("patch_agent", {}).get("plan_json_path"),
                "patch_agent_plan_md_path": modify.get("patch_agent", {}).get("plan_md_path"),
                "patch_agent_report_json_path": modify.get("patch_agent", {}).get("report_json_path"),
                "patch_agent_report_md_path": modify.get("patch_agent", {}).get("report_md_path"),
                "patch_agent_rollback_json_path": modify.get("patch_agent", {}).get("rollback_json_path"),
                "patch_agent_rollback_md_path": modify.get("patch_agent", {}).get("rollback_md_path"),
                "agent_repair_plan_json_path": repair_summary.get("agent_repair_plan_json_path"),
                "agent_repair_plan_md_path": repair_summary.get("agent_repair_plan_md_path"),
                "repair_loop_report_json_path": repair_summary.get("repair_loop_report_json_path"),
                "repair_loop_report_md_path": repair_summary.get("repair_loop_report_md_path"),
                "repair_rag_context_json_path": repair_summary.get("repair_rag_report_json_path"),
                "repair_rag_context_md_path": repair_summary.get("repair_rag_report_md_path"),
                **console["direct_code"].get("artifacts", {}),
            },
            "raw": payload,
        }

    def _workspace_console_summary(self, workspace: Path | None) -> dict[str, Any]:
        direct_code = self._direct_code_summary(workspace)
        resource_preview = self._resource_preview_summary(workspace)
        harvest_summary = self._harvest_summary()
        evidence = self._evidence_summary(
            workspace,
            direct_code=direct_code,
            resource_preview=resource_preview,
            harvest_summary=harvest_summary,
        )
        return {
            "evidence": evidence,
            "direct_code": direct_code,
            "resource_preview": resource_preview,
            "harvest_summary": harvest_summary,
        }

    def _direct_code_summary(self, workspace: Path | None) -> dict[str, Any]:
        if workspace is None or not workspace.exists():
            return {
                "used": False,
                "status": "not_used",
                "rollback_recommended": False,
                "artifacts": {},
                "snapshot_files": [],
                "summary": "No workspace is loaded.",
            }
        agent_dir = workspace / ".agent"
        artifacts = {
            "direct_code_plan_json_path": agent_dir / "direct-code-plan.json",
            "direct_code_plan_md_path": agent_dir / "direct-code-plan.md",
            "direct_code_review_json_path": agent_dir / "direct-code-review.json",
            "direct_code_diff_md_path": agent_dir / "direct-code-diff.md",
            "direct_code_report_json_path": agent_dir / "direct-code-report.json",
            "direct_code_rollback_json_path": agent_dir / "direct-code-rollback-report.json",
            "direct_code_snapshots_path": agent_dir / "direct-code-snapshots",
        }
        existing = {key: str(path) for key, path in artifacts.items() if path.exists()}
        used = bool(existing)
        plan = self._load_json(artifacts["direct_code_plan_json_path"], default={}) if artifacts["direct_code_plan_json_path"].exists() else {}
        review = self._load_json(artifacts["direct_code_review_json_path"], default={}) if artifacts["direct_code_review_json_path"].exists() else {}
        report = self._load_json(artifacts["direct_code_report_json_path"], default={}) if artifacts["direct_code_report_json_path"].exists() else {}
        rollback = self._load_json(artifacts["direct_code_rollback_json_path"], default={}) if artifacts["direct_code_rollback_json_path"].exists() else {}
        snapshot_root = artifacts["direct_code_snapshots_path"]
        snapshot_files = (
            sorted(str(path.relative_to(snapshot_root)) for path in snapshot_root.rglob("*") if path.is_file())
            if snapshot_root.exists()
            else []
        )
        rollback_recommended = bool(
            rollback.get("rollback_required")
            or rollback.get("status") == "recommended"
            or report.get("success") is False
        )
        return {
            "used": used,
            "status": "used" if used else "not_used",
            "summary": plan.get("summary") or ("Direct Code Lane artifacts found." if used else "Direct Code Lane was not used for this workspace."),
            "changes_count": len(plan.get("changes", [])) if isinstance(plan, dict) else 0,
            "review_approved": review.get("approved") if isinstance(review, dict) and review else None,
            "review_errors_count": len(review.get("errors", [])) if isinstance(review, dict) else 0,
            "changed_files": list(report.get("changed_files", [])) if isinstance(report, dict) else [],
            "snapshot_files": snapshot_files,
            "snapshot_files_count": len(snapshot_files),
            "rollback_status": rollback.get("status") if isinstance(rollback, dict) and rollback else "not_used",
            "rollback_recommended": rollback_recommended,
            "rollback_reason": rollback.get("reason") if isinstance(rollback, dict) else "",
            "artifacts": existing,
            "plan": plan,
            "review": review,
            "report": report,
            "rollback": rollback,
        }

    def _resource_preview_summary(self, workspace: Path | None) -> dict[str, Any]:
        if workspace is None or not workspace.exists():
            return {"available": False, "summary": "No workspace is loaded.", "artifacts": {}}
        agent_dir = workspace / ".agent"
        report_json = agent_dir / "resource-quality-report.json"
        report_md = agent_dir / "resource-quality-report.md"
        atlas = agent_dir / "texture-atlas.png"
        previews_dir = agent_dir / "previews"
        report = self._load_json(report_json, default={}) if report_json.exists() else {}
        previews = sorted(str(path.relative_to(workspace)) for path in previews_dir.glob("*.png")) if previews_dir.exists() else []
        artifacts = {
            key: str(path)
            for key, path in {
                "resource_quality_report_json_path": report_json,
                "resource_quality_report_md_path": report_md,
                "texture_atlas_path": atlas,
                "structure_previews_path": previews_dir,
            }.items()
            if path.exists()
        }
        summary = report.get("summary", {}) if isinstance(report, dict) else {}
        return {
            "available": bool(report or atlas.exists() or previews),
            "summary": summary or "No resource quality report found.",
            "textures": summary.get("textures", 0) if isinstance(summary, dict) else 0,
            "model_variants": summary.get("model_variants", 0) if isinstance(summary, dict) else 0,
            "structure_previews": previews,
            "structure_previews_count": len(previews),
            "atlas_available": atlas.exists(),
            "artifacts": artifacts,
            "report": report,
        }

    def _harvest_summary(self, *, limit: int = 8) -> dict[str, Any]:
        lab_root = self.config.workspace_root / "free-code-lab-runs"
        harvest_root = self.config.workspace_root / "harvest-runs"
        candidates: list[dict[str, Any]] = []
        if lab_root.exists():
            for candidate_path in sorted(lab_root.glob("*/.agent/harvest-candidate.json")):
                payload = self._load_json(candidate_path, default={})
                if isinstance(payload, dict):
                    payload = dict(payload)
                    payload["candidate_path"] = str(candidate_path)
                    candidates.append(payload)
        harvest_reports: list[dict[str, Any]] = []
        if harvest_root.exists():
            for report_path in sorted(harvest_root.glob("*/.agent/harvest-report.json")):
                payload = self._load_json(report_path, default={})
                harvest_reports.append(
                    {
                        "run_id": payload.get("run_id", report_path.parents[1].name) if isinstance(payload, dict) else report_path.parents[1].name,
                        "report_json_path": str(report_path),
                        "report_md_path": str(report_path.with_suffix(".md")),
                    }
                )
        return {
            "available": bool(candidates or harvest_reports),
            "lab_runs_count": len(list(lab_root.iterdir())) if lab_root.exists() else 0,
            "candidates_count": len(candidates),
            "ready_to_harvest_count": sum(1 for item in candidates if item.get("ready_to_harvest")),
            "harvest_reports_count": len(harvest_reports),
            "latest_candidates": candidates[-limit:],
            "latest_harvest_reports": harvest_reports[-limit:],
            "lab_root": str(lab_root),
            "harvest_root": str(harvest_root),
        }

    def _evidence_summary(
        self,
        workspace: Path | None,
        *,
        direct_code: dict[str, Any],
        resource_preview: dict[str, Any],
        harvest_summary: dict[str, Any],
    ) -> dict[str, Any]:
        if workspace is None or not workspace.exists():
            return {"available": False, "workspace": None, "artifacts": {}, "summary": "No workspace is loaded."}
        agent_dir = workspace / ".agent"
        base_artifacts = {
            "modspec_json_path": agent_dir / "modspec.json",
            "generation_summary_json_path": agent_dir / "generation-summary.json",
            "audit_report_json_path": agent_dir / "audit-report.json",
            "audit_report_md_path": agent_dir / "audit-report.md",
            "agent_run_json_path": agent_dir / "agent-run.json",
            "agent_run_md_path": agent_dir / "agent-run.md",
            "agent_trace_summary_json_path": agent_dir / "agent-trace-summary.json",
            "prompt_trace_json_path": agent_dir / "prompt-trace.json",
            "agent_decisions_md_path": agent_dir / "agent-decisions.md",
            "repair_plan_json_path": agent_dir / "agent-repair-plan.json",
            "repair_loop_report_json_path": agent_dir / "repair-loop-report.json",
        }
        artifacts = {key: str(path) for key, path in base_artifacts.items() if path.exists()}
        artifacts.update(direct_code.get("artifacts", {}))
        artifacts.update(resource_preview.get("artifacts", {}))
        return {
            "available": bool(artifacts),
            "workspace": str(workspace),
            "artifacts": artifacts,
            "artifacts_count": len(artifacts),
            "direct_code_used": direct_code.get("used", False),
            "rollback_recommended": direct_code.get("rollback_recommended", False),
            "resource_preview_available": resource_preview.get("available", False),
            "harvest_candidates_count": harvest_summary.get("candidates_count", 0),
        }

    def _spec_from_steps(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        for step in payload.get("steps", []):
            details = step.get("details") or {}
            spec = details.get("spec")
            if isinstance(spec, dict):
                return spec
        return None

    def _workspace_summary(self, workspace: Path) -> dict[str, Any]:
        modspec_path = workspace / ".agent" / "modspec.json"
        summary_path = workspace / ".agent" / "generation-summary.json"
        audit_path = workspace / ".agent" / "audit-report.json"
        repair_path = workspace / ".agent" / "agent-repair-plan.json"
        modspec = self._load_json(modspec_path, default={})
        generated_files = self._load_json(summary_path, default={}).get("generated_files", []) if summary_path.exists() else []
        audit = self._load_json(audit_path, default={}) if audit_path.exists() else {}
        repair = self._load_json(repair_path, default={}) if repair_path.exists() else {}
        modified_at = datetime.fromtimestamp(modspec_path.stat().st_mtime).isoformat(timespec="seconds") if modspec_path.exists() else ""
        return {
            "name": workspace.name,
            "path": str(workspace),
            "mod_id": modspec.get("mod_id", ""),
            "display_name": modspec.get("display_name") or modspec.get("mod_name", ""),
            "features_count": len(modspec.get("features", [])) if isinstance(modspec, dict) else 0,
            "generated_files_count": len(generated_files) if isinstance(generated_files, list) else 0,
            "audit_success": audit.get("success") if isinstance(audit, dict) and audit else None,
            "repair_needed": repair.get("repair_needed") if isinstance(repair, dict) and repair else None,
            "repair_executed": repair.get("repair_executed") if isinstance(repair, dict) and repair else None,
            "repair_success": repair.get("repair_success") if isinstance(repair, dict) and repair else None,
            "repair_rag_hits_count": int((repair.get("repair_rag") or {}).get("hits_count", 0) or 0) if isinstance(repair, dict) and repair else 0,
            "modified_at": modified_at,
        }

    def _resolve_workspace(self, value: str) -> Path:
        candidate = resolve_workspace_child(self.config.workspace_root, value)
        if not candidate.exists():
            raise FileNotFoundError(f"Workspace not found: {candidate}")
        if not (candidate / ".agent" / "modspec.json").exists():
            raise FileNotFoundError(f"Workspace is missing .agent/modspec.json: {candidate}")
        return candidate

    def _load_json(self, path: Path, *, default: Any | None = None) -> Any:
        if not path.exists():
            if default is not None:
                return default
            raise FileNotFoundError(f"JSON file not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _modspec_diff(self, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        before_features = {self._feature_key(feature): feature for feature in self._feature_list(before)}
        after_features = {self._feature_key(feature): feature for feature in self._feature_list(after)}
        added = sorted(key for key in after_features if key not in before_features)
        removed = sorted(key for key in before_features if key not in after_features)
        updated = sorted(
            key
            for key in before_features.keys() & after_features.keys()
            if before_features[key] != after_features[key]
        )
        top_level_fields = ["mod_id", "mod_name", "display_name", "package", "package_name", "version", "description"]
        top_level_changed = [
            {
                "field": field,
                "before": before.get(field),
                "after": after.get(field),
            }
            for field in top_level_fields
            if before.get(field) != after.get(field)
        ]
        return {
            "added": added,
            "updated": updated,
            "removed": removed,
            "top_level_changed": top_level_changed,
            "added_count": len(added),
            "updated_count": len(updated),
            "removed_count": len(removed),
        }

    def _feature_list(self, modspec: dict[str, Any]) -> list[dict[str, Any]]:
        features = modspec.get("features")
        if isinstance(features, list):
            return [feature for feature in features if isinstance(feature, dict)]
        result: list[dict[str, Any]] = []
        for key, feature_type in (
            ("items", "item"),
            ("blocks", "block"),
            ("ores", "ore"),
            ("foods", "food"),
            ("swords", "sword"),
            ("tools", "tool"),
            ("armors", "armor"),
            ("recipes", "recipe"),
        ):
            for entry in modspec.get(key, []) if isinstance(modspec.get(key), list) else []:
                if isinstance(entry, dict):
                    copied = dict(entry)
                    copied.setdefault("type", feature_type)
                    result.append(copied)
        return result

    def _feature_key(self, feature: dict[str, Any]) -> str:
        feature_type = str(feature.get("type", "feature"))
        identifier = str(feature.get("id", feature.get("identifier", "unknown")))
        return f"{feature_type}:{identifier}"

    def _planner_selection(self, selection: str) -> tuple[str, str]:
        normalized = selection.strip().lower().replace("_", "-")
        mapping = {
            "rules": ("rules", "mock"),
            "mock-llm": ("llm", "mock"),
            "mock": ("llm", "mock"),
            "real-llm": ("llm", "openai-compatible"),
            "real": ("llm", "openai-compatible"),
            "openai-compatible": ("llm", "openai-compatible"),
            "auto-mock": ("auto", "mock"),
            "auto-real": ("auto", "openai-compatible"),
            "auto": ("auto", "mock"),
        }
        if normalized not in mapping:
            raise ValueError(f"Unsupported planner selection: {selection}")
        return mapping[normalized]

    def _workspace_name_from_request(self, request: str) -> str:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = slugify_mod_id(request, fallback="web_demo")
        return f"v35-web-demo-{slug[:28]}-{stamp}"

    def _project_version(self) -> str:
        pyproject_path = self.config.project_root / "pyproject.toml"
        if not pyproject_path.exists():
            return "unknown"
        text = pyproject_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("version ="):
                return line.split("=", 1)[1].strip().strip('"')
        return "unknown"


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


class WebDemoServer:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()
        self.runner = WebDemoRunner(self.config)

    def serve(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        open_browser: bool = False,
    ) -> WebDemoServerResult:
        runner = self.runner

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
                parsed = urlparse(self.path)
                if parsed.path in {"/", "/index.html"}:
                    _send_html(self, runner.render_index_html())
                    return
                if parsed.path == "/api/health":
                    _send_json(self, runner.health())
                    return
                if parsed.path == "/api/workspaces":
                    _send_json(self, runner.list_workspaces())
                    return
                if parsed.path == "/api/workspace":
                    query = parse_qs(parsed.query)
                    name = (query.get("name") or [""])[0]
                    payload = runner.get_workspace(name)
                    _send_json(self, payload, status=200 if payload.get("success") else 404)
                    return
                if parsed.path == "/api/job":
                    query = parse_qs(parsed.query)
                    job_id = (query.get("id") or [""])[0]
                    payload = runner.get_job(job_id)
                    _send_json(self, payload, status=200 if payload.get("success") else 404)
                    return
                if parsed.path == "/api/knowledge":
                    query = parse_qs(parsed.query)
                    payload = runner.list_knowledge_entries(
                        query=(query.get("query") or [""])[0],
                        category=(query.get("category") or [""])[0],
                        capability=(query.get("capability") or [""])[0],
                        tag=(query.get("tag") or [""])[0],
                        limit=int((query.get("limit") or ["50"])[0]),
                    )
                    _send_json(self, payload)
                    return
                _send_json(self, {"success": False, "error": "Not found."}, status=404)

            def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
                parsed = urlparse(self.path)
                try:
                    body = _read_json(self)
                    if parsed.path == "/api/generate":
                        payload = runner.run_generate(
                            str(body.get("request", "")),
                            planner_selection=str(body.get("planner", "mock-llm")),
                            workspace_name=str(body.get("workspace_name", "")).strip() or None,
                            overwrite=bool(body.get("overwrite", True)),
                            run_build=bool(body.get("build", False)),
                            run_audit=bool(body.get("audit", True)),
                        )
                        _send_json(self, payload, status=200 if payload.get("success") else 400)
                        return
                    if parsed.path == "/api/jobs/generate":
                        payload = runner.start_generate_job(
                            str(body.get("request", "")),
                            planner_selection=str(body.get("planner", "mock-llm")),
                            workspace_name=str(body.get("workspace_name", "")).strip() or None,
                            overwrite=bool(body.get("overwrite", True)),
                            run_build=bool(body.get("build", False)),
                            run_audit=bool(body.get("audit", True)),
                        )
                        _send_json(self, payload, status=202 if payload.get("success") else 400)
                        return
                    if parsed.path == "/api/eval":
                        payload = runner.run_eval(
                            planner_selection=str(body.get("planner", "mock-llm")),
                            limit=int(body.get("limit", 3)),
                            run_build=bool(body.get("build", False)),
                            run_audit=bool(body.get("audit", True)),
                        )
                        _send_json(self, payload, status=200 if payload.get("success") else 400)
                        return
                    if parsed.path == "/api/modify":
                        payload = runner.run_modify(
                            str(body.get("workspace", "")),
                            str(body.get("change_request", "")),
                            planner_selection=str(body.get("planner", "mock-llm")),
                            run_build=bool(body.get("build", False)),
                            run_audit=bool(body.get("audit", True)),
                        )
                        _send_json(self, payload, status=200 if payload.get("success") else 400)
                        return
                    if parsed.path == "/api/jobs/modify":
                        payload = runner.start_modify_job(
                            str(body.get("workspace", "")),
                            str(body.get("change_request", "")),
                            planner_selection=str(body.get("planner", "mock-llm")),
                            run_build=bool(body.get("build", False)),
                            run_audit=bool(body.get("audit", True)),
                        )
                        _send_json(self, payload, status=202 if payload.get("success") else 400)
                        return
                    _send_json(self, {"success": False, "error": "Not found."}, status=404)
                except Exception as exc:
                    _send_json(
                        self,
                        {
                            "success": False,
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                        },
                        status=500,
                    )

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - inherited name.
                return

        server = ThreadingHTTPServer((host, port), Handler)
        actual_host, actual_port = server.server_address
        url = f"http://{actual_host}:{actual_port}/"
        result = WebDemoServerResult(
            success=True,
            host=str(actual_host),
            port=int(actual_port),
            url=url,
            message="Web Demo server is running. Press Ctrl+C to stop.",
        )
        if open_browser:
            webbrowser.open(url)
        print(f"Web Demo Dashboard: {url}")
        print("Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return result


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    raw = handler.rfile.read(length) if length else b"{}"
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object.")
    return data


def _send_json(handler: BaseHTTPRequestHandler, payload: dict[str, Any], *, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _send_html(handler: BaseHTTPRequestHandler, html: str, *, status: int = 200) -> None:
    body = html.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .config import AppConfig
from .models import ModSpec, ValidationReport
from .schema import get_modspec_schema
from .validator import validate_mod_spec


@runtime_checkable
class DomainSpec(Protocol):
    """Structured intent for one generation domain."""

    @property
    def domain_id(self) -> str:
        ...

    @property
    def domain_spec_type(self) -> str:
        ...

    def to_dict(self) -> dict[str, Any]:
        ...


@dataclass(slots=True)
class DomainSpecMetadata:
    domain_id: str
    spec_type: str
    display_name: str
    status: str
    summary: str
    artifact_name: str
    schema_name: str
    input_kinds: list[str] = field(default_factory=list)
    output_kinds: list[str] = field(default_factory=list)
    runtime_stages: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "spec_type": self.spec_type,
            "display_name": self.display_name,
            "status": self.status,
            "summary": self.summary,
            "artifact_name": self.artifact_name,
            "schema_name": self.schema_name,
            "input_kinds": list(self.input_kinds),
            "output_kinds": list(self.output_kinds),
            "runtime_stages": list(self.runtime_stages),
            "notes": list(self.notes),
        }


class DomainSpecPlugin(Protocol):
    metadata: DomainSpecMetadata

    def can_load(self, data: dict[str, Any]) -> bool:
        ...

    def load(self, data: dict[str, Any]) -> DomainSpec:
        ...

    def dump(self, spec: DomainSpec) -> dict[str, Any]:
        ...

    def json_schema(self) -> dict[str, Any]:
        ...

    def validate(self, spec: DomainSpec, config: AppConfig) -> ValidationReport:
        ...

    def describe(self, spec: DomainSpec) -> dict[str, Any]:
        ...


class NeoForgeModSpecPlugin:
    metadata = DomainSpecMetadata(
        domain_id="minecraft.neoforge",
        spec_type="ModSpec",
        display_name="Minecraft NeoForge ModSpec",
        status="stable",
        summary="DomainSpec implementation for NeoForge 26.1 mod generation: items, blocks, resources, worldgen, audit, build, repair, eval, benchmark, and replay.",
        artifact_name=".agent/modspec.json",
        schema_name="NeoForgeAgentModSpec",
        input_kinds=["natural_language", "json_modspec", "llm_planner_output"],
        output_kinds=["neoforge_workspace", "java", "resource_json", "png_textures", "agent_reports"],
        runtime_stages=["planner", "reviewer", "executor", "auditor", "repair", "trace"],
        notes=[
            "LLM output is constrained to ModSpec, patch, or repair intent.",
            "Deterministic NeoForge generators materialize final Java, JSON, PNG, and report artifacts.",
        ],
    )

    def can_load(self, data: dict[str, Any]) -> bool:
        payload = _unwrap_domain_payload(data)
        domain_id = str(payload.get("domain", payload.get("domain_id", "")))
        spec_type = str(payload.get("domain_spec_type", payload.get("spec_type", "")))
        if domain_id in {self.metadata.domain_id, "neoforge", "minecraft.modspec"}:
            return True
        if spec_type.lower() == self.metadata.spec_type.lower():
            return True
        if str(payload.get("loader", "neoforge")) != "neoforge":
            return False
        return "mod_id" in payload and (
            "features" in payload
            or any(
                key in payload
                for key in (
                    "items",
                    "blocks",
                    "machines",
                    "entities",
                    "ores",
                    "recipes",
                    "world_features",
                    "progressions",
                    "quests",
                )
            )
        )

    def load(self, data: dict[str, Any]) -> ModSpec:
        payload = _unwrap_domain_payload(data)
        return ModSpec.from_dict(payload)

    def dump(self, spec: DomainSpec) -> dict[str, Any]:
        if not isinstance(spec, ModSpec):
            raise TypeError(f"{self.metadata.domain_id} plugin can only dump ModSpec instances.")
        return spec.to_dict()

    def json_schema(self) -> dict[str, Any]:
        return get_modspec_schema()

    def validate(self, spec: DomainSpec, config: AppConfig) -> ValidationReport:
        if not isinstance(spec, ModSpec):
            raise TypeError(f"{self.metadata.domain_id} plugin can only validate ModSpec instances.")
        return validate_mod_spec(spec, config)

    def describe(self, spec: DomainSpec) -> dict[str, Any]:
        if not isinstance(spec, ModSpec):
            raise TypeError(f"{self.metadata.domain_id} plugin can only describe ModSpec instances.")
        feature_counts: dict[str, int] = {}
        for feature in spec.iter_features():
            feature_type = str(getattr(feature, "feature_type", type(feature).__name__))
            feature_counts[feature_type] = feature_counts.get(feature_type, 0) + 1
        return {
            "domain_id": self.metadata.domain_id,
            "spec_type": self.metadata.spec_type,
            "mod_id": spec.mod_id,
            "display_name": spec.display_name,
            "package_name": spec.package_name,
            "feature_count": sum(feature_counts.values()),
            "feature_counts": feature_counts,
        }


@dataclass(slots=True)
class PlannedDomainSpecPlugin:
    metadata: DomainSpecMetadata

    def can_load(self, data: dict[str, Any]) -> bool:
        payload = _unwrap_domain_payload(data)
        return str(payload.get("domain", payload.get("domain_id", ""))) == self.metadata.domain_id

    def load(self, data: dict[str, Any]) -> DomainSpec:
        raise NotImplementedError(f"{self.metadata.domain_id} is registered as a planned DomainSpec plugin.")

    def dump(self, spec: DomainSpec) -> dict[str, Any]:
        raise NotImplementedError(f"{self.metadata.domain_id} is registered as a planned DomainSpec plugin.")

    def json_schema(self) -> dict[str, Any]:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": self.metadata.schema_name,
            "type": "object",
            "properties": {
                "domain": {"const": self.metadata.domain_id},
                "domain_spec_type": {"const": self.metadata.spec_type},
            },
            "additionalProperties": True,
        }

    def validate(self, spec: DomainSpec, config: AppConfig) -> ValidationReport:
        raise NotImplementedError(f"{self.metadata.domain_id} is registered as a planned DomainSpec plugin.")

    def describe(self, spec: DomainSpec) -> dict[str, Any]:
        raise NotImplementedError(f"{self.metadata.domain_id} is registered as a planned DomainSpec plugin.")


class DomainSpecRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, DomainSpecPlugin] = {}

    @classmethod
    def default(cls) -> "DomainSpecRegistry":
        registry = cls()
        registry.register(NeoForgeModSpecPlugin())
        registry.register(
            PlannedDomainSpecPlugin(
                DomainSpecMetadata(
                    domain_id="spring.api",
                    spec_type="SpringApiSpec",
                    display_name="Spring API Spec",
                    status="planned",
                    summary="Future domain spec for Spring Boot API projects: endpoints, DTOs, services, validation, tests, and OpenAPI evidence.",
                    artifact_name=".agent/domain-spec.json",
                    schema_name="SpringApiSpec",
                    input_kinds=["natural_language", "json_spring_api_spec"],
                    output_kinds=["spring_boot_project", "java", "tests", "openapi"],
                    runtime_stages=["planner", "reviewer", "executor", "auditor", "repair", "trace"],
                    notes=["Registered to document the plugin boundary; generation is not implemented in this repository yet."],
                )
            )
        )
        registry.register(
            PlannedDomainSpecPlugin(
                DomainSpecMetadata(
                    domain_id="unity.component",
                    spec_type="UnityComponentSpec",
                    display_name="Unity Component Spec",
                    status="planned",
                    summary="Future domain spec for Unity components: MonoBehaviour fields, lifecycle hooks, prefabs, scenes, tests, and gameplay evidence.",
                    artifact_name=".agent/domain-spec.json",
                    schema_name="UnityComponentSpec",
                    input_kinds=["natural_language", "json_unity_component_spec"],
                    output_kinds=["unity_scripts", "prefab_metadata", "test_reports"],
                    runtime_stages=["planner", "reviewer", "executor", "auditor", "repair", "trace"],
                    notes=["Registered to document the plugin boundary; generation is not implemented in this repository yet."],
                )
            )
        )
        return registry

    def register(self, plugin: DomainSpecPlugin) -> None:
        self._plugins[plugin.metadata.domain_id] = plugin

    def get(self, domain_id: str) -> DomainSpecPlugin:
        try:
            return self._plugins[domain_id]
        except KeyError as exc:
            known = ", ".join(sorted(self._plugins))
            raise KeyError(f"Unknown domain spec '{domain_id}'. Known domains: {known}") from exc

    def list_metadata(self, *, status: str | None = None) -> list[DomainSpecMetadata]:
        items = [plugin.metadata for plugin in self._plugins.values()]
        if status:
            items = [metadata for metadata in items if metadata.status == status]
        return sorted(items, key=lambda metadata: (metadata.status != "stable", metadata.domain_id))

    def detect(self, data: dict[str, Any]) -> DomainSpecPlugin:
        payload = _unwrap_domain_payload(data)
        domain_id = str(payload.get("domain", payload.get("domain_id", "")))
        if domain_id and domain_id in self._plugins:
            return self.get(domain_id)
        for plugin in self._plugins.values():
            if plugin.can_load(payload):
                return plugin
        known = ", ".join(sorted(self._plugins))
        raise ValueError(f"Could not detect DomainSpec plugin. Known domains: {known}")

    def load(self, data: dict[str, Any], *, domain_id: str | None = None) -> DomainSpec:
        plugin = self.get(domain_id) if domain_id else self.detect(data)
        return plugin.load(data)

    def to_dict(self) -> dict[str, Any]:
        domains = [metadata.to_dict() for metadata in self.list_metadata()]
        return {
            "domains": domains,
            "domains_count": len(domains),
            "stable_count": sum(1 for domain in domains if domain["status"] == "stable"),
            "planned_count": sum(1 for domain in domains if domain["status"] == "planned"),
        }


def _unwrap_domain_payload(data: dict[str, Any]) -> dict[str, Any]:
    spec = data.get("spec")
    if isinstance(spec, dict) and ("domain" in data or "domain_id" in data):
        merged = dict(spec)
        if "domain" not in merged and "domain" in data:
            merged["domain"] = data["domain"]
        if "domain_id" not in merged and "domain_id" in data:
            merged["domain_id"] = data["domain_id"]
        if "domain_spec_type" not in merged and "domain_spec_type" in data:
            merged["domain_spec_type"] = data["domain_spec_type"]
        if "spec_type" not in merged and "spec_type" in data:
            merged["spec_type"] = data["spec_type"]
        return merged
    return data

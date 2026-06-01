from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .auditor import WorkspaceAuditor
from .config import AppConfig
from .planner import ModProjectPlanner
from .tools import ensure_directory, write_json, write_text


@dataclass(slots=True)
class GoldenJsonExpectation:
    path: str
    fields: dict[str, Any] = field(default_factory=dict)
    contains: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "fields": dict(self.fields),
            "contains": list(self.contains),
        }


@dataclass(slots=True)
class GoldenCase:
    identifier: str
    request: str
    expected_features: list[str]
    expected_paths: list[str]
    json_expectations: list[GoldenJsonExpectation] = field(default_factory=list)
    min_generated_files: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "request": self.request,
            "expected_features": list(self.expected_features),
            "expected_paths": list(self.expected_paths),
            "json_expectations": [expectation.to_dict() for expectation in self.json_expectations],
            "min_generated_files": self.min_generated_files,
        }


@dataclass(slots=True)
class GoldenCheck:
    id: str
    status: str
    message: str = ""
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "message": self.message,
            "path": self.path,
        }


@dataclass(slots=True)
class GoldenCaseResult:
    identifier: str
    request: str
    success: bool
    workspace: str | None = None
    generated_files_count: int = 0
    feature_ids: list[str] = field(default_factory=list)
    checks: list[GoldenCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    audit_success: bool | None = None
    audit_report_path: str | None = None
    snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "request": self.request,
            "success": self.success,
            "workspace": self.workspace,
            "generated_files_count": self.generated_files_count,
            "feature_ids": list(self.feature_ids),
            "checks": [check.to_dict() for check in self.checks],
            "errors": list(self.errors),
            "audit_success": self.audit_success,
            "audit_report_path": self.audit_report_path,
            "snapshot": dict(self.snapshot),
        }


@dataclass(slots=True)
class GoldenTestResult:
    success: bool
    run_id: str
    report_dir: Path
    cases: list[GoldenCaseResult]
    golden_report_json_path: Path
    golden_report_md_path: Path

    def to_dict(self) -> dict[str, Any]:
        passed = sum(1 for case in self.cases if case.success)
        failed = len(self.cases) - passed
        checks_count = sum(len(case.checks) for case in self.cases)
        return {
            "success": self.success,
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "cases": [case.to_dict() for case in self.cases],
            "cases_count": len(self.cases),
            "passed_count": passed,
            "failed_count": failed,
            "checks_count": checks_count,
            "golden_report_json_path": str(self.golden_report_json_path),
            "golden_report_md_path": str(self.golden_report_md_path),
        }


class GoldenTestRunner:
    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def run(
        self,
        *,
        run_name: str | None = None,
        limit: int | None = None,
    ) -> GoldenTestResult:
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = ensure_directory(self.config.workspace_root / "golden-runs" / run_id)
        report_dir = ensure_directory(run_dir / ".agent")
        workspace_root = ensure_directory(run_dir / "workspaces")
        scoped_config = replace(self.config, workspace_root=workspace_root)

        cases = default_golden_cases()
        if limit is not None:
            cases = cases[: max(0, limit)]

        results: list[GoldenCaseResult] = []
        planner = ModProjectPlanner(scoped_config)
        auditor = WorkspaceAuditor(scoped_config)
        for index, case in enumerate(cases, start=1):
            workspace_name = f"{index:02d}-{case.identifier}"
            results.append(
                self._run_case(
                    case,
                    planner=planner,
                    auditor=auditor,
                    workspace_name=workspace_name,
                )
            )

        success = all(case.success for case in results)
        report_json = report_dir / "golden-report.json"
        report_md = report_dir / "golden-report.md"
        result = GoldenTestResult(
            success=success,
            run_id=run_id,
            report_dir=report_dir,
            cases=results,
            golden_report_json_path=report_json,
            golden_report_md_path=report_md,
        )
        write_json(report_dir / "golden-cases.json", [case.to_dict() for case in cases])
        write_json(report_json, result.to_dict())
        write_text(report_md, self._render_report_md(result))
        return result

    def _run_case(
        self,
        case: GoldenCase,
        *,
        planner: ModProjectPlanner,
        auditor: WorkspaceAuditor,
        workspace_name: str,
    ) -> GoldenCaseResult:
        checks: list[GoldenCheck] = []
        errors: list[str] = []
        try:
            generation = planner.execute(
                case.request,
                workspace_name=workspace_name,
                overwrite=True,
                run_build=False,
            )
        except Exception as exc:
            return GoldenCaseResult(
                identifier=case.identifier,
                request=case.request,
                success=False,
                checks=[GoldenCheck("generation:exception", "fail", f"{type(exc).__name__}: {exc}")],
                errors=[f"{type(exc).__name__}: {exc}"],
            )

        workspace = generation.workspace_dir
        modspec_path = workspace / ".agent" / "modspec.json"
        summary_path = workspace / ".agent" / "generation-summary.json"
        modspec = _read_json(modspec_path)
        summary = _read_json(summary_path)
        feature_ids = sorted(_feature_ids(modspec))
        generated_files = [str(item) for item in summary.get("generated_files", [])] if isinstance(summary, dict) else []
        generated_files_set = {_normalize_relative_path(item) for item in generated_files}

        self._check(checks, "generation:success", generation.succeeded, str(workspace), "Generation failed.")
        self._check(
            checks,
            "generated_files:min_count",
            len(generated_files) >= case.min_generated_files,
            str(summary_path),
            f"Expected at least {case.min_generated_files} generated files, got {len(generated_files)}.",
        )

        for expected_feature in case.expected_features:
            self._check(
                checks,
                f"feature:{expected_feature}",
                expected_feature in feature_ids,
                str(modspec_path),
                f"Missing expected feature '{expected_feature}'.",
            )

        for relative in case.expected_paths:
            normalized = _normalize_relative_path(relative)
            path = workspace / relative
            exists = path.exists()
            self._check(checks, f"path:{normalized}", exists, str(path), "Expected generated path is missing.")
            self._check(
                checks,
                f"summary:{normalized}",
                normalized in generated_files_set,
                str(summary_path),
                "Expected path is not recorded in generation-summary.json.",
            )

        for expectation in case.json_expectations:
            self._check_json_expectation(checks, workspace, expectation)

        audit_success: bool | None = None
        audit_report_path: str | None = None
        try:
            audit = auditor.audit_workspace(workspace)
            audit_success = audit.success
            audit_report_path = audit.audit_report_path
            self._check(checks, "audit:success", audit.success, audit.audit_report_path, "Workspace audit failed.")
            if audit.errors:
                errors.extend(f"{issue.id}: {issue.message}" for issue in audit.errors)
        except Exception as exc:
            audit_success = False
            self._check(checks, "audit:exception", False, str(workspace), f"{type(exc).__name__}: {exc}")
            errors.append(f"{type(exc).__name__}: {exc}")

        errors.extend(check.message for check in checks if check.status == "fail" and check.message)
        snapshot = {
            "feature_ids": feature_ids,
            "generated_files_count": len(generated_files),
            "expected_paths": list(case.expected_paths),
            "json_expectations": [expectation.to_dict() for expectation in case.json_expectations],
            "generated_files_sample": sorted(generated_files)[:20],
        }
        return GoldenCaseResult(
            identifier=case.identifier,
            request=case.request,
            success=not errors,
            workspace=str(workspace),
            generated_files_count=len(generated_files),
            feature_ids=feature_ids,
            checks=checks,
            errors=errors,
            audit_success=audit_success,
            audit_report_path=audit_report_path,
            snapshot=snapshot,
        )

    def _check_json_expectation(
        self,
        checks: list[GoldenCheck],
        workspace: Path,
        expectation: GoldenJsonExpectation,
    ) -> None:
        path = workspace / expectation.path
        if not path.exists():
            self._check(checks, f"json:{expectation.path}:exists", False, str(path), "Expected JSON file is missing.")
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._check(checks, f"json:{expectation.path}:parse", False, str(path), f"Invalid JSON: {exc}")
            return
        self._check(checks, f"json:{expectation.path}:parse", True, str(path), "JSON parsed.")

        raw_text = path.read_text(encoding="utf-8")
        for needle in expectation.contains:
            self._check(
                checks,
                f"json:{expectation.path}:contains:{needle}",
                needle in raw_text,
                str(path),
                f"JSON text does not contain '{needle}'.",
            )

        for field_path, expected in expectation.fields.items():
            actual = _json_select(data, field_path)
            ok = _json_matches(actual, expected)
            self._check(
                checks,
                f"json:{expectation.path}:field:{field_path}",
                ok,
                str(path),
                f"Expected field '{field_path}' to be {expected!r}, got {actual!r}.",
            )

    def _check(
        self,
        checks: list[GoldenCheck],
        check_id: str,
        ok: bool,
        path: str | None,
        message: str,
    ) -> None:
        checks.append(GoldenCheck(id=check_id, status="pass" if ok else "fail", message="" if ok else message, path=path))

    def _render_report_md(self, result: GoldenTestResult) -> str:
        payload = result.to_dict()
        lines = [
            "# Golden Test Report",
            "",
            f"Success: {str(result.success).lower()}",
            f"Run ID: `{result.run_id}`",
            f"Passed: {payload['passed_count']}",
            f"Failed: {payload['failed_count']}",
            f"Checks: {payload['checks_count']}",
            "",
            "## Cases",
            "",
        ]
        for case in result.cases:
            lines.append(f"- `{case.identifier}`: {'pass' if case.success else 'fail'}")
            lines.append(f"  - generated files: {case.generated_files_count}")
            if case.workspace:
                lines.append(f"  - workspace: `{case.workspace}`")
            if case.errors:
                for error in case.errors[:5]:
                    lines.append(f"  - error: {error}")
        lines.append("")
        return "\n".join(lines)


def default_golden_cases() -> list[GoldenCase]:
    return [
        GoldenCase(
            identifier="basic_ruby_item",
            request="Create a ruby mod with ruby.",
            expected_features=["ruby"],
            expected_paths=[
                "src/main/java/com/generated/ruby_mod/RubyMod.java",
                "src/main/resources/assets/ruby_mod/items/ruby.json",
                "src/main/resources/assets/ruby_mod/models/item/ruby.json",
                "src/main/resources/assets/ruby_mod/textures/item/ruby.png",
                "src/main/resources/assets/ruby_mod/lang/en_us.json",
                "src/main/resources/assets/ruby_mod/lang/zh_cn.json",
                "src/main/resources/pack.mcmeta",
                ".agent/texture-manifest.json",
            ],
            json_expectations=[
                GoldenJsonExpectation("src/main/resources/assets/ruby_mod/items/ruby.json", {"model.type": "minecraft:model", "model.model": "ruby_mod:item/ruby"}),
                GoldenJsonExpectation("src/main/resources/assets/ruby_mod/models/item/ruby.json", {"parent": "minecraft:item/generated", "textures.layer0": "ruby_mod:item/ruby"}),
                GoldenJsonExpectation("src/main/resources/pack.mcmeta", {"pack.description": "ruby_mod resources", "pack.pack_format": "__int__"}),
                GoldenJsonExpectation(".agent/texture-manifest.json", {"textures": "__list__"}, contains=["ruby.png"]),
            ],
            min_generated_files=7,
        ),
        GoldenCase(
            identifier="ruby_block",
            request="Create a ruby mod with ruby block.",
            expected_features=["ruby_block"],
            expected_paths=[
                "src/main/resources/assets/ruby_mod/blockstates/ruby_block.json",
                "src/main/resources/assets/ruby_mod/items/ruby_block.json",
                "src/main/resources/assets/ruby_mod/models/block/ruby_block.json",
                "src/main/resources/assets/ruby_mod/models/item/ruby_block.json",
                "src/main/resources/assets/ruby_mod/textures/block/ruby_block.png",
                "src/main/resources/data/ruby_mod/loot_table/blocks/ruby_block.json",
            ],
            json_expectations=[
                GoldenJsonExpectation("src/main/resources/assets/ruby_mod/models/block/ruby_block.json", {"parent": "minecraft:block/cube_all", "textures.all": "ruby_mod:block/ruby_block"}),
            ],
            min_generated_files=10,
        ),
        GoldenCase(
            identifier="ruby_charm_behavior",
            request="Create a ruby mod with a ruby charm item.",
            expected_features=["ruby_charm"],
            expected_paths=[
                "src/main/java/com/generated/ruby_mod/RubyMod.java",
                "src/main/java/com/generated/ruby_mod/item/RubyCharmItem.java",
                "src/main/resources/assets/ruby_mod/items/ruby_charm.json",
                "src/main/resources/assets/ruby_mod/models/item/ruby_charm.json",
                "src/main/resources/assets/ruby_mod/textures/item/ruby_charm.png",
            ],
            json_expectations=[
                GoldenJsonExpectation("src/main/resources/assets/ruby_mod/models/item/ruby_charm.json", {"textures.layer0": "ruby_mod:item/ruby_charm"}),
            ],
            min_generated_files=8,
        ),
        GoldenCase(
            identifier="ruby_food_effect",
            request="Create a ruby apple that grants regeneration II for 5 seconds.",
            expected_features=["ruby_apple"],
            expected_paths=[
                "src/main/resources/assets/ruby_mod/models/item/ruby_apple.json",
                "src/main/resources/assets/ruby_mod/items/ruby_apple.json",
                "src/main/resources/assets/ruby_mod/textures/item/ruby_apple.png",
            ],
            json_expectations=[
                GoldenJsonExpectation("src/main/resources/assets/ruby_mod/models/item/ruby_apple.json", {"parent": "minecraft:item/generated", "textures.layer0": "ruby_mod:item/ruby_apple"}),
            ],
            min_generated_files=7,
        ),
        GoldenCase(
            identifier="ruby_sword_ignite",
            request="Create a ruby sword that ignites enemies for 5 seconds.",
            expected_features=["ruby_sword"],
            expected_paths=[
                "src/main/java/com/generated/ruby_mod/item/RubySwordItem.java",
                "src/main/resources/assets/ruby_mod/items/ruby_sword.json",
                "src/main/resources/assets/ruby_mod/models/item/ruby_sword.json",
                "src/main/resources/assets/ruby_mod/textures/item/ruby_sword.png",
            ],
            json_expectations=[
                GoldenJsonExpectation("src/main/resources/assets/ruby_mod/models/item/ruby_sword.json", {"parent": "minecraft:item/handheld", "textures.layer0": "ruby_mod:item/ruby_sword"}),
            ],
            min_generated_files=8,
        ),
        GoldenCase(
            identifier="ruby_ore_worldgen",
            request="Create a ruby mod with ruby and ruby ore, ruby ore drops ruby, and ruby ore generates underground in the overworld, Y -64 to 32, vein size 6, 4 per chunk.",
            expected_features=["ruby", "ruby_ore"],
            expected_paths=[
                "src/main/resources/data/ruby_mod/worldgen/configured_feature/ruby_ore.json",
                "src/main/resources/data/ruby_mod/worldgen/placed_feature/ruby_ore.json",
                "src/main/resources/data/ruby_mod/neoforge/biome_modifier/add_ruby_ore.json",
                "src/main/resources/data/ruby_mod/loot_table/blocks/ruby_ore.json",
            ],
            json_expectations=[
                GoldenJsonExpectation("src/main/resources/data/ruby_mod/worldgen/configured_feature/ruby_ore.json", {"type": "minecraft:ore", "config.size": 6}, contains=["ruby_mod:ruby_ore"]),
                GoldenJsonExpectation("src/main/resources/data/ruby_mod/worldgen/placed_feature/ruby_ore.json", {"feature": "ruby_mod:ruby_ore", "placement.0.count": 4}, contains=["minecraft:height_range"]),
                GoldenJsonExpectation("src/main/resources/data/ruby_mod/neoforge/biome_modifier/add_ruby_ore.json", {"type": "neoforge:add_features", "step": "underground_ores"}, contains=["#minecraft:is_overworld"]),
            ],
            min_generated_files=14,
        ),
        GoldenCase(
            identifier="ruby_tool_set",
            request="Create a ruby mod with ruby tool set.",
            expected_features=["ruby", "ruby_sword", "ruby_pickaxe", "ruby_axe", "ruby_shovel", "ruby_hoe"],
            expected_paths=[
                "src/main/resources/assets/ruby_mod/models/item/ruby_pickaxe.json",
                "src/main/resources/assets/ruby_mod/items/ruby_pickaxe.json",
                "src/main/resources/assets/ruby_mod/models/item/ruby_axe.json",
                "src/main/resources/assets/ruby_mod/items/ruby_axe.json",
                "src/main/resources/assets/ruby_mod/models/item/ruby_shovel.json",
                "src/main/resources/assets/ruby_mod/items/ruby_shovel.json",
                "src/main/resources/assets/ruby_mod/models/item/ruby_hoe.json",
                "src/main/resources/assets/ruby_mod/items/ruby_hoe.json",
                "src/main/resources/data/ruby_mod/recipe/ruby_pickaxe.json",
                "src/main/resources/data/ruby_mod/recipe/ruby_axe.json",
                "src/main/resources/data/ruby_mod/recipe/ruby_shovel.json",
                "src/main/resources/data/ruby_mod/recipe/ruby_hoe.json",
            ],
            json_expectations=[
                GoldenJsonExpectation("src/main/resources/assets/ruby_mod/models/item/ruby_pickaxe.json", {"parent": "minecraft:item/handheld", "textures.layer0": "ruby_mod:item/ruby_pickaxe"}),
                GoldenJsonExpectation("src/main/resources/data/ruby_mod/recipe/ruby_pickaxe.json", {"type": "minecraft:crafting_shaped", "result.id": "ruby_mod:ruby_pickaxe"}),
            ],
            min_generated_files=18,
        ),
        GoldenCase(
            identifier="ruby_armor_set",
            request="Create a ruby mod with ruby armor set.",
            expected_features=["ruby", "ruby_helmet", "ruby_chestplate", "ruby_leggings", "ruby_boots"],
            expected_paths=[
                "src/main/resources/assets/ruby_mod/models/item/ruby_helmet.json",
                "src/main/resources/assets/ruby_mod/items/ruby_helmet.json",
                "src/main/resources/assets/ruby_mod/models/item/ruby_chestplate.json",
                "src/main/resources/assets/ruby_mod/items/ruby_chestplate.json",
                "src/main/resources/assets/ruby_mod/models/item/ruby_leggings.json",
                "src/main/resources/assets/ruby_mod/items/ruby_leggings.json",
                "src/main/resources/assets/ruby_mod/models/item/ruby_boots.json",
                "src/main/resources/assets/ruby_mod/items/ruby_boots.json",
                "src/main/resources/data/ruby_mod/recipe/ruby_helmet.json",
                "src/main/resources/data/ruby_mod/recipe/ruby_chestplate.json",
                "src/main/resources/data/ruby_mod/recipe/ruby_leggings.json",
                "src/main/resources/data/ruby_mod/recipe/ruby_boots.json",
            ],
            json_expectations=[
                GoldenJsonExpectation("src/main/resources/assets/ruby_mod/models/item/ruby_helmet.json", {"parent": "minecraft:item/generated", "textures.layer0": "ruby_mod:item/ruby_helmet"}),
                GoldenJsonExpectation("src/main/resources/data/ruby_mod/recipe/ruby_helmet.json", {"type": "minecraft:crafting_shaped", "result.id": "ruby_mod:ruby_helmet"}),
            ],
            min_generated_files=16,
        ),
        GoldenCase(
            identifier="ruby_block_variants",
            request="Create a ruby mod with ruby block variants.",
            expected_features=[
                "ruby_block",
                "ruby_stairs",
                "ruby_slab",
                "ruby_wall",
                "ruby_button",
                "ruby_pressure_plate",
                "ruby_fence",
                "ruby_fence_gate",
                "ruby_door",
                "ruby_trapdoor",
            ],
            expected_paths=[
                "src/main/resources/assets/ruby_mod/blockstates/ruby_stairs.json",
                "src/main/resources/assets/ruby_mod/blockstates/ruby_slab.json",
                "src/main/resources/assets/ruby_mod/blockstates/ruby_wall.json",
                "src/main/resources/assets/ruby_mod/blockstates/ruby_door.json",
                "src/main/resources/assets/ruby_mod/blockstates/ruby_trapdoor.json",
                "src/main/resources/assets/ruby_mod/models/block/ruby_stairs_inner.json",
                "src/main/resources/assets/ruby_mod/models/block/ruby_wall_side_tall.json",
                "src/main/resources/assets/ruby_mod/models/block/ruby_door_bottom_left.json",
                "src/main/resources/assets/ruby_mod/models/block/ruby_trapdoor_open.json",
                "src/main/resources/data/ruby_mod/recipe/ruby_stairs.json",
                "src/main/resources/data/ruby_mod/recipe/ruby_door.json",
            ],
            json_expectations=[
                GoldenJsonExpectation("src/main/resources/assets/ruby_mod/models/block/ruby_stairs.json", {"parent": "minecraft:block/stairs"}),
                GoldenJsonExpectation("src/main/resources/assets/ruby_mod/blockstates/ruby_wall.json", {"multipart": "__list__"}, contains=["ruby_wall_side_tall"]),
                GoldenJsonExpectation("src/main/resources/assets/ruby_mod/blockstates/ruby_door.json", {"variants": "__dict__"}, contains=["half=lower"]),
                GoldenJsonExpectation("src/main/resources/data/ruby_mod/recipe/ruby_door.json", {"type": "minecraft:crafting_shaped", "result.id": "ruby_mod:ruby_door"}),
            ],
            min_generated_files=70,
        ),
        GoldenCase(
            identifier="ruby_goblin_entity",
            request="Create a ruby goblin mob with melee attack, emerald drops, and overworld spawn.",
            expected_features=["ruby_goblin"],
            expected_paths=[
                "src/main/java/com/generated/ruby_mod/entity/RubyGoblinEntity.java",
                "src/main/java/com/generated/ruby_mod/client/RubyGoblinRenderer.java",
                "src/main/java/com/generated/ruby_mod/client/RubyModEntityClient.java",
                "src/main/resources/assets/ruby_mod/textures/entity/ruby_goblin.png",
                "src/main/resources/data/ruby_mod/loot_table/entities/ruby_goblin.json",
                "src/main/resources/data/ruby_mod/neoforge/biome_modifier/add_ruby_goblin.json",
            ],
            json_expectations=[
                GoldenJsonExpectation("src/main/resources/data/ruby_mod/loot_table/entities/ruby_goblin.json", {"type": "minecraft:entity"}, contains=["minecraft:emerald"]),
                GoldenJsonExpectation("src/main/resources/data/ruby_mod/neoforge/biome_modifier/add_ruby_goblin.json", {"type": "neoforge:add_spawns"}, contains=["ruby_mod:ruby_goblin"]),
            ],
            min_generated_files=10,
        ),
        GoldenCase(
            identifier="ruby_realm_world_structure",
            request="Create a Ruby Realm dimension with Ruby Fields biome, ruby vein world feature, ruby shrine structure, and loot pool.",
            expected_features=["ruby_realm", "ruby_fields", "ruby_vein", "ruby_shrine", "ruby_shrine_loot"],
            expected_paths=[
                "src/main/resources/data/ruby_mod/dimension_type/ruby_realm.json",
                "src/main/resources/data/ruby_mod/dimension/ruby_realm.json",
                "src/main/resources/data/ruby_mod/worldgen/biome/ruby_fields.json",
                "src/main/resources/data/ruby_mod/worldgen/configured_feature/ruby_vein.json",
                "src/main/resources/data/ruby_mod/worldgen/placed_feature/ruby_vein.json",
                "src/main/resources/data/ruby_mod/neoforge/biome_modifier/add_ruby_vein.json",
                "src/main/resources/data/ruby_mod/worldgen/structure/ruby_shrine.json",
                "src/main/resources/data/ruby_mod/worldgen/structure_set/ruby_shrine.json",
                "src/main/resources/data/ruby_mod/worldgen/template_pool/ruby_shrine/start_pool.json",
                "src/main/resources/data/ruby_mod/loot_table/chests/ruby_shrine_loot.json",
            ],
            json_expectations=[
                GoldenJsonExpectation("src/main/resources/data/ruby_mod/dimension/ruby_realm.json", {"type": "ruby_mod:ruby_realm"}, contains=["ruby_mod:ruby_fields"]),
                GoldenJsonExpectation("src/main/resources/data/ruby_mod/worldgen/configured_feature/ruby_vein.json", {"type": "minecraft:ore", "config.size": 6}, contains=["minecraft:redstone_ore"]),
                GoldenJsonExpectation("src/main/resources/data/ruby_mod/worldgen/structure_set/ruby_shrine.json", {"placement.spacing": 28, "placement.separation": 8}, contains=["ruby_mod:ruby_shrine"]),
                GoldenJsonExpectation("src/main/resources/data/ruby_mod/loot_table/chests/ruby_shrine_loot.json", {"type": "minecraft:chest"}, contains=["minecraft:emerald"]),
            ],
            min_generated_files=12,
        ),
        GoldenCase(
            identifier="controlled_java_extension",
            request="Create a controlled Java extension for a safe info helper.",
            expected_features=["safe_info_extension"],
            expected_paths=[
                "src/main/java/com/generated/extension_mod/extension/SafeInfoExtension.java",
                ".agent/java-extension-report.json",
                ".agent/java-extension-report.md",
            ],
            json_expectations=[
                GoldenJsonExpectation(".agent/java-extension-report.json", {"status": "pending-build", "sandbox.mode": "managed-additive-class"}, contains=["SafeInfoExtension"]),
            ],
            min_generated_files=4,
        ),
    ]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _feature_ids(data: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    features = data.get("features", [])
    if isinstance(features, list):
        for feature in features:
            if isinstance(feature, dict) and feature.get("id"):
                ids.add(str(feature["id"]))
    for key in (
        "items",
        "blocks",
        "machines",
        "entities",
        "dimensions",
        "biomes",
        "world_features",
        "structures",
        "loot_pools",
        "java_extensions",
        "ores",
        "foods",
        "swords",
        "tools",
        "armors",
        "recipes",
    ):
        entries = data.get(key, [])
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and entry.get("id"):
                    ids.add(str(entry["id"]))
    return ids


def _normalize_relative_path(value: str) -> str:
    return value.replace("\\", "/").strip("/").lower()


def _json_select(data: Any, dotted_path: str) -> Any:
    current = data
    for part in dotted_path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
            continue
        if isinstance(current, dict):
            current = current.get(part)
            continue
        return None
    return current


def _json_matches(actual: Any, expected: Any) -> bool:
    if expected == "__int__":
        return isinstance(actual, int)
    if expected == "__list__":
        return isinstance(actual, list)
    if expected == "__dict__":
        return isinstance(actual, dict)
    return actual == expected

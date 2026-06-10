from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .tools import ensure_directory, write_json, write_text


ASCII_TOKEN_RE = re.compile(r"[a-z0-9_:#./-]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "by",
    "create",
    "for",
    "from",
    "generate",
    "generated",
    "in",
    "is",
    "make",
    "mod",
    "of",
    "on",
    "the",
    "to",
    "with",
}
CHINESE_TERMS = (
    "红宝石",
    "矿石",
    "自然生成",
    "主世界",
    "高度",
    "矿脉",
    "方块",
    "物品",
    "材质",
    "贴图",
    "黑紫",
    "模型",
    "配方",
    "掉落",
    "标签",
    "右键",
    "回血",
    "效果",
    "冷却",
    "食物",
    "剑",
    "工具",
    "护甲",
    "镐",
    "斧",
    "铲",
    "锄",
    "头盔",
    "胸甲",
    "护腿",
    "靴子",
    "点燃",
    "审计",
    "修复",
    "知识库",
)


@dataclass(slots=True)
class KnowledgeEntry:
    identifier: str
    title: str
    category: str
    tags: list[str]
    summary: str
    content: str
    capability: str = ""
    source: str = "bundled:v2.4"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "title": self.title,
            "category": self.category,
            "capability": self.capability or self.category,
            "tags": list(self.tags),
            "summary": self.summary,
            "content": self.content,
            "source": self.source,
        }


@dataclass(slots=True)
class KnowledgeHit:
    entry: KnowledgeEntry
    score: int
    matched_terms: list[str] = field(default_factory=list)
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.entry.identifier,
            "title": self.entry.title,
            "category": self.entry.category,
            "capability": self.entry.capability or self.entry.category,
            "score": self.score,
            "matched_terms": list(self.matched_terms),
            "snippet": self.snippet,
            "source": self.entry.source,
            "tags": list(self.entry.tags),
            "summary": self.entry.summary,
        }


@dataclass(slots=True)
class KnowledgeQueryResult:
    success: bool
    query: str
    limit: int
    hits: list[KnowledgeHit]
    context: str
    query_expansions: list[str] = field(default_factory=list)
    categories: dict[str, int] = field(default_factory=dict)
    capabilities: dict[str, int] = field(default_factory=dict)
    report_json_path: Path | None = None
    report_md_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "query": self.query,
            "limit": self.limit,
            "hits": [hit.to_dict() for hit in self.hits],
            "hits_count": len(self.hits),
            "query_expansions": list(self.query_expansions),
            "categories": dict(self.categories),
            "capabilities": dict(self.capabilities),
            "context": self.context,
            "report_json_path": str(self.report_json_path) if self.report_json_path else None,
            "report_md_path": str(self.report_md_path) if self.report_md_path else None,
        }


class NeoForgeKnowledgeBase:
    def __init__(self, entries: list[KnowledgeEntry] | None = None) -> None:
        self.entries = entries or default_knowledge_entries()

    def query(self, query: str, *, limit: int = 5, use_query_expansion: bool = True) -> list[KnowledgeHit]:
        query = query.strip()
        limit = max(1, min(limit, 12))
        expanded_query = _expanded_query(query) if use_query_expansion else query
        query_terms = _tokens(expanded_query)
        hits: list[KnowledgeHit] = []
        for entry in self.entries:
            entry_terms = _tokens(_entry_search_text(entry))
            matched = sorted(query_terms & entry_terms)
            score = self._score(entry, query, query_terms, matched)
            if score <= 0:
                continue
            hits.append(
                KnowledgeHit(
                    entry=entry,
                    score=score,
                    matched_terms=matched,
                    snippet=_snippet(entry, matched),
                )
            )
        hits.sort(key=lambda hit: (-hit.score, hit.entry.identifier))
        return hits[:limit]

    def categories(self) -> dict[str, list[dict[str, str]]]:
        grouped: dict[str, list[dict[str, str]]] = {}
        for entry in self.entries:
            grouped.setdefault(entry.category, []).append(
                {
                    "id": entry.identifier,
                    "title": entry.title,
                    "capability": entry.capability or entry.category,
                    "summary": entry.summary,
                }
            )
        return {category: sorted(items, key=lambda item: item["id"]) for category, items in sorted(grouped.items())}

    def render_context(self, query: str, *, limit: int = 5) -> str:
        hits = self.query(query, limit=limit)
        if not hits:
            return "NeoForge RAG Context: no matching bundled knowledge snippets were found."
        category_summary = _hit_counts(hits, key="category")
        capability_summary = _hit_counts(hits, key="capability")
        lines = [
            "NeoForge RAG Context:",
            "Use these bundled knowledge snippets as constraints. They are retrieval hints, not permission to generate unsupported feature types.",
            "Retrieved categories: " + ", ".join(f"{key}={value}" for key, value in category_summary.items()),
            "Retrieved capabilities: " + ", ".join(f"{key}={value}" for key, value in capability_summary.items()),
            "",
        ]
        for index, hit in enumerate(hits, start=1):
            lines.extend(
                [
                    f"[{index}] {hit.entry.identifier} - {hit.entry.title}",
                    f"Category: {hit.entry.category}",
                    f"Summary: {hit.entry.summary}",
                    f"Key facts: {_compact(hit.entry.content, 700)}",
                    "",
                ]
            )
        return "\n".join(lines).strip()

    def _score(self, entry: KnowledgeEntry, query: str, query_terms: set[str], matched: list[str]) -> int:
        if not query:
            return 1 if entry.identifier == "modspec.boundary" else 0
        haystack = _entry_search_text(entry).lower()
        query_lower = query.lower()
        score = len(matched) * 10
        if query_lower and query_lower in haystack:
            score += 30
        title_terms = _tokens(entry.title)
        tag_terms = _tokens(" ".join(entry.tags))
        capability_terms = _tokens(entry.capability or entry.category)
        score += len(query_terms & title_terms) * 7
        score += len(query_terms & tag_terms) * 12
        score += len(query_terms & capability_terms) * 18
        return score


class KnowledgeQueryRunner:
    def __init__(self, config: AppConfig | None = None, knowledge_base: NeoForgeKnowledgeBase | None = None) -> None:
        self.config = config or AppConfig.default()
        self.knowledge_base = knowledge_base or NeoForgeKnowledgeBase()

    def query(self, query: str, *, limit: int = 5, run_name: str | None = None) -> KnowledgeQueryResult:
        hits = self.knowledge_base.query(query, limit=limit)
        context = self.knowledge_base.render_context(query, limit=limit)
        result = KnowledgeQueryResult(
            success=True,
            query=query,
            limit=max(1, min(limit, 12)),
            hits=hits,
            context=context,
            query_expansions=_query_expansions(query),
            categories=_hit_counts(hits, key="category"),
            capabilities=_hit_counts(hits, key="capability"),
        )
        run_id = run_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        report_dir = ensure_directory(self.config.workspace_root / "knowledge-runs" / run_id / ".agent")
        result.report_json_path = report_dir / "rag-query.json"
        result.report_md_path = report_dir / "rag-query.md"
        write_json(result.report_json_path, result.to_dict())
        write_text(result.report_md_path, self._render_markdown(result))
        return result

    def _render_markdown(self, result: KnowledgeQueryResult) -> str:
        lines = [
            "# NeoForge Knowledge Query",
            "",
            f"Success: {str(result.success).lower()}",
            f"Query: `{result.query}`",
            f"Hits: {len(result.hits)}",
            "",
            "## Hits",
            "",
        ]
        if not result.hits:
            lines.append("- No matching snippets.")
        for hit in result.hits:
            lines.extend(
                [
                    f"- `{hit.entry.identifier}` score={hit.score}: {hit.entry.title}",
                    f"  - category: `{hit.entry.category}`",
                    f"  - capability: `{hit.entry.capability or hit.entry.category}`",
                    f"  - snippet: {hit.snippet}",
                ]
            )
        if result.query_expansions:
            lines.extend(["", "## Automatic Query Expansions", ""])
            lines.extend(f"- `{item}`" for item in result.query_expansions)
        lines.extend(["", "## RAG Context", "", "```text", result.context, "```", ""])
        return "\n".join(lines)


def expand_knowledge_query(query: str) -> list[str]:
    return _query_expansions(query)


def summarize_knowledge_hits(hits: list[KnowledgeHit] | list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    category_counts: dict[str, int] = {}
    capability_counts: dict[str, int] = {}
    for hit in hits:
        if isinstance(hit, KnowledgeHit):
            category = hit.entry.category
            capability = hit.entry.capability or hit.entry.category
        else:
            category = str(hit.get("category", "uncategorized"))
            capability = str(hit.get("capability", category))
        category_counts[category] = category_counts.get(category, 0) + 1
        capability_counts[capability] = capability_counts.get(capability, 0) + 1
    return {
        "categories": dict(sorted(category_counts.items())),
        "capabilities": dict(sorted(capability_counts.items())),
    }


def default_knowledge_entries() -> list[KnowledgeEntry]:
    return [
        KnowledgeEntry(
            identifier="modspec.boundary",
            title="ModSpec is the generation contract",
            category="architecture",
            capability="modspec_boundary",
            tags=["modspec", "llm", "deterministic-generator", "validator", "audit"],
            summary="Natural language and LLM planning should produce ModSpec only; Java and JSON are generated deterministically.",
            content=(
                "The project boundary is natural language or LLM -> ModSpec -> validator -> deterministic Java/JSON/assets -> audit/build/repair. "
                "LLM output must stay constrained to supported ModSpec fields. Do not ask the LLM to emit arbitrary Java, Gradle, datapack JSON, or PNG bytes."
            ),
        ),
        KnowledgeEntry(
            identifier="neoforge.deferred_register",
            title="NeoForge registration uses deferred registers",
            category="java",
            capability="registration",
            tags=["neoforge", "registry", "deferredregister", "deferreditem", "deferredblock", "item", "block"],
            summary="Generated Java should register content through NeoForge deferred register helpers in the mod main class.",
            content=(
                "Generated items and blocks are registered from the mod main class with DeferredRegister helpers. "
                "Behavior items and swords use generated custom item classes, while normal items can use simple Item registrations. "
                "The registry id must match the ModSpec feature id and the generated asset/model file names."
            ),
        ),
        KnowledgeEntry(
            identifier="neoforge.mods_toml",
            title="NeoForge metadata is declared in neoforge.mods.toml",
            category="metadata",
            capability="mod_metadata",
            tags=["neoforge.mods.toml", "mods.toml", "mod metadata", "modloader", "loaderVersion", "displayName"],
            summary="Generated NeoForge projects include a mods metadata template under src/main/templates/META-INF.",
            content=(
                "The generated NeoForge metadata file lives at src/main/templates/META-INF/neoforge.mods.toml. "
                "A minimal generated metadata template includes modLoader, loaderVersion, license, [[mods]], modId, version, displayName, and description. "
                "The modId must match the generated ModSpec id so Gradle resource expansion and audit checks can validate the workspace."
            ),
        ),
        KnowledgeEntry(
            identifier="java.controlled_extension",
            title="V6.1 controlled Java extension is additive, sandboxed, and gated",
            category="java",
            capability="controlled_java_extension",
            tags=["java_extension", "sandbox", "controlled", "audit", "build", "llm"],
            summary="V6.1 may request only managed additive extension classes through structured ModSpec fields and records build, diff, and rollback evidence.",
            content=(
                "Controlled Java extension entries use type java_extension in ModSpec. "
                "The LLM may provide class_name, purpose, explanation, allowed_imports from the allowlist, and String-returning method declarations. "
                "The deterministic generator writes classes only under <package>.extension and writes .agent/java-extension-report.json, .agent/java-extension-diff.md, and rollback reports. "
                "It must not patch existing Java sources, generate package/import text directly, modify Gradle, use file/network/process/reflection/thread APIs, or skip validator, audit, and build gates."
            ),
        ),
        KnowledgeEntry(
            identifier="workflow.managed_patch_agent",
            title="Controlled patch agent edits managed files only",
            category="workflow",
            capability="patch_agent",
            tags=["patch_agent", "modify", "managed_files", "audit", "build", "rollback"],
            summary="The patch agent first writes a patch plan, then regenerates only managed files and records audit, build, and rollback evidence.",
            content=(
                "The controlled patch-agent layer is built on modify mode rather than raw repository editing. "
                "LLM output is still constrained to a structured patch plan or patch ModSpec delta, the executor regenerates only managed files, and the workspace writes .agent/patch-agent-plan.json, .agent/patch-agent-report.json, and rollback guidance. "
                "User-authored files stay outside the overwrite scope; audit and build gates decide whether the patch is accepted."
            ),
        ),
        KnowledgeEntry(
            identifier="assets.models_textures",
            title="Assets live under assets/<modid>",
            category="assets",
            capability="assets_models_textures",
            tags=["assets", "model", "texture", "材质", "贴图", "black-purple", "黑紫"],
            summary="Item and block models reference textures under src/main/resources/assets/<modid>/textures.",
            content=(
                "Item model definitions are generated under assets/<modid>/items/<id>.json for Minecraft 26.x, and legacy model files remain under assets/<modid>/models/item/<id>.json. "
                "The item definition points at the model path, usually <modid>:item/<id>. "
                "Block models are generated under assets/<modid>/models/block/<id>.json and normally reference <modid>:block/<id>. "
                "Missing or malformed textures can appear in-game as black/purple missing-texture blocks."
            ),
        ),
        KnowledgeEntry(
            identifier="assets.procedural_textures",
            title="Programmatic textures are managed assets",
            category="assets",
            capability="procedural_textures",
            tags=["texture-manifest", "resource-quality-report", "texture-atlas", "procedural_textures", "png", "16x16", "rgba", "材质", "贴图"],
            summary="V8 keeps deterministic 16x16 RGBA PNG textures and adds resource quality profiles, texture atlas previews, and resource reports.",
            content=(
                "Supported generated features receive deterministic 16x16 RGBA PNG placeholder textures. "
                "Templates include gem, heal_badge, effect_crystal, apple, sword, tool icons, armor icons, solid_block, and ore_block. "
                "The manifest .agent/texture-manifest.json records id, feature type, path, template, width, height, and color type. "
                "V8 also writes .agent/resource-quality-report.json and .agent/texture-atlas.png so dashboards can show texture profiles, model variant counts, and preview evidence without external image dependencies."
            ),
        ),
        KnowledgeEntry(
            identifier="audit.texture_checks",
            title="Audit verifies managed texture PNG files",
            category="audit",
            capability="texture_audit",
            tags=["audit", "texture_audit", "png", "repair-loop", "修复", "审计"],
            summary="Audit checks generated texture existence and PNG shape before in-game testing.",
            content=(
                "Workspace audit checks texture-manifest.json and every managed texture path. "
                "Generated textures should have a PNG signature, IHDR chunk, 16x16 size, 8-bit depth, and RGBA color type. "
                "If a generated texture is deleted, repair-loop can regenerate managed files from .agent/modspec.json."
            ),
        ),
        KnowledgeEntry(
            identifier="behavior.right_click_item",
            title="Right click item behaviors use custom Item classes",
            category="behavior",
            capability="right_click_behavior",
            tags=["behavior", "right_click_heal", "right_click_effect", "右键", "回血", "效果", "cooldown"],
            summary="right_click_heal and right_click_effect generate custom item classes with server-side action logic.",
            content=(
                "Behavior items override use(Level, Player, InteractionHand). "
                "Server-side logic performs player.heal(...) or player.addEffect(new MobEffectInstance(...)), then applies cooldown and optional stack consumption. "
                "The item registry should use the generated class, for example RubyCharmItem::new."
            ),
        ),
        KnowledgeEntry(
            identifier="behavior.dsl_event_action",
            title="V5.1 Behavior DSL is a shared event-condition-action layer",
            category="behavior",
            capability="shared_behavior_report",
            tags=["behavior", "behavior_dsl", "event_action", "right_click", "hit_entity", "inventory_tick", "block_use", "machine", "entity", "progression", "quest", "combo", "state", "resource", "chain"],
            summary="Behavior DSL declares shared triggers, conditions, actions, combos, state, resources, cooldowns, and chains while Java remains deterministically generated.",
            content=(
                "A behavior with type event_action can declare events as trigger -> conditions -> actions. "
                "The shared layer covers item, block, machine, entity, progression, and quest hosts; item/block/sword/ore hooks are compiled into managed runtime templates, while machine/entity/progression/quest behavior is captured as report-only semantics for audit and roadmap evidence. "
                "Events can use trigger_mode any/all/sequence, window_ticks, state fields, resource fields, cooldown_ready, combo_ready, and chain_event actions. "
                "The LLM should emit Behavior DSL JSON only; Java, resources, reports, and checklists are still generated deterministically by Python."
            ),
        ),
        KnowledgeEntry(
            identifier="behavior.food_effects",
            title="Food effects are declared in ModSpec",
            category="behavior",
            capability="food_effects",
            tags=["food", "effects", "regeneration", "食物", "生命恢复"],
            summary="Food effects use effect resource locations, duration ticks, amplifier, and probability.",
            content=(
                "Food ModSpec entries can include effects with effect, duration_ticks, amplifier, and probability. "
                "Supported effect mappings include minecraft:speed, minecraft:regeneration, minecraft:strength, minecraft:resistance, minecraft:jump_boost, and minecraft:haste."
            ),
        ),
        KnowledgeEntry(
            identifier="behavior.sword_ignite",
            title="Sword ignite uses a generated custom item class",
            category="behavior",
            capability="sword_ignite",
            tags=["sword", "ignite", "点燃", "剑", "on_hit"],
            summary="sword.on_hit ignite generates a custom class whose hit logic ignites the target.",
            content=(
                "A sword with on_hit type ignite should generate <PascalId>Item.java. "
                "The generated class calls target.igniteForSeconds(seconds) from hurtEnemy and then calls super.hurtEnemy(...)."
            ),
        ),
        KnowledgeEntry(
            identifier="content.tools_armor",
            title="Tools and armor are deterministic content types",
            category="content",
            capability="tools_armor",
            tags=["tool", "armor", "pickaxe", "axe", "shovel", "hoe", "helmet", "chestplate", "leggings", "boots", "工具", "护甲"],
            summary="V2.7 supports tool and armor ModSpec features, equipment sets, and deterministic equipment recipes without allowing LLM-generated Java.",
            content=(
                "Tool features support tool_type pickaxe, axe, shovel, and hoe with tool_material plus attack baselines. "
                "Armor features support armor_type helmet, chestplate, leggings, and boots with armor_material. "
                "Ruby equipment sets should include ruby material, ruby_sword plus the four tools or the four armor pieces, and shaped recipe features. "
                "The LLM should output ModSpec feature declarations only; Java registration, item models, textures, language entries, and audit checks are generated deterministically."
            ),
        ),
        KnowledgeEntry(
            identifier="content.block_variants",
            title="Block variants use block_kind declarations",
            category="content",
            capability="block_variants",
            tags=["block", "stairs", "slab", "wall", "button", "pressure_plate", "fence", "door", "trapdoor", "方块变体", "楼梯", "台阶", "门"],
            summary="V2.8 supports block_kind-based generation for common building and simple interactive blocks.",
            content=(
                "Block features may set block_kind to cube, stairs, slab, wall, button, pressure_plate, fence, fence_gate, door, or trapdoor. "
                "Ruby block variant requests should include ruby_block plus ruby_stairs, ruby_slab, ruby_wall, ruby_button, ruby_pressure_plate, ruby_fence, ruby_fence_gate, ruby_door, and ruby_trapdoor. "
                "The LLM should only emit ModSpec fields such as block_kind and base_block; Java registrations, blockstates, models, loot, recipes, textures, and audit checks are deterministic."
            ),
        ),
        KnowledgeEntry(
            identifier="data.recipes_loot_tags",
            title="Data pack files cover recipes, loot, and tags",
            category="data",
            capability="recipes_loot_tags",
            tags=["recipe", "loot_table", "tag", "配方", "掉落", "标签"],
            summary="Generated data JSON files live under src/main/resources/data.",
            content=(
                "Recipes are generated under data/<modid>/recipe/<id>.json. "
                "Block and ore loot tables are generated under data/<modid>/loot_table/blocks/<id>.json. "
                "Mineable and tool tier tags are generated under data/minecraft/tags/block."
            ),
        ),
        KnowledgeEntry(
            identifier="worldgen.overworld_ore",
            title="Overworld ore worldgen uses configured, placed, and biome modifier JSON",
            category="worldgen",
            capability="overworld_ore",
            tags=["worldgen", "ore", "configured_feature", "placed_feature", "biome_modifier", "矿石", "自然生成", "主世界", "矿脉"],
            summary="V0.8 supports overworld underground ore generation through deterministic JSON files.",
            content=(
                "Ore worldgen currently supports minecraft:overworld. "
                "Generated files include data/<modid>/worldgen/configured_feature/<ore_id>.json, "
                "data/<modid>/worldgen/placed_feature/<ore_id>.json, and data/<modid>/neoforge/biome_modifier/add_<ore_id>.json. "
                "The biome modifier targets #minecraft:is_overworld and step underground_ores."
            ),
        ),
        KnowledgeEntry(
            identifier="world.structure_dsl",
            title="V5.4 World / Structure DSL stays data-driven",
            category="worldgen",
            capability="world_structure_dsl",
            tags=["dimension", "biome", "structure", "world_feature", "loot_pool", "vein", "worldgen"],
            summary="V5.4 supports template-based world and structure data pack features through ModSpec.",
            content=(
                "World / Structure DSL entries use ModSpec feature types dimension, biome, world_feature, structure, and loot_pool. "
                "The deterministic generator writes dimension_type, dimension, worldgen/biome, configured_feature, placed_feature, NeoForge biome_modifier, worldgen/structure, structure_set, template_pool, and chest loot_table JSON. "
                "The supported world_feature kind is ore_vein and the supported structure kind is jigsaw. "
                "Authored NBT structures, custom terrain noise, and complex cross-dimension gameplay logic remain outside the default generator."
            ),
        ),
        KnowledgeEntry(
            identifier="pack.mcmeta",
            title="Generated resources include pack.mcmeta",
            category="resources",
            capability="pack_mcmeta",
            tags=["pack.mcmeta", "resources", "datapack", "resourcepack"],
            summary="Generated projects include src/main/resources/pack.mcmeta and audit checks its basic shape.",
            content=(
                "pack.mcmeta is generated at src/main/resources/pack.mcmeta. "
                "Audit checks that it is valid JSON and contains pack.description plus integer pack.pack_format."
            ),
        ),
        KnowledgeEntry(
            identifier="entity.mob_dsl",
            title="V5.3 Entity / Mob DSL uses deterministic mob templates",
            category="content",
            capability="entity",
            tags=["entity", "mob", "monster", "pet", "boss", "npc", "attributes", "ai_goal", "loot_table", "spawn"],
            summary="V5.3 supports structured entity declarations for simple mobs without free-form Java.",
            content=(
                "Entity / Mob DSL entries use type entity in ModSpec. "
                "Supported fields include entity_kind, category, width, height, tracking_range, update_interval, xp_reward, fire_immune, attributes, drops, spawn, goals, and attack. "
                "The deterministic generator writes EntityType registration, a PathfinderMob subclass, attribute registration, a lightweight client renderer, entity texture, language keys, entity loot table, and optional NeoForge add_spawns biome modifier. "
                "Supported AI templates include float, melee_attack, random_stroll, look_at_player, random_look_around, hurt_by_target, and target_player."
            ),
        ),
        KnowledgeEntry(
            identifier="unsupported.boundaries",
            title="Current unsupported game systems",
            category="limits",
            capability="unsupported_boundaries",
            tags=["unsupported", "gui", "entity", "blockentity", "dimension", "限制"],
            summary="The current generator intentionally excludes complex free-form systems such as arbitrary GUI logic, advanced entity AI, custom terrain engines, and handwritten Java.",
            content=(
                "Unsupported or out-of-scope systems include arbitrary GUI logic, custom energy networks, complex entity animation/model systems, advanced entity AI, authored NBT structures, custom terrain noise engines, arbitrary Java snippets, and scripting. "
                "Requests for those systems should produce warnings or stay out of generated ModSpec rather than inventing unsupported feature types."
            ),
        ),
    ]


def _entry_search_text(entry: KnowledgeEntry) -> str:
    return " ".join([entry.identifier, entry.title, entry.category, entry.capability, " ".join(entry.tags), entry.summary, entry.content])


def _expanded_query(query: str) -> str:
    expansions = _query_expansions(query)
    if not expansions:
        return query
    return " ".join([query, *expansions])


def _query_expansions(query: str) -> list[str]:
    lowered = query.lower()
    expansions: list[str] = []
    if any(token in lowered for token in ("right click", "heal", "charm", "ruby_charm", "cooldown")) or any(token in query for token in ("右键", "回血", "护符", "冷却")):
        expansions.extend(["behavior", "right_click_heal", "right_click_effect", "custom item", "cooldown"])
    if any(token in lowered for token in ("behavior dsl", "event action", "particle", "sound", "inventory tick", "block use")):
        expansions.extend(["behavior_dsl", "event_action", "right_click", "hit_entity", "inventory_tick", "block_use", "particles", "sounds"])
    if any(token in lowered for token in ("effect", "speed", "regeneration", "food", "apple")) or any(token in query for token in ("效果", "速度", "生命恢复", "食物", "苹果")):
        expansions.extend(["behavior", "food_effects", "mob effect", "duration_ticks", "amplifier"])
    if any(token in lowered for token in ("sword", "ignite", "fire", "on hit")) or any(token in query for token in ("剑", "点燃", "着火", "击中")):
        expansions.extend(["behavior", "sword_ignite", "on_hit", "custom sword item"])
    if any(token in lowered for token in ("ore", "worldgen", "overworld", "underground", "vein")) or any(token in query for token in ("矿石", "自然生成", "主世界", "矿脉", "地下")):
        expansions.extend(["worldgen", "overworld_ore", "configured_feature", "placed_feature", "biome_modifier"])
    if any(token in lowered for token in ("dimension", "biome", "structure", "world feature", "loot pool", "world structure")):
        expansions.extend(["world_structure_dsl", "dimension", "biome", "structure", "structure_set", "template_pool", "loot_pool"])
    if any(token in lowered for token in ("java extension", "controlled java extension", "safe java extension", "sandboxed java")):
        expansions.extend(["java_extension", "controlled_java_extension", "sandbox", "audit", "build"])
    if any(token in lowered for token in ("texture", "png", "asset", "model", "black purple")) or any(token in query for token in ("贴图", "黑紫", "模型", "材质")):
        expansions.extend(["assets", "procedural_textures", "texture_manifest", "model texture"])
    if any(token in lowered for token in ("tool", "armor", "pickaxe", "helmet", "equipment")) or any(token in query for token in ("工具", "护甲", "装备", "镐")):
        expansions.extend(["content", "tool", "armor", "equipment_sets", "equipment_recipes"])
    if any(token in lowered for token in ("stairs", "slab", "wall", "button", "door", "trapdoor", "fence", "block variants", "building block")) or any(token in query for token in ("楼梯", "台阶", "门", "方块变体")):
        expansions.extend(["content", "block_variants", "block_kind", "interactive_blocks"])
    if any(token in lowered for token in ("recipe", "loot", "tag")) or any(token in query for token in ("配方", "掉落", "标签")):
        expansions.extend(["data", "recipe", "loot_table", "tags"])
    if any(token in lowered for token in ("llm", "modspec", "planner", "agent", "audit", "repair")) or any(token in query for token in ("知识库", "审计", "修复", "规划")):
        expansions.extend(["architecture", "modspec", "validator", "audit", "repair"])
    if any(token in lowered for token in ("entity", "mob", "monster", "pet", "boss", "npc", "goblin", "spawn", "ai goal")):
        expansions.extend(["content", "entity", "mob_dsl", "entity_attributes", "entity_ai_goals", "entity_loot_spawn"])
    return sorted(set(expansions))

def _hit_counts(hits: list[KnowledgeHit], *, key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for hit in hits:
        value = hit.entry.category if key == "category" else (hit.entry.capability or hit.entry.category)
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    tokens = set(ASCII_TOKEN_RE.findall(lowered))
    tokens.update(term for term in CHINESE_TERMS if term in text)
    return {token for token in tokens if token and len(token) > 1 and token not in STOP_WORDS}


def _snippet(entry: KnowledgeEntry, matched_terms: list[str]) -> str:
    text = f"{entry.summary} {entry.content}"
    compact = _compact(text, 420)
    for term in matched_terms:
        index = text.lower().find(term.lower())
        if index >= 0:
            start = max(0, index - 120)
            end = min(len(text), index + 300)
            return _compact(text[start:end], 420)
    return compact


def _compact(text: str, limit: int) -> str:
    value = " ".join(text.split())
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."

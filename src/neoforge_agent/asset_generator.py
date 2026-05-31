from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any

from .models import ArmorSpec, BlockSpec, EntityDropSpec, EntitySpec, FoodSpec, ItemSpec, MachineSpec, ModSpec, OreSpec, RecipeSpec, SwordSpec, ToolSpec, WorldStructureSpec
from .project_generator import ProjectLayout
from .tools import ensure_directory, write_json, write_text


class AssetGenerator:
    def generate(self, layout: ProjectLayout, spec: ModSpec) -> list[Path]:
        out: list[Path] = []
        asset_root = layout.asset_dir
        data_root = ensure_directory(layout.resources_dir / "data" / spec.mod_id)
        en_us = {f"itemGroup.{spec.mod_id}": f"{spec.display_name} Tab"}
        zh_cn = {f"itemGroup.{spec.mod_id}": spec.display_name}

        item_definitions = ensure_directory(asset_root / "items")
        item_models = ensure_directory(asset_root / "models" / "item")
        item_textures = ensure_directory(asset_root / "textures" / "item")
        blockstates = ensure_directory(asset_root / "blockstates")
        block_models = ensure_directory(asset_root / "models" / "block")
        block_textures = ensure_directory(asset_root / "textures" / "block")
        entity_textures = ensure_directory(asset_root / "textures" / "entity")
        texture_records: list[dict[str, Any]] = []
        model_records: list[dict[str, Any]] = []
        structure_previews: list[dict[str, Any]] = []

        for item in spec.items:
            out.append(self._item_model(item_models, spec, item))
            out.append(self._item_definition(item_definitions, spec, item.identifier))
            texture_path = self._item_texture(item_textures, item)
            out.append(texture_path)
            texture_records.append(self._texture_record(layout, "item", item.identifier, texture_path, self._item_texture_kind(item), self._color(item)))
            self._item_lang(spec, item, en_us, zh_cn)
        for food in spec.foods:
            out.append(self._item_model(item_models, spec, food))
            out.append(self._item_definition(item_definitions, spec, food.identifier))
            texture_path = self._food_texture(item_textures, food)
            out.append(texture_path)
            texture_records.append(self._texture_record(layout, "food", food.identifier, texture_path, "apple", self._color(food)))
            self._item_lang(spec, food, en_us, zh_cn)
        for sword in spec.swords:
            out.append(write_json(item_models / f"{sword.identifier}.json", {"parent": "minecraft:item/handheld", "textures": {"layer0": f"{spec.mod_id}:item/{sword.identifier}"}}))
            out.append(self._item_definition(item_definitions, spec, sword.identifier))
            texture_path = self._sword_texture(item_textures, sword)
            out.append(texture_path)
            texture_records.append(self._texture_record(layout, "sword", sword.identifier, texture_path, "sword", self._color(sword)))
            self._item_lang(spec, sword, en_us, zh_cn)
        for tool in spec.tools:
            out.append(write_json(item_models / f"{tool.identifier}.json", {"parent": "minecraft:item/handheld", "textures": {"layer0": f"{spec.mod_id}:item/{tool.identifier}"}}))
            out.append(self._item_definition(item_definitions, spec, tool.identifier))
            texture_path = self._tool_texture(item_textures, tool)
            out.append(texture_path)
            texture_records.append(self._texture_record(layout, "tool", tool.identifier, texture_path, f"tool_{tool.tool_type}", self._color(tool)))
            self._item_lang(spec, tool, en_us, zh_cn)
        for armor in spec.armors:
            out.append(self._item_model(item_models, spec, armor))
            out.append(self._item_definition(item_definitions, spec, armor.identifier))
            texture_path = self._armor_texture(item_textures, armor)
            out.append(texture_path)
            texture_records.append(self._texture_record(layout, "armor", armor.identifier, texture_path, f"armor_{armor.armor_type}", self._color(armor)))
            self._item_lang(spec, armor, en_us, zh_cn)
        for block in [*spec.blocks, *spec.machines, *spec.ores]:
            block_asset_paths = self._block_assets(blockstates, block_models, item_models, spec, block)
            out.extend(block_asset_paths)
            out.append(self._item_definition(item_definitions, spec, block.identifier))
            model_records.append(self._model_variant_record(layout, block, block_asset_paths))
            texture_path = self._block_texture(block_textures, block)
            out.append(texture_path)
            texture_records.append(
                self._texture_record(
                    layout,
                    "ore" if isinstance(block, OreSpec) else "machine" if isinstance(block, MachineSpec) else "block",
                    block.identifier,
                    texture_path,
                    "ore_block" if isinstance(block, OreSpec) else "machine_block" if isinstance(block, MachineSpec) else "solid_block",
                    self._color(block),
                )
            )
            self._block_lang(spec, block, en_us, zh_cn)
        for entity in spec.entities:
            texture_path = self._entity_texture(entity_textures, entity)
            out.append(texture_path)
            texture_records.append(self._texture_record(layout, "entity", entity.identifier, texture_path, "mob_face", self._color(entity)))
            self._entity_lang(spec, entity, en_us, zh_cn)
        for structure in spec.structures:
            preview_path = self._structure_preview(layout.project_dir / ".agent" / "previews", structure)
            out.append(preview_path)
            structure_previews.append(self._structure_preview_record(layout, structure, preview_path))

        recipes_dir = ensure_directory(data_root / "recipe")
        for recipe in spec.recipes:
            payload = self._shapeless(recipe) if recipe.recipe_type == "shapeless" else self._shaped(recipe)
            out.append(write_json(recipes_dir / f"{recipe.identifier}.json", payload))

        loot_dir = ensure_directory(data_root / "loot_table" / "blocks")
        for block in spec.blocks:
            out.append(write_json(loot_dir / f"{block.identifier}.json", self._drop_table(f"{spec.mod_id}:{block.identifier}")))
        for machine in spec.machines:
            out.append(write_json(loot_dir / f"{machine.identifier}.json", self._drop_table(f"{spec.mod_id}:{machine.identifier}")))
        for ore in spec.ores:
            out.append(write_json(loot_dir / f"{ore.identifier}.json", self._drop_table(ore.drop or f"{spec.mod_id}:{ore.identifier}")))
        entity_loot_dir = ensure_directory(data_root / "loot_table" / "entities")
        for entity in spec.entities:
            out.append(write_json(entity_loot_dir / f"{entity.identifier}.json", self._entity_loot_table(entity)))
            if entity.spawn is not None and entity.spawn.enabled:
                out.append(write_json(data_root / "neoforge" / "biome_modifier" / f"add_{entity.identifier}.json", self._entity_spawn_modifier(spec, entity)))

        out.extend(self._block_tags(layout.resources_dir, spec))

        lang_dir = ensure_directory(asset_root / "lang")
        out.append(write_json(lang_dir / "en_us.json", en_us))
        out.append(write_json(lang_dir / "zh_cn.json", zh_cn))
        texture_manifest = self._texture_manifest(layout, spec, texture_records)
        texture_atlas = self._texture_atlas(layout, texture_records)
        resource_reports = self._resource_quality_reports(layout, spec, texture_records, model_records, structure_previews, texture_atlas)
        out.extend([texture_manifest, texture_atlas, *resource_reports])
        return out

    def _block_assets(
        self,
        blockstates: Path,
        block_models: Path,
        item_models: Path,
        spec: ModSpec,
        block: BlockSpec,
    ) -> list[Path]:
        kind = block.block_kind.lower()
        if kind == "stairs":
            return self._stairs_assets(blockstates, block_models, item_models, spec, block)
        if kind == "slab":
            return self._slab_assets(blockstates, block_models, item_models, spec, block)
        if kind == "wall":
            return self._wall_assets(blockstates, block_models, item_models, spec, block)
        if kind == "button":
            return self._button_assets(blockstates, block_models, item_models, spec, block)
        if kind == "pressure_plate":
            return self._pressure_plate_assets(blockstates, block_models, item_models, spec, block)
        if kind == "fence":
            return self._fence_assets(blockstates, block_models, item_models, spec, block)
        if kind == "fence_gate":
            return self._fence_gate_assets(blockstates, block_models, item_models, spec, block)
        if kind == "door":
            return self._door_assets(blockstates, block_models, item_models, spec, block)
        if kind == "trapdoor":
            return self._trapdoor_assets(blockstates, block_models, item_models, spec, block)
        texture = f"{spec.mod_id}:block/{block.identifier}"
        return [
            write_json(blockstates / f"{block.identifier}.json", {"variants": {"": {"model": f"{spec.mod_id}:block/{block.identifier}"}}}),
            write_json(block_models / f"{block.identifier}.json", {"parent": "minecraft:block/cube_all", "textures": {"all": texture}}),
            write_json(item_models / f"{block.identifier}.json", {"parent": f"{spec.mod_id}:block/{block.identifier}"}),
        ]

    def _stairs_assets(self, blockstates: Path, block_models: Path, item_models: Path, spec: ModSpec, block: BlockSpec) -> list[Path]:
        variants: dict[str, dict[str, Any]] = {}
        shape_models = {
            "straight": block.identifier,
            "inner_left": f"{block.identifier}_inner",
            "inner_right": f"{block.identifier}_inner",
            "outer_left": f"{block.identifier}_outer",
            "outer_right": f"{block.identifier}_outer",
        }
        y_rotations = {"north": 270, "east": 0, "south": 90, "west": 180}
        for facing, y in y_rotations.items():
            for half in ("bottom", "top"):
                for shape, model_name in shape_models.items():
                    for waterlogged in ("false", "true"):
                        entry: dict[str, Any] = {"model": f"{spec.mod_id}:block/{model_name}", "y": y, "uvlock": True}
                        if half == "top":
                            entry["x"] = 180
                        if shape.endswith("_right"):
                            entry["y"] = (y + 90) % 360
                        variants[f"facing={facing},half={half},shape={shape},waterlogged={waterlogged}"] = entry
        texture = f"{spec.mod_id}:block/{block.identifier}"
        return [
            write_json(blockstates / f"{block.identifier}.json", {"variants": variants}),
            write_json(block_models / f"{block.identifier}.json", {"parent": "minecraft:block/stairs", "textures": {"bottom": texture, "top": texture, "side": texture}}),
            write_json(block_models / f"{block.identifier}_inner.json", {"parent": "minecraft:block/inner_stairs", "textures": {"bottom": texture, "top": texture, "side": texture}}),
            write_json(block_models / f"{block.identifier}_outer.json", {"parent": "minecraft:block/outer_stairs", "textures": {"bottom": texture, "top": texture, "side": texture}}),
            write_json(item_models / f"{block.identifier}.json", {"parent": f"{spec.mod_id}:block/{block.identifier}"}),
        ]

    def _slab_assets(self, blockstates: Path, block_models: Path, item_models: Path, spec: ModSpec, block: BlockSpec) -> list[Path]:
        variants = {}
        for waterlogged in ("false", "true"):
            variants[f"type=bottom,waterlogged={waterlogged}"] = {"model": f"{spec.mod_id}:block/{block.identifier}"}
            variants[f"type=top,waterlogged={waterlogged}"] = {"model": f"{spec.mod_id}:block/{block.identifier}_top"}
            variants[f"type=double,waterlogged={waterlogged}"] = {"model": f"{spec.mod_id}:block/{block.identifier}_double"}
        texture = f"{spec.mod_id}:block/{block.identifier}"
        return [
            write_json(blockstates / f"{block.identifier}.json", {"variants": variants}),
            write_json(block_models / f"{block.identifier}.json", {"parent": "minecraft:block/slab", "textures": {"bottom": texture, "top": texture, "side": texture}}),
            write_json(block_models / f"{block.identifier}_top.json", {"parent": "minecraft:block/slab_top", "textures": {"bottom": texture, "top": texture, "side": texture}}),
            write_json(block_models / f"{block.identifier}_double.json", {"parent": "minecraft:block/cube_all", "textures": {"all": texture}}),
            write_json(item_models / f"{block.identifier}.json", {"parent": f"{spec.mod_id}:block/{block.identifier}"}),
        ]

    def _wall_assets(self, blockstates: Path, block_models: Path, item_models: Path, spec: ModSpec, block: BlockSpec) -> list[Path]:
        multipart: list[dict[str, Any]] = [
            {"when": {"up": "true"}, "apply": {"model": f"{spec.mod_id}:block/{block.identifier}_post"}},
        ]
        rotations = {"north": 0, "east": 90, "south": 180, "west": 270}
        for direction, y in rotations.items():
            multipart.append({"when": {direction: "low"}, "apply": {"model": f"{spec.mod_id}:block/{block.identifier}_side", "y": y, "uvlock": True}})
            multipart.append({"when": {direction: "tall"}, "apply": {"model": f"{spec.mod_id}:block/{block.identifier}_side_tall", "y": y, "uvlock": True}})
        texture = f"{spec.mod_id}:block/{block.identifier}"
        return [
            write_json(blockstates / f"{block.identifier}.json", {"multipart": multipart}),
            write_json(block_models / f"{block.identifier}.json", {"parent": "minecraft:block/wall_inventory", "textures": {"wall": texture}}),
            write_json(block_models / f"{block.identifier}_post.json", {"parent": "minecraft:block/template_wall_post", "textures": {"wall": texture}}),
            write_json(block_models / f"{block.identifier}_side.json", {"parent": "minecraft:block/template_wall_side", "textures": {"wall": texture}}),
            write_json(block_models / f"{block.identifier}_side_tall.json", {"parent": "minecraft:block/template_wall_side_tall", "textures": {"wall": texture}}),
            write_json(item_models / f"{block.identifier}.json", {"parent": f"{spec.mod_id}:block/{block.identifier}"}),
        ]

    def _button_assets(self, blockstates: Path, block_models: Path, item_models: Path, spec: ModSpec, block: BlockSpec) -> list[Path]:
        variants: dict[str, dict[str, Any]] = {}
        y_rotations = {"north": 180, "east": 270, "south": 0, "west": 90}
        for face in ("floor", "wall", "ceiling"):
            for facing, y in y_rotations.items():
                for powered in ("false", "true"):
                    model = f"{block.identifier}_pressed" if powered == "true" else block.identifier
                    entry: dict[str, Any] = {"model": f"{spec.mod_id}:block/{model}", "y": y}
                    if face == "floor":
                        entry["x"] = 90
                    elif face == "ceiling":
                        entry["x"] = 270
                    variants[f"face={face},facing={facing},powered={powered}"] = entry
        texture = f"{spec.mod_id}:block/{block.identifier}"
        return [
            write_json(blockstates / f"{block.identifier}.json", {"variants": variants}),
            write_json(block_models / f"{block.identifier}.json", {"parent": "minecraft:block/button", "textures": {"texture": texture}}),
            write_json(block_models / f"{block.identifier}_pressed.json", {"parent": "minecraft:block/button_pressed", "textures": {"texture": texture}}),
            write_json(block_models / f"{block.identifier}_inventory.json", {"parent": "minecraft:block/button_inventory", "textures": {"texture": texture}}),
            write_json(item_models / f"{block.identifier}.json", {"parent": f"{spec.mod_id}:block/{block.identifier}_inventory"}),
        ]

    def _pressure_plate_assets(self, blockstates: Path, block_models: Path, item_models: Path, spec: ModSpec, block: BlockSpec) -> list[Path]:
        texture = f"{spec.mod_id}:block/{block.identifier}"
        return [
            write_json(blockstates / f"{block.identifier}.json", {"variants": {"powered=false": {"model": f"{spec.mod_id}:block/{block.identifier}"}, "powered=true": {"model": f"{spec.mod_id}:block/{block.identifier}_down"}}}),
            write_json(block_models / f"{block.identifier}.json", {"parent": "minecraft:block/pressure_plate_up", "textures": {"texture": texture}}),
            write_json(block_models / f"{block.identifier}_down.json", {"parent": "minecraft:block/pressure_plate_down", "textures": {"texture": texture}}),
            write_json(item_models / f"{block.identifier}.json", {"parent": f"{spec.mod_id}:block/{block.identifier}"}),
        ]

    def _fence_assets(self, blockstates: Path, block_models: Path, item_models: Path, spec: ModSpec, block: BlockSpec) -> list[Path]:
        multipart: list[dict[str, Any]] = [
            {"apply": {"model": f"{spec.mod_id}:block/{block.identifier}_post"}},
        ]
        rotations = {"north": 0, "east": 90, "south": 180, "west": 270}
        for direction, y in rotations.items():
            multipart.append({"when": {direction: "true"}, "apply": {"model": f"{spec.mod_id}:block/{block.identifier}_side", "y": y, "uvlock": True}})
        texture = f"{spec.mod_id}:block/{block.identifier}"
        return [
            write_json(blockstates / f"{block.identifier}.json", {"multipart": multipart}),
            write_json(block_models / f"{block.identifier}.json", {"parent": "minecraft:block/fence_inventory", "textures": {"texture": texture}}),
            write_json(block_models / f"{block.identifier}_post.json", {"parent": "minecraft:block/fence_post", "textures": {"texture": texture}}),
            write_json(block_models / f"{block.identifier}_side.json", {"parent": "minecraft:block/fence_side", "textures": {"texture": texture}}),
            write_json(item_models / f"{block.identifier}.json", {"parent": f"{spec.mod_id}:block/{block.identifier}"}),
        ]

    def _fence_gate_assets(self, blockstates: Path, block_models: Path, item_models: Path, spec: ModSpec, block: BlockSpec) -> list[Path]:
        variants: dict[str, dict[str, Any]] = {}
        y_rotations = {"north": 180, "east": 270, "south": 0, "west": 90}
        for facing, y in y_rotations.items():
            for in_wall in ("false", "true"):
                for open_value in ("false", "true"):
                    for powered in ("false", "true"):
                        suffix = "_wall" if in_wall == "true" else ""
                        suffix += "_open" if open_value == "true" else ""
                        variants[f"facing={facing},in_wall={in_wall},open={open_value},powered={powered}"] = {
                            "model": f"{spec.mod_id}:block/{block.identifier}{suffix}",
                            "y": y,
                            "uvlock": True,
                        }
        texture = f"{spec.mod_id}:block/{block.identifier}"
        return [
            write_json(blockstates / f"{block.identifier}.json", {"variants": variants}),
            write_json(block_models / f"{block.identifier}.json", {"parent": "minecraft:block/template_fence_gate", "textures": {"texture": texture}}),
            write_json(block_models / f"{block.identifier}_open.json", {"parent": "minecraft:block/template_fence_gate_open", "textures": {"texture": texture}}),
            write_json(block_models / f"{block.identifier}_wall.json", {"parent": "minecraft:block/template_fence_gate_wall", "textures": {"texture": texture}}),
            write_json(block_models / f"{block.identifier}_wall_open.json", {"parent": "minecraft:block/template_fence_gate_wall_open", "textures": {"texture": texture}}),
            write_json(item_models / f"{block.identifier}.json", {"parent": f"{spec.mod_id}:block/{block.identifier}"}),
        ]

    def _door_assets(self, blockstates: Path, block_models: Path, item_models: Path, spec: ModSpec, block: BlockSpec) -> list[Path]:
        variants: dict[str, dict[str, Any]] = {}
        y_rotations = {"north": 0, "east": 90, "south": 180, "west": 270}
        for facing, y in y_rotations.items():
            for half in ("lower", "upper"):
                for hinge in ("left", "right"):
                    for open_value in ("false", "true"):
                        for powered in ("false", "true"):
                            model_suffix = f"{'top' if half == 'upper' else 'bottom'}_{hinge}"
                            if open_value == "true":
                                model_suffix += "_open"
                            variants[f"facing={facing},half={half},hinge={hinge},open={open_value},powered={powered}"] = {
                                "model": f"{spec.mod_id}:block/{block.identifier}_{model_suffix}",
                                "y": y,
                            }
        texture = f"{spec.mod_id}:block/{block.identifier}"
        out = [write_json(blockstates / f"{block.identifier}.json", {"variants": variants})]
        for half in ("bottom", "top"):
            for hinge in ("left", "right"):
                for open_suffix in ("", "_open"):
                    suffix = f"{half}_{hinge}{open_suffix}"
                    parent = f"minecraft:block/door_{suffix}"
                    out.append(write_json(block_models / f"{block.identifier}_{suffix}.json", {"parent": parent, "textures": {"bottom": texture, "top": texture}}))
        out.append(write_json(block_models / f"{block.identifier}.json", {"parent": f"{spec.mod_id}:block/{block.identifier}_bottom_left"}))
        out.append(write_json(item_models / f"{block.identifier}.json", {"parent": "minecraft:item/generated", "textures": {"layer0": texture}}))
        return out

    def _trapdoor_assets(self, blockstates: Path, block_models: Path, item_models: Path, spec: ModSpec, block: BlockSpec) -> list[Path]:
        variants: dict[str, dict[str, Any]] = {}
        y_rotations = {"north": 180, "east": 270, "south": 0, "west": 90}
        for facing, y in y_rotations.items():
            for half in ("bottom", "top"):
                for open_value in ("false", "true"):
                    for powered in ("false", "true"):
                        for waterlogged in ("false", "true"):
                            suffix = "_open" if open_value == "true" else f"_{half}"
                            variants[f"facing={facing},half={half},open={open_value},powered={powered},waterlogged={waterlogged}"] = {
                                "model": f"{spec.mod_id}:block/{block.identifier}{suffix}",
                                "y": y,
                            }
        texture = f"{spec.mod_id}:block/{block.identifier}"
        return [
            write_json(blockstates / f"{block.identifier}.json", {"variants": variants}),
            write_json(block_models / f"{block.identifier}.json", {"parent": f"{spec.mod_id}:block/{block.identifier}_bottom"}),
            write_json(block_models / f"{block.identifier}_bottom.json", {"parent": "minecraft:block/template_trapdoor_bottom", "textures": {"texture": texture}}),
            write_json(block_models / f"{block.identifier}_top.json", {"parent": "minecraft:block/template_trapdoor_top", "textures": {"texture": texture}}),
            write_json(block_models / f"{block.identifier}_open.json", {"parent": "minecraft:block/template_trapdoor_open", "textures": {"texture": texture}}),
            write_json(item_models / f"{block.identifier}.json", {"parent": f"{spec.mod_id}:block/{block.identifier}_bottom"}),
        ]

    def _item_model(self, root: Path, spec: ModSpec, item: ItemSpec) -> Path:
        return write_json(root / f"{item.identifier}.json", {"parent": "minecraft:item/generated", "textures": {"layer0": f"{spec.mod_id}:item/{item.identifier}"}})

    def _item_definition(self, root: Path, spec: ModSpec, identifier: str) -> Path:
        return write_json(
            root / f"{identifier}.json",
            {"model": {"type": "minecraft:model", "model": f"{spec.mod_id}:item/{identifier}"}},
        )

    def _item_texture(self, root: Path, item: ItemSpec) -> Path:
        color = self._color(item)
        if item.behavior is not None:
            if self._behavior_has_action(item, "heal"):
                pixels = self._heal_icon(color)
            elif self._behavior_has_action(item, "apply_effect"):
                pixels = self._effect_icon(color)
            else:
                pixels = self._gem_icon(color)
        else:
            pixels = self._gem_icon(color)
        return self._png(root / f"{item.identifier}.png", pixels)

    def _item_texture_kind(self, item: ItemSpec) -> str:
        if item.behavior is None:
            return "gem"
        if self._behavior_has_action(item, "heal"):
            return "heal_badge"
        if self._behavior_has_action(item, "apply_effect"):
            return "effect_crystal"
        return "gem"

    def _behavior_has_action(self, item: ItemSpec, action_type: str) -> bool:
        if item.behavior is None:
            return False
        if action_type == "heal" and item.behavior.behavior_type == "right_click_heal":
            return True
        if action_type == "apply_effect" and item.behavior.behavior_type == "right_click_effect":
            return True
        return any(action.action_type == action_type for event in item.behavior.events for action in event.actions)

    def _food_texture(self, root: Path, item: FoodSpec) -> Path:
        return self._png(root / f"{item.identifier}.png", self._apple_icon(self._color(item)))

    def _sword_texture(self, root: Path, item: SwordSpec) -> Path:
        return self._png(root / f"{item.identifier}.png", self._sword_icon(self._color(item)))

    def _tool_texture(self, root: Path, item: ToolSpec) -> Path:
        return self._png(root / f"{item.identifier}.png", self._tool_icon(self._color(item), item.tool_type))

    def _armor_texture(self, root: Path, item: ArmorSpec) -> Path:
        return self._png(root / f"{item.identifier}.png", self._armor_icon(self._color(item), item.armor_type))

    def _block_texture(self, root: Path, block: BlockSpec) -> Path:
        if isinstance(block, OreSpec):
            pixels = self._ore_block(self._color(block))
        elif isinstance(block, MachineSpec):
            pixels = self._machine_block(self._color(block))
        else:
            pixels = self._solid_block(self._color(block))
        return self._png(root / f"{block.identifier}.png", pixels)

    def _entity_texture(self, root: Path, entity: EntitySpec) -> Path:
        return self._png(root / f"{entity.identifier}.png", self._mob_icon(self._color(entity)))

    def _shaped(self, recipe: RecipeSpec) -> dict:
        return {"type": "minecraft:crafting_shaped", "category": recipe.category, **({"group": recipe.group} if recipe.group else {}), "pattern": recipe.pattern, "key": dict(recipe.keys), "result": {"id": recipe.result, "count": recipe.count}}

    def _shapeless(self, recipe: RecipeSpec) -> dict:
        return {"type": "minecraft:crafting_shapeless", "category": recipe.category, **({"group": recipe.group} if recipe.group else {}), "ingredients": list(recipe.ingredients), "result": {"id": recipe.result, "count": recipe.count}}

    def _drop_table(self, item_name: str) -> dict:
        return {"type": "minecraft:block", "pools": [{"rolls": 1, "entries": [{"type": "minecraft:item", "name": item_name}], "conditions": [{"condition": "minecraft:survives_explosion"}]}]}

    def _entity_loot_table(self, entity: EntitySpec) -> dict:
        pools = []
        for drop in entity.drops:
            pools.append({"rolls": 1, "entries": [self._entity_drop_entry(drop)]})
        return {"type": "minecraft:entity", "pools": pools}

    def _entity_drop_entry(self, drop: EntityDropSpec) -> dict:
        entry: dict[str, Any] = {"type": "minecraft:item", "name": drop.item}
        functions = []
        if drop.min_count != 1 or drop.max_count != 1:
            functions.append(
                {
                    "function": "minecraft:set_count",
                    "count": {
                        "type": "minecraft:uniform",
                        "min": drop.min_count,
                        "max": drop.max_count,
                    },
                }
            )
        if functions:
            entry["functions"] = functions
        if drop.chance < 1.0:
            entry["conditions"] = [{"condition": "minecraft:random_chance", "chance": drop.chance}]
        return entry

    def _entity_spawn_modifier(self, spec: ModSpec, entity: EntitySpec) -> dict:
        spawn = entity.spawn
        if spawn is None:
            return {}
        return {
            "type": "neoforge:add_spawns",
            "biomes": spawn.biomes,
            "spawners": [
                {
                    "type": f"{spec.mod_id}:{entity.identifier}",
                    "weight": spawn.weight,
                    "minCount": spawn.min_count,
                    "maxCount": spawn.max_count,
                }
            ],
        }

    def _block_tags(self, resources_dir: Path, spec: ModSpec) -> list[Path]:
        out: list[Path] = []
        blocks = [f"{spec.mod_id}:{b.identifier}" for b in [*spec.blocks, *spec.machines, *spec.ores] if b.requires_correct_tool]
        if not blocks:
            return out
        root = ensure_directory(resources_dir / "data" / "minecraft" / "tags" / "block")
        out.append(write_json(ensure_directory(root / "mineable") / "pickaxe.json", {"replace": False, "values": blocks}))
        tiers = {"stone": [], "iron": [], "diamond": []}
        for block in [*spec.blocks, *spec.machines, *spec.ores]:
            if not block.requires_correct_tool:
                continue
            tier = self._normalize_tier(block.tool_tier)
            tiers[tier].append(f"{spec.mod_id}:{block.identifier}")
        for tier, values in tiers.items():
            if values:
                out.append(write_json(root / f"needs_{tier}_tool.json", {"replace": False, "values": values}))
        return out

    def _texture_manifest(self, layout: ProjectLayout, spec: ModSpec, records: list[dict[str, Any]]) -> Path:
        return write_json(
            layout.project_dir / ".agent" / "texture-manifest.json",
            {
                "version": 1,
                "generator": "procedural_16x16_rgba",
                "mod_id": spec.mod_id,
                "textures": records,
            },
        )

    def _texture_record(
        self,
        layout: ProjectLayout,
        feature_type: str,
        identifier: str,
        path: Path,
        template: str,
        base_color: tuple[int, int, int, int],
    ) -> dict[str, Any]:
        return {
            "type": feature_type,
            "id": identifier,
            "path": str(path.relative_to(layout.project_dir)),
            "template": template,
            "quality_profile": self._texture_profile(feature_type, template),
            "dominant_rgba": list(base_color),
            "palette": {
                "shadow": self._hex(self._shift(base_color, -45)),
                "base": self._hex(base_color),
                "highlight": self._hex(self._shift(base_color, 40)),
            },
            "width": 16,
            "height": 16,
            "color_type": "rgba",
        }

    def _texture_profile(self, feature_type: str, template: str) -> dict[str, Any]:
        base_profiles: dict[str, dict[str, str]] = {
            "gem": {
                "profile_id": "gem_cut",
                "silhouette": "faceted_item",
                "shading": "outline_shadow_highlight",
                "detail": "white sparkle pixels",
            },
            "heal_badge": {
                "profile_id": "utility_badge",
                "silhouette": "square_badge",
                "shading": "clean panel with colored cross",
                "detail": "first-aid readable at 16px",
            },
            "effect_crystal": {
                "profile_id": "effect_crystal",
                "silhouette": "diamond_crystal",
                "shading": "radial crystal contrast",
                "detail": "six sparkle anchors",
            },
            "apple": {
                "profile_id": "food_icon",
                "silhouette": "round_food",
                "shading": "organic highlight",
                "detail": "stem and leaf",
            },
            "sword": {
                "profile_id": "weapon_icon",
                "silhouette": "vertical_blade",
                "shading": "edge_core_shadow",
                "detail": "hilt and pommel",
            },
            "solid_block": {
                "profile_id": "tiling_block",
                "silhouette": "full_tile",
                "shading": "checker and border contrast",
                "detail": "repeatable pixel texture",
            },
            "ore_block": {
                "profile_id": "ore_embedded",
                "silhouette": "full_tile",
                "shading": "stone base plus ore highlight",
                "detail": "distributed ore flecks",
            },
            "machine_block": {
                "profile_id": "machine_face",
                "silhouette": "front_panel",
                "shading": "metal frame and energy strip",
                "detail": "screen slot and corner bolts",
            },
            "mob_face": {
                "profile_id": "mob_portrait",
                "silhouette": "head_icon",
                "shading": "face highlight and jaw shadow",
                "detail": "eyes and horns",
            },
        }
        if template.startswith("tool_"):
            profile = {
                "profile_id": "tool_icon",
                "silhouette": template.replace("tool_", ""),
                "shading": "metal head with wooden handle",
                "detail": "tool-type specific head",
            }
        elif template.startswith("armor_"):
            profile = {
                "profile_id": "armor_icon",
                "silhouette": template.replace("armor_", ""),
                "shading": "rim shadow and material highlight",
                "detail": "armor-slot readable shape",
            }
        else:
            profile = dict(base_profiles.get(template, base_profiles["gem"]))
        profile["feature_type"] = feature_type
        profile["resolution"] = "16x16"
        profile["quality_gate"] = "valid_png_profiled"
        return profile

    def _model_variant_record(self, layout: ProjectLayout, block: BlockSpec, paths: list[Path]) -> dict[str, Any]:
        model_files = [
            str(path.relative_to(layout.project_dir))
            for path in paths
            if "models" in path.parts and path.suffix == ".json"
        ]
        blockstate_files = [
            str(path.relative_to(layout.project_dir))
            for path in paths
            if "blockstates" in path.parts and path.suffix == ".json"
        ]
        kind = block.block_kind.lower()
        roles = {
            "cube": ["cube_all"],
            "stairs": ["straight", "inner", "outer", "top_bottom_state"],
            "slab": ["bottom", "top", "double"],
            "wall": ["post", "side", "side_tall", "inventory"],
            "button": ["wall_floor_ceiling", "pressed", "inventory"],
            "pressure_plate": ["up", "down"],
            "fence": ["post", "side", "inventory"],
            "fence_gate": ["closed", "open", "wall", "wall_open"],
            "door": ["bottom_top", "hinge_left_right", "open_closed"],
            "trapdoor": ["bottom", "top", "open"],
        }.get(kind, [kind or "cube"])
        return {
            "id": block.identifier,
            "type": "ore" if isinstance(block, OreSpec) else "machine" if isinstance(block, MachineSpec) else "block",
            "block_kind": block.block_kind,
            "base_block": block.base_block,
            "variant_roles": roles,
            "variant_count": len(model_files),
            "model_files": model_files,
            "blockstate_files": blockstate_files,
        }

    def _texture_atlas(self, layout: ProjectLayout, records: list[dict[str, Any]]) -> Path:
        cell = 20
        columns = min(8, max(1, len(records)))
        rows_count = max(1, (len(records) + columns - 1) // columns)
        width = columns * cell
        height = rows_count * cell
        pixels = [[(240, 236, 224, 255) for _ in range(width)] for _ in range(height)]
        for y in range(height):
            for x in range(width):
                if (x // 4 + y // 4) % 2 == 0:
                    pixels[y][x] = (222, 218, 207, 255)
        if not records:
            for i in range(min(width, height)):
                pixels[i][i] = (126, 126, 138, 255)
            return self._png(layout.project_dir / ".agent" / "texture-atlas.png", pixels)
        for index, record in enumerate(records):
            column = index % columns
            row = index // columns
            x0 = column * cell + 2
            y0 = row * cell + 2
            texture_rows = self._read_png_rgba(layout.project_dir / str(record.get("path", "")))
            if not texture_rows:
                base = tuple(record.get("dominant_rgba", [126, 126, 138, 255]))  # type: ignore[arg-type]
                texture_rows = self._swatch_icon((int(base[0]), int(base[1]), int(base[2]), int(base[3])))
            for y, texture_row in enumerate(texture_rows[:16]):
                for x, color in enumerate(texture_row[:16]):
                    pixels[y0 + y][x0 + x] = color
            border = (65, 74, 84, 255)
            for x in range(x0 - 1, x0 + 17):
                pixels[y0 - 1][x] = border
                pixels[y0 + 16][x] = border
            for y in range(y0 - 1, y0 + 17):
                pixels[y][x0 - 1] = border
                pixels[y][x0 + 16] = border
        return self._png(layout.project_dir / ".agent" / "texture-atlas.png", pixels)

    def _resource_quality_reports(
        self,
        layout: ProjectLayout,
        spec: ModSpec,
        texture_records: list[dict[str, Any]],
        model_records: list[dict[str, Any]],
        structure_previews: list[dict[str, Any]],
        texture_atlas: Path,
    ) -> list[Path]:
        profile_counts: dict[str, int] = {}
        for record in texture_records:
            profile = record.get("quality_profile", {})
            profile_id = str(profile.get("profile_id", record.get("template", "unknown"))) if isinstance(profile, dict) else str(record.get("template", "unknown"))
            profile_counts[profile_id] = profile_counts.get(profile_id, 0) + 1
        texture_types = sorted({str(record.get("type", "")) for record in texture_records if record.get("type")})
        variant_count = sum(int(record.get("variant_count", 0) or 0) for record in model_records)
        atlas_path = str(texture_atlas.relative_to(layout.project_dir))
        report = {
            "version": 8,
            "generator": "deterministic_resource_quality_v8",
            "mod_id": spec.mod_id,
            "summary": {
                "textures": len(texture_records),
                "texture_types": texture_types,
                "texture_profiles": profile_counts,
                "model_variant_blocks": len(model_records),
                "model_variants": variant_count,
                "structure_previews": len(structure_previews),
                "dashboard_ready": True,
            },
            "preview_artifacts": {
                "texture_atlas": {
                    "path": atlas_path,
                    "texture_count": len(texture_records),
                    "cell_size": 20,
                    "purpose": "static dashboard preview",
                }
            },
            "texture_profiles": texture_records,
            "model_variants": model_records,
            "structure_previews": structure_previews,
            "quality_notes": [
                "Textures are still deterministic 16x16 PNG assets, but each asset now carries a profile describing silhouette, shading, palette, and intended readability.",
                "The atlas and structure preview PNGs are portfolio/dashboard evidence, not in-game runtime dependencies.",
                "Structure previews are schematic top-down thumbnails, not NBT or full rendered builds.",
            ],
            "next_art_upgrade_hooks": [
                "Replace a texture profile with an authored or AI-generated source while keeping the same manifest path.",
                "Add model-specific variants for stateful blocks by extending block_kind templates.",
                "Swap schematic structure preview PNGs for real structure screenshots once NBT structure generation exists.",
            ],
        }
        report_path = write_json(layout.project_dir / ".agent" / "resource-quality-report.json", report)
        return [report_path, self._resource_quality_markdown(layout, report)]

    def _resource_quality_markdown(self, layout: ProjectLayout, report: dict[str, Any]) -> Path:
        summary = report["summary"]
        lines = [
            "# Resource Quality Report",
            "",
            f"Mod ID: `{report['mod_id']}`",
            f"Generator: `{report['generator']}`",
            "",
            "## Summary",
            "",
            f"- textures: `{summary['textures']}`",
            f"- texture types: `{', '.join(summary['texture_types']) or 'none'}`",
            f"- model variant blocks: `{summary['model_variant_blocks']}`",
            f"- model variants: `{summary['model_variants']}`",
            f"- structure previews: `{summary['structure_previews']}`",
            f"- texture atlas: `{report['preview_artifacts']['texture_atlas']['path']}`",
            "",
            "## Texture Profiles",
            "",
        ]
        for profile, count in sorted(summary["texture_profiles"].items()):
            lines.append(f"- `{profile}`: `{count}`")
        lines.extend(["", "## Model Variants", ""])
        for record in report["model_variants"]:
            lines.append(f"- `{record['id']}` `{record['block_kind']}`: `{record['variant_count']}` model file(s)")
        if report["structure_previews"]:
            lines.extend(["", "## Structure Previews", ""])
            for preview in report["structure_previews"]:
                lines.append(f"- `{preview['id']}`: `{preview['path']}`")
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in report["quality_notes"])
        lines.append("")
        return write_text(layout.project_dir / ".agent" / "resource-quality-report.md", "\n".join(lines))

    def _structure_preview(self, root: Path, structure: WorldStructureSpec) -> Path:
        size = 64
        base = self._structure_color(structure.identifier)
        floor = self._shift(base, -45)
        wall = self._shift(base, 20)
        accent = self._shift(base, 60)
        chest = (214, 157, 54, 255)
        pixels = [[(34, 44, 39, 255) for _ in range(size)] for _ in range(size)]
        for y in range(4, 60):
            for x in range(4, 60):
                if (x // 8 + y // 8) % 2 == 0:
                    pixels[y][x] = floor
                else:
                    pixels[y][x] = self._shift(floor, 16)
        for x in range(10, 54):
            for y in (10, 11, 52, 53):
                pixels[y][x] = wall
        for y in range(10, 54):
            for x in (10, 11, 52, 53):
                pixels[y][x] = wall
        for y in range(20, 44):
            for x in range(20, 44):
                if x in (20, 43) or y in (20, 43):
                    pixels[y][x] = accent
        for y in range(28, 36):
            for x in range(28, 36):
                pixels[y][x] = chest
        for x in range(28, 36):
            pixels[31][x] = self._shift(chest, -70)
        for x, y in ((16, 16), (47, 16), (16, 47), (47, 47)):
            for yy in range(y - 2, y + 3):
                for xx in range(x - 2, x + 3):
                    pixels[yy][xx] = self._shift(wall, 30)
        return self._png(root / f"{structure.identifier}.png", pixels)

    def _structure_preview_record(self, layout: ProjectLayout, structure: WorldStructureSpec, path: Path) -> dict[str, Any]:
        return {
            "id": structure.identifier,
            "structure_kind": structure.structure_kind,
            "path": str(path.relative_to(layout.project_dir)),
            "width": 64,
            "height": 64,
            "projection": "top_down_schematic",
            "biomes": structure.biomes,
            "loot_table": structure.loot_table,
        }

    def _read_png_rgba(self, path: Path) -> list[list[tuple[int, int, int, int]]]:
        try:
            data = path.read_bytes()
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                return []
            offset = 8
            width = height = 0
            payload = b""
            while offset + 8 <= len(data):
                length = struct.unpack(">I", data[offset : offset + 4])[0]
                kind = data[offset + 4 : offset + 8]
                chunk = data[offset + 8 : offset + 8 + length]
                offset += 12 + length
                if kind == b"IHDR":
                    width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", chunk)
                    if bit_depth != 8 or color_type != 6:
                        return []
                elif kind == b"IDAT":
                    payload += chunk
                elif kind == b"IEND":
                    break
            if not width or not height or not payload:
                return []
            raw = zlib.decompress(payload)
            rows: list[list[tuple[int, int, int, int]]] = []
            stride = width * 4
            cursor = 0
            for _ in range(height):
                if raw[cursor] != 0:
                    return []
                cursor += 1
                row_bytes = raw[cursor : cursor + stride]
                cursor += stride
                rows.append([tuple(row_bytes[i : i + 4]) for i in range(0, len(row_bytes), 4)])  # type: ignore[list-item]
            return rows
        except (OSError, ValueError, zlib.error, struct.error, IndexError):
            return []

    def _swatch_icon(self, base: tuple[int, int, int, int]) -> list[list[tuple[int, int, int, int]]]:
        rows = self._empty()
        for y in range(16):
            for x in range(16):
                rows[y][x] = self._shift(base, 35) if x < 8 and y < 8 else self._shift(base, -35) if x > 7 and y > 7 else base
        return rows

    def _structure_color(self, identifier: str) -> tuple[int, int, int, int]:
        total = sum(ord(char) for char in identifier)
        return (100 + total % 90, 78 + (total // 3) % 90, 88 + (total // 7) % 90, 255)

    def _hex(self, color: tuple[int, int, int, int]) -> str:
        r, g, b, _ = color
        return f"#{r:02x}{g:02x}{b:02x}"

    def _normalize_tier(self, tier: str) -> str:
        value = tier.lower()
        if value in {"netherite", "diamond"}:
            return "diamond"
        if value in {"iron", "copper"}:
            return "iron"
        return "stone"

    def _item_lang(self, spec: ModSpec, item: ItemSpec | FoodSpec | SwordSpec | ToolSpec | ArmorSpec, en: dict[str, str], zh: dict[str, str]) -> None:
        key = f"item.{spec.mod_id}.{item.identifier}"
        en[key] = item.display_name_en_us
        zh[key] = item.localized_name("zh_cn")

    def _block_lang(self, spec: ModSpec, block: BlockSpec, en: dict[str, str], zh: dict[str, str]) -> None:
        key = f"block.{spec.mod_id}.{block.identifier}"
        en[key] = block.display_name_en_us
        zh[key] = block.localized_name("zh_cn")

    def _entity_lang(self, spec: ModSpec, entity: EntitySpec, en: dict[str, str], zh: dict[str, str]) -> None:
        key = f"entity.{spec.mod_id}.{entity.identifier}"
        en[key] = entity.display_name_en_us
        zh[key] = entity.localized_name("zh_cn")

    def _color(self, feature: ItemSpec | BlockSpec | EntitySpec) -> tuple[int, int, int, int]:
        label = f"{feature.identifier} {feature.display_name} {feature.display_name_zh_cn}".lower()
        if self._has_keyword(label, ("ruby", "\u7ea2\u5b9d\u77f3")):
            return (189, 36, 79, 255)
        if self._has_keyword(label, ("speed", "\u901f\u5ea6")):
            return (76, 198, 255, 255)
        if self._has_keyword(label, ("apple", "\u82f9\u679c")):
            return (198, 56, 52, 255)
        if self._has_keyword(label, ("emerald", "\u7eff\u5b9d\u77f3", "\u7fe1\u7fe0")):
            return (44, 178, 92, 255)
        return (126, 126, 138, 255)

    def _has_keyword(self, label: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in label for keyword in keywords)

    def _gem_icon(self, base: tuple[int, int, int, int]) -> list[list[tuple[int, int, int, int]]]:
        rows = self._empty()
        outline, shadow, light = self._shift(base, -70), self._shift(base, -35), self._shift(base, 35)
        for y in range(2, 14):
            for x in range(2, 14):
                rows[y][x] = outline if x in (2, 13) or y in (2, 13) else (light if x + y < 9 else shadow if x + y > 18 else base)
        for x, y in ((5, 5), (10, 6), (8, 9)):
            rows[y][x] = (255, 255, 255, 255)
        return rows

    def _heal_icon(self, base: tuple[int, int, int, int]) -> list[list[tuple[int, int, int, int]]]:
        rows = self._empty()
        border, panel, cross = (98, 107, 116, 255), (242, 245, 247, 255), self._shift(base, 10)
        for y in range(2, 14):
            for x in range(2, 14):
                rows[y][x] = border if x in (2, 13) or y in (2, 13) else panel
        for y in range(5, 11):
            for x in range(6, 10):
                rows[y][x] = cross
        for y in range(6, 10):
            for x in range(4, 12):
                rows[y][x] = cross
        rows[5][7] = self._shift(base, 45)
        rows[6][6] = self._shift(base, 45)
        return rows

    def _effect_icon(self, base: tuple[int, int, int, int]) -> list[list[tuple[int, int, int, int]]]:
        rows = self._empty()
        dark, mid, light = self._shift(base, -60), self._shift(base, -10), self._shift(base, 35)
        for y in range(3, 13):
            for x in range(3, 13):
                rows[y][x] = dark if x in (3, 12) or y in (3, 12) else light if abs(x - 7.5) + abs(y - 7.5) < 6 else mid
        for x, y in ((7, 4), (10, 7), (7, 10), (4, 7), (9, 5), (5, 9)):
            rows[y][x] = (255, 255, 255, 255)
        return rows

    def _apple_icon(self, base: tuple[int, int, int, int]) -> list[list[tuple[int, int, int, int]]]:
        rows = self._empty()
        outline, shine, stem, leaf = self._shift(base, -55), self._shift(base, 28), (92, 160, 60, 255), (66, 191, 87, 255)
        for y in range(4, 14):
            for x in range(3, 13):
                if ((x - 7.5) ** 2) / 20 + ((y - 9) ** 2) / 18 <= 1.0:
                    rows[y][x] = outline if x in (3, 12) or y in (4, 13) else (shine if x < 7 and y < 9 else base)
        for y in range(1, 5):
            rows[y][7] = stem
            rows[y][8] = stem
        rows[2][9], rows[3][10] = leaf, leaf
        return rows

    def _sword_icon(self, base: tuple[int, int, int, int]) -> list[list[tuple[int, int, int, int]]]:
        rows = self._empty()
        edge, core, shadow = self._shift(base, 45), self._shift(base, 10), self._shift(base, -45)
        hilt, pommel = (110, 74, 42, 255), (186, 158, 76, 255)
        for y in range(1, 11):
            rows[y][7], rows[y][8] = edge, core
            if y > 2:
                rows[y][9] = shadow
        for x in range(4, 12):
            rows[11][x] = hilt if x not in (4, 11) else shadow
        for y in range(12, 15):
            rows[y][7] = hilt
            rows[y][8] = hilt
        rows[15][7], rows[15][8] = pommel, pommel
        return rows

    def _tool_icon(self, base: tuple[int, int, int, int], tool_type: str) -> list[list[tuple[int, int, int, int]]]:
        rows = self._empty()
        metal_light, metal, metal_dark = self._shift(base, 45), self._shift(base, 5), self._shift(base, -55)
        handle, handle_dark = (116, 76, 42, 255), (82, 50, 30, 255)
        for i in range(5, 15):
            x = i - 1
            rows[i][x] = handle
            if x + 1 < 16:
                rows[i][x + 1] = handle_dark

        normalized = tool_type.lower()
        if normalized == "axe":
            for y in range(1, 7):
                for x in range(8, 14):
                    if x + y < 18 and not (x == 13 and y in (5, 6)):
                        rows[y][x] = metal_dark if x in (8, 13) or y in (1, 6) else metal
            rows[2][9], rows[3][10] = metal_light, metal_light
        elif normalized == "shovel":
            for y in range(1, 7):
                for x in range(6, 11):
                    if ((x - 8) ** 2) / 6 + ((y - 4) ** 2) / 8 <= 1.0:
                        rows[y][x] = metal_dark if y == 6 else metal
            rows[2][8] = metal_light
        elif normalized == "hoe":
            for x in range(5, 13):
                rows[3][x] = metal_dark if x in (5, 12) else metal
                rows[4][x] = metal
            rows[5][11] = metal_dark
            rows[6][10] = metal
        else:
            for y in range(1, 7):
                for x in range(5, 12):
                    if abs(x - 8) + y < 9:
                        rows[y][x] = metal_dark if x in (5, 11) or y == 1 else metal
            rows[2][8], rows[3][7] = metal_light, metal_light
        return rows

    def _armor_icon(self, base: tuple[int, int, int, int], armor_type: str) -> list[list[tuple[int, int, int, int]]]:
        rows = self._empty()
        dark, mid, light = self._shift(base, -60), self._shift(base, -8), self._shift(base, 45)
        normalized = armor_type.lower()
        if normalized == "chestplate":
            for y in range(3, 14):
                for x in range(3, 13):
                    if x in (3, 12) or y in (3, 13) or (y < 6 and x in (5, 10)):
                        rows[y][x] = dark
                    elif not (y < 5 and 6 <= x <= 9):
                        rows[y][x] = light if x < 7 and y < 8 else mid
        elif normalized == "leggings":
            for y in range(3, 15):
                for x in (4, 5, 6, 9, 10, 11):
                    rows[y][x] = dark if x in (4, 11) or y in (3, 14) else mid
            for x in range(5, 11):
                rows[3][x] = dark
        elif normalized == "boots":
            for y in range(8, 14):
                for x in range(3, 7):
                    rows[y][x] = dark if x == 3 or y == 13 else mid
                for x in range(9, 13):
                    rows[y][x] = dark if x == 12 or y == 13 else mid
            for x in range(2, 7):
                rows[14][x] = dark
            for x in range(9, 14):
                rows[14][x] = dark
        else:
            for y in range(3, 10):
                for x in range(4, 12):
                    if y == 3 or x in (4, 11) or (y == 9 and x not in (6, 7, 8, 9)):
                        rows[y][x] = dark
                    elif not (y > 6 and 6 <= x <= 9):
                        rows[y][x] = light if x < 7 and y < 6 else mid
        return rows

    def _solid_block(self, base: tuple[int, int, int, int]) -> list[list[tuple[int, int, int, int]]]:
        light, dark, border = self._shift(base, 32), self._shift(base, -28), self._shift(base, -52)
        out: list[list[tuple[int, int, int, int]]] = []
        for y in range(16):
            row = []
            for x in range(16):
                if x in (0, 15) or y in (0, 15):
                    row.append(border)
                elif (x + y) % 4 < 2:
                    row.append(light)
                elif (x // 4 + y // 4) % 2 == 0:
                    row.append(base)
                else:
                    row.append(dark)
            out.append(row)
        return out

    def _ore_block(self, base: tuple[int, int, int, int]) -> list[list[tuple[int, int, int, int]]]:
        rows = self._solid_block((122, 122, 130, 255))
        light, shadow = self._shift(base, 40), self._shift(base, -35)
        for x, y in ((4, 4), (5, 5), (11, 5), (7, 8), (8, 8), (10, 11), (5, 12), (11, 12)):
            rows[y][x] = base
            if x + 1 < 15:
                rows[y][x + 1] = light
            if y + 1 < 15:
                rows[y + 1][x] = shadow
        return rows

    def _machine_block(self, base: tuple[int, int, int, int]) -> list[list[tuple[int, int, int, int]]]:
        rows = self._solid_block(self._shift(base, -12))
        frame, dark, light, energy = (54, 60, 69, 255), (28, 32, 38, 255), self._shift(base, 48), (65, 199, 242, 255)
        for y in range(2, 14):
            for x in range(2, 14):
                if x in (2, 13) or y in (2, 13):
                    rows[y][x] = frame
        for y in range(5, 11):
            for x in range(4, 12):
                rows[y][x] = dark
        for x in range(5, 11):
            rows[6][x] = light
            rows[9][x] = self._shift(base, 20)
        for y in range(4, 12):
            rows[y][12] = energy if y >= 8 else self._shift(energy, -70)
        rows[4][4], rows[4][11], rows[11][4], rows[11][11] = light, light, light, light
        return rows

    def _mob_icon(self, base: tuple[int, int, int, int]) -> list[list[tuple[int, int, int, int]]]:
        rows = self._empty()
        outline, shadow, light = self._shift(base, -70), self._shift(base, -28), self._shift(base, 38)
        eye, horn = (245, 248, 255, 255), (223, 194, 118, 255)
        for y in range(3, 14):
            for x in range(3, 13):
                if ((x - 7.5) ** 2) / 22 + ((y - 8.5) ** 2) / 26 <= 1.0:
                    rows[y][x] = outline if x in (3, 12) or y in (3, 13) else light if x < 7 and y < 8 else base
        for x, y in ((4, 2), (11, 2), (5, 3), (10, 3)):
            rows[y][x] = horn
        rows[7][5] = eye
        rows[7][10] = eye
        rows[8][5] = (20, 24, 30, 255)
        rows[8][10] = (20, 24, 30, 255)
        for x in range(6, 10):
            rows[11][x] = shadow
        rows[12][7] = outline
        rows[12][8] = outline
        return rows

    def _empty(self) -> list[list[tuple[int, int, int, int]]]:
        return [[(0, 0, 0, 0) for _ in range(16)] for _ in range(16)]

    def _shift(self, color: tuple[int, int, int, int], delta: int) -> tuple[int, int, int, int]:
        r, g, b, a = color
        return (max(0, min(255, r + delta)), max(0, min(255, g + delta)), max(0, min(255, b + delta)), a)

    def _png(self, path: Path, pixels: list[list[tuple[int, int, int, int]]]) -> Path:
        h = len(pixels)
        w = len(pixels[0]) if pixels else 0
        raw = [b"\x00" + b"".join(bytes(px) for px in row) for row in pixels]
        data = zlib.compress(b"".join(raw), level=9)
        png = b"".join([
            b"\x89PNG\r\n\x1a\n",
            self._chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)),
            self._chunk(b"IDAT", data),
            self._chunk(b"IEND", b""),
        ])
        ensure_directory(path.parent)
        path.write_bytes(png)
        return path

    def _chunk(self, kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind)
        crc = zlib.crc32(data, crc)
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc & 0xFFFFFFFF)

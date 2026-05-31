from __future__ import annotations

from pathlib import Path

from .behavior_generator import BehaviorGenerator
from .entity_generator import EntityGenerator
from .java_extension_generator import JavaExtensionGenerator
from .machine_generator import MachineGenerator
from .models import ArmorSpec, BlockSpec, FoodSpec, ItemSpec, ModSpec, OreSpec, SwordSpec, ToolSpec
from .project_generator import ProjectLayout
from .tools import upper_snake_case, write_text


class CodeGenerator:
    def generate(self, layout: ProjectLayout, spec: ModSpec) -> tuple[list[Path], list[str]]:
        behavior_result = BehaviorGenerator().generate(layout, spec)
        machine_generator = MachineGenerator()
        machine_result = machine_generator.generate(layout, spec)
        entity_generator = EntityGenerator()
        entity_result = entity_generator.generate(layout, spec)
        java_extension_result = JavaExtensionGenerator().generate(layout, spec)
        main_class_path = layout.package_dir / f"{layout.main_class_name}.java"
        warnings = [
            *self._warnings_for(spec),
            *behavior_result.warnings,
            *entity_result.warnings,
            *java_extension_result.warnings,
        ]
        extra_imports = sorted(
            {
                *behavior_result.import_lines,
                *machine_result.import_lines,
                *machine_generator.main_imports(spec),
                *entity_result.import_lines,
                *entity_generator.main_imports(spec),
            }
        )
        write_text(main_class_path, self._render_main_class(layout.main_class_name, spec, extra_imports))
        return [
            main_class_path,
            *behavior_result.java_files,
            *machine_result.java_files,
            *entity_result.java_files,
            *java_extension_result.artifacts,
        ], warnings

    def _warnings_for(self, spec: ModSpec) -> list[str]:
        warnings: list[str] = []
        for sword in spec.swords:
            if sword.tool_material.lower() not in {"wood", "stone", "copper", "iron", "diamond", "gold", "golden", "netherite", "ruby"}:
                warnings.append(
                    f"Sword '{sword.identifier}' requested unsupported tool_material '{sword.tool_material}', falling back to IRON."
                )
        for tool in spec.tools:
            if tool.tool_material.lower() not in {"wood", "stone", "copper", "iron", "diamond", "gold", "golden", "netherite", "ruby"}:
                warnings.append(
                    f"Tool '{tool.identifier}' requested unsupported tool_material '{tool.tool_material}', falling back to IRON."
                )
        for armor in spec.armors:
            if armor.armor_material.lower() not in {"leather", "chainmail", "chain", "copper", "iron", "diamond", "gold", "golden", "netherite", "ruby"}:
                warnings.append(
                    f"Armor '{armor.identifier}' requested unsupported armor_material '{armor.armor_material}', falling back to IRON."
                )
        return warnings

    def _render_main_class(self, class_name: str, spec: ModSpec, extra_imports: list[str]) -> str:
        behavior_generator = BehaviorGenerator()
        entity_generator = EntityGenerator()
        declarations: list[str] = []
        declarations.extend(self._render_block_declarations(block) for block in spec.blocks)
        declarations.extend(MachineGenerator().machine_declarations(machine) for machine in spec.machines)
        declarations.extend(entity_generator.entity_declarations(entity) for entity in spec.entities)
        declarations.extend(self._render_ore_declarations(ore) for ore in spec.ores)
        declarations.extend(self._render_item_declaration(item) for item in spec.items)
        declarations.extend(self._render_food_declaration(food) for food in spec.foods)
        declarations.extend(self._render_sword_declaration(sword) for sword in spec.swords)
        declarations.extend(self._render_tool_declaration(tool) for tool in spec.tools)
        declarations.extend(self._render_armor_declaration(armor) for armor in spec.armors)
        tab_section = self._render_tab_section(spec)

        sections = [
            f"package {spec.package_name};",
            "",
            "import org.slf4j.Logger;",
            "",
            "import com.mojang.logging.LogUtils;",
            "",
            "import net.minecraft.core.registries.Registries;",
            "import net.minecraft.network.chat.Component;",
            "import net.minecraft.world.food.FoodProperties;",
            "import net.minecraft.world.item.BlockItem;",
            "import net.minecraft.world.item.CreativeModeTab;",
            "import net.minecraft.world.item.CreativeModeTabs;",
            "import net.minecraft.world.item.DoubleHighBlockItem;",
            "import net.minecraft.world.item.Item;",
            "import net.minecraft.world.item.ToolMaterial;",
            "import net.minecraft.world.item.equipment.ArmorMaterial;",
            "import net.minecraft.world.item.equipment.ArmorMaterials;",
            "import net.minecraft.world.item.equipment.ArmorType;",
            "import net.minecraft.world.level.block.Block;",
            "import net.minecraft.world.level.block.Blocks;",
            "import net.minecraft.world.level.block.ButtonBlock;",
            "import net.minecraft.world.level.block.DoorBlock;",
            "import net.minecraft.world.level.block.FenceBlock;",
            "import net.minecraft.world.level.block.FenceGateBlock;",
            "import net.minecraft.world.level.block.PressurePlateBlock;",
            "import net.minecraft.world.level.block.SoundType;",
            "import net.minecraft.world.level.block.SlabBlock;",
            "import net.minecraft.world.level.block.StairBlock;",
            "import net.minecraft.world.level.block.TrapDoorBlock;",
            "import net.minecraft.world.level.block.WallBlock;",
            "import net.minecraft.world.level.block.state.properties.BlockSetType;",
            "import net.minecraft.world.level.block.state.properties.WoodType;",
            "import net.minecraft.world.level.material.MapColor;",
            "import net.neoforged.bus.api.IEventBus;",
            "import net.neoforged.fml.ModContainer;",
            "import net.neoforged.fml.common.Mod;",
            "import net.neoforged.neoforge.registries.DeferredBlock;",
            "import net.neoforged.neoforge.registries.DeferredHolder;",
            "import net.neoforged.neoforge.registries.DeferredItem;",
            "import net.neoforged.neoforge.registries.DeferredRegister;",
            *behavior_generator.food_effect_imports(spec),
            *extra_imports,
            "",
            f"@Mod({class_name}.MODID)",
            f"public final class {class_name} {{",
            f'    public static final String MODID = "{spec.mod_id}";',
            "    public static final Logger LOGGER = LogUtils.getLogger();",
            "    public static final DeferredRegister.Blocks BLOCKS = DeferredRegister.createBlocks(MODID);",
            "    public static final DeferredRegister.Items ITEMS = DeferredRegister.createItems(MODID);",
        ]

        if spec.machines:
            sections.extend(MachineGenerator().registry_declarations())
        if spec.entities:
            sections.extend(entity_generator.registry_declarations())

        if spec.all_content():
            sections.append(
                "    public static final DeferredRegister<CreativeModeTab> CREATIVE_MODE_TABS = DeferredRegister.create(Registries.CREATIVE_MODE_TAB, MODID);"
            )

        if declarations:
            sections.extend(["", *declarations])

        if tab_section:
            sections.extend(["", tab_section])

        sections.extend(
            [
                "",
                f"    public {class_name}(IEventBus modEventBus, ModContainer modContainer) {{",
                "        BLOCKS.register(modEventBus);",
                "        ITEMS.register(modEventBus);",
                *(MachineGenerator().constructor_registrations() if spec.machines else []),
                *(entity_generator.constructor_registrations() if spec.entities else []),
                *(["        CREATIVE_MODE_TABS.register(modEventBus);"] if spec.all_content() else []),
                '        LOGGER.info("Loading {}.", MODID);',
                "    }",
                "",
                *(entity_generator.attribute_registration_method(spec) if spec.entities else []),
                "    private static SoundType resolveSound(String name) {",
                "        return switch (name) {",
                '            case "metal" -> SoundType.METAL;',
                '            case "wood" -> SoundType.WOOD;',
                '            case "glass" -> SoundType.GLASS;',
                '            case "gravel" -> SoundType.GRAVEL;',
                '            case "sand" -> SoundType.SAND;',
                "            default -> SoundType.STONE;",
                "        };",
                "    }",
                "",
                "    private static ToolMaterial resolveToolMaterial(String name) {",
                "        return switch (name.toLowerCase()) {",
                '            case "wood", "wooden" -> ToolMaterial.WOOD;',
                '            case "stone" -> ToolMaterial.STONE;',
                '            case "copper" -> ToolMaterial.COPPER;',
                '            case "ruby" -> ToolMaterial.IRON;',
                '            case "diamond" -> ToolMaterial.DIAMOND;',
                '            case "gold", "golden" -> ToolMaterial.GOLD;',
                '            case "netherite" -> ToolMaterial.NETHERITE;',
                "            default -> ToolMaterial.IRON;",
                "        };",
                "    }",
                "",
                "    private static ArmorMaterial resolveArmorMaterial(String name) {",
                "        return switch (name.toLowerCase()) {",
                '            case "leather" -> ArmorMaterials.LEATHER;',
                '            case "chainmail", "chain" -> ArmorMaterials.CHAINMAIL;',
                '            case "copper" -> ArmorMaterials.COPPER;',
                '            case "ruby" -> ArmorMaterials.IRON;',
                '            case "diamond" -> ArmorMaterials.DIAMOND;',
                '            case "gold", "golden" -> ArmorMaterials.GOLD;',
                '            case "netherite" -> ArmorMaterials.NETHERITE;',
                "            default -> ArmorMaterials.IRON;",
                "        };",
                "    }",
                "}",
                "",
            ]
        )
        return "\n".join(sections)

    def _render_item_declaration(self, item: ItemSpec) -> str:
        behavior_declaration = BehaviorGenerator().item_registration(item)
        if behavior_declaration is not None:
            return behavior_declaration
        constant_name = upper_snake_case(item.identifier)
        return (
            f'    public static final DeferredItem<Item> {constant_name} = '
            f'ITEMS.registerSimpleItem("{item.identifier}", () -> new Item.Properties());'
        )

    def _render_food_declaration(self, food: FoodSpec) -> str:
        constant_name = upper_snake_case(food.identifier)
        if food.effects:
            consumable = BehaviorGenerator().food_effect_properties(food.effects)
            return (
                f'    public static final DeferredItem<Item> {constant_name} = '
                f'ITEMS.registerSimpleItem("{food.identifier}", properties -> properties.food(new FoodProperties.Builder()'
                f'.nutrition({food.nutrition}).saturationModifier({food.saturation:.2f}F).build(), {consumable}));'
            )
        return (
            f'    public static final DeferredItem<Item> {constant_name} = '
            f'ITEMS.registerSimpleItem("{food.identifier}", properties -> properties.food(new FoodProperties.Builder()'
            f'.nutrition({food.nutrition}).saturationModifier({food.saturation:.2f}F).build()));'
        )

    def _render_sword_declaration(self, sword: SwordSpec) -> str:
        behavior_declaration = BehaviorGenerator().sword_registration(sword)
        if behavior_declaration is not None:
            return behavior_declaration
        constant_name = upper_snake_case(sword.identifier)
        material_name = sword.tool_material.lower()
        return (
            f'    public static final DeferredItem<Item> {constant_name} = '
            f'ITEMS.registerSimpleItem("{sword.identifier}", properties -> properties.sword(resolveToolMaterial("{material_name}"), {sword.attack_damage_bonus:.2f}F, {sword.attack_speed:.2f}F));'
        )

    def _render_tool_declaration(self, tool: ToolSpec) -> str:
        constant_name = upper_snake_case(tool.identifier)
        material_name = tool.tool_material.lower()
        tool_method = self._tool_method(tool.tool_type)
        return (
            f'    public static final DeferredItem<Item> {constant_name} = '
            f'ITEMS.registerSimpleItem("{tool.identifier}", properties -> properties.{tool_method}(resolveToolMaterial("{material_name}"), {tool.attack_damage_bonus:.2f}F, {tool.attack_speed:.2f}F));'
        )

    def _render_armor_declaration(self, armor: ArmorSpec) -> str:
        constant_name = upper_snake_case(armor.identifier)
        material_name = armor.armor_material.lower()
        armor_type = self._armor_type_constant(armor.armor_type)
        return (
            f'    public static final DeferredItem<Item> {constant_name} = '
            f'ITEMS.registerSimpleItem("{armor.identifier}", properties -> properties.humanoidArmor(resolveArmorMaterial("{material_name}"), ArmorType.{armor_type}));'
        )

    def _tool_method(self, tool_type: str) -> str:
        normalized = tool_type.lower()
        return normalized if normalized in {"pickaxe", "axe", "shovel", "hoe"} else "pickaxe"

    def _armor_type_constant(self, armor_type: str) -> str:
        normalized = armor_type.lower()
        mapping = {
            "helmet": "HELMET",
            "chestplate": "CHESTPLATE",
            "leggings": "LEGGINGS",
            "boots": "BOOTS",
        }
        return mapping.get(normalized, "HELMET")

    def _render_block_declarations(self, block: BlockSpec) -> str:
        return self._render_common_block(block)

    def _render_ore_declarations(self, ore: OreSpec) -> str:
        return self._render_common_block(ore)

    def _render_common_block(self, block: BlockSpec) -> str:
        behavior_generator = BehaviorGenerator()
        constant_name = upper_snake_case(block.identifier)
        block_kind = block.block_kind.lower()
        java_class = behavior_generator.block_registration_class(block) or self._block_java_class(block_kind)
        constructor = self._block_constructor(block, block_kind)
        item_type = "DoubleHighBlockItem" if block_kind == "door" else "BlockItem"
        item_registration = (
            f'ITEMS.registerItem("{block.identifier}", properties -> new DoubleHighBlockItem({constant_name}.get(), properties));'
            if block_kind == "door"
            else f'ITEMS.registerSimpleBlockItem("{block.identifier}", {constant_name});'
        )
        return "\n".join(
            [
                f'    public static final DeferredBlock<{java_class}> {constant_name} = '
                f'BLOCKS.registerBlock("{block.identifier}", properties -> {constructor});',
                f'    public static final DeferredItem<{item_type}> {constant_name}_ITEM = '
                f'{item_registration}',
            ]
        )

    def _block_java_class(self, block_kind: str) -> str:
        return {
            "stairs": "StairBlock",
            "slab": "SlabBlock",
            "wall": "WallBlock",
            "button": "ButtonBlock",
            "pressure_plate": "PressurePlateBlock",
            "fence": "FenceBlock",
            "fence_gate": "FenceGateBlock",
            "door": "DoorBlock",
            "trapdoor": "TrapDoorBlock",
        }.get(block_kind, "Block")

    def _block_constructor(self, block: BlockSpec, block_kind: str) -> str:
        properties_chain = self._render_block_properties(block)
        behavior_class = BehaviorGenerator().block_registration_class(block)
        if behavior_class is not None:
            return f"new {behavior_class}({properties_chain})"
        if block_kind == "stairs":
            return f"new StairBlock(Blocks.STONE.defaultBlockState(), {properties_chain})"
        if block_kind == "slab":
            return f"new SlabBlock({properties_chain})"
        if block_kind == "wall":
            return f"new WallBlock({properties_chain})"
        if block_kind == "button":
            return f"new ButtonBlock(BlockSetType.STONE, 20, {properties_chain}.noCollision())"
        if block_kind == "pressure_plate":
            return f"new PressurePlateBlock(BlockSetType.STONE, {properties_chain}.noCollision())"
        if block_kind == "fence":
            return f"new FenceBlock({properties_chain})"
        if block_kind == "fence_gate":
            return f"new FenceGateBlock(WoodType.OAK, {properties_chain})"
        if block_kind == "door":
            return f"new DoorBlock(BlockSetType.IRON, {properties_chain}.noOcclusion())"
        if block_kind == "trapdoor":
            return f"new TrapDoorBlock(BlockSetType.IRON, {properties_chain}.noOcclusion())"
        return f"new Block({properties_chain})"

    def _render_block_properties(self, block: BlockSpec) -> str:
        chain = [
            "properties",
            ".mapColor(MapColor.STONE)",
            f".strength({block.strength:.2f}F, {block.resistance:.2f}F)",
            f'.sound(resolveSound("{block.sound.lower()}"))',
        ]
        if block.requires_correct_tool:
            chain.append(".requiresCorrectToolForDrops()")
        return "".join(chain)

    def _render_tab_section(self, spec: ModSpec) -> str:
        if not spec.all_content():
            return ""

        tab_constant = f"{upper_snake_case(spec.mod_id)}_TAB"
        tab_identifier = f"{spec.mod_id}_tab"
        icon_constant = self._tab_icon_constant(spec)
        display_lines = [
            *(f"                output.accept({upper_snake_case(block.identifier)}_ITEM.get());" for block in spec.blocks),
            *(f"                output.accept({upper_snake_case(machine.identifier)}_ITEM.get());" for machine in spec.machines),
            *(f"                output.accept({upper_snake_case(ore.identifier)}_ITEM.get());" for ore in spec.ores),
            *(f"                output.accept({upper_snake_case(item.identifier)}.get());" for item in spec.items),
            *(f"                output.accept({upper_snake_case(food.identifier)}.get());" for food in spec.foods),
            *(f"                output.accept({upper_snake_case(sword.identifier)}.get());" for sword in spec.swords),
            *(f"                output.accept({upper_snake_case(tool.identifier)}.get());" for tool in spec.tools),
            *(f"                output.accept({upper_snake_case(armor.identifier)}.get());" for armor in spec.armors),
        ]

        return "\n".join(
            [
                f"    public static final DeferredHolder<CreativeModeTab, CreativeModeTab> {tab_constant} = "
                f'CREATIVE_MODE_TABS.register("{tab_identifier}", () -> CreativeModeTab.builder()',
                f'            .title(Component.translatable("itemGroup.{spec.mod_id}"))',
                "            .withTabsBefore(CreativeModeTabs.COMBAT)",
                f"            .icon(() -> {icon_constant}.get().getDefaultInstance())",
                "            .displayItems((parameters, output) -> {",
                *display_lines,
                "            })",
                "            .build());",
            ]
        )

    def _tab_icon_constant(self, spec: ModSpec) -> str:
        if spec.items:
            return upper_snake_case(spec.items[0].identifier)
        if spec.foods:
            return upper_snake_case(spec.foods[0].identifier)
        if spec.swords:
            return upper_snake_case(spec.swords[0].identifier)
        if spec.tools:
            return upper_snake_case(spec.tools[0].identifier)
        if spec.armors:
            return upper_snake_case(spec.armors[0].identifier)
        if spec.blocks:
            return f"{upper_snake_case(spec.blocks[0].identifier)}_ITEM"
        if spec.machines:
            return f"{upper_snake_case(spec.machines[0].identifier)}_ITEM"
        return f"{upper_snake_case(spec.ores[0].identifier)}_ITEM"

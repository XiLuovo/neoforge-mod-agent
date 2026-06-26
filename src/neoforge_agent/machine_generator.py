from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .models import MachineSpec, ModSpec
from .project_generator import ProjectLayout
from .tools import pascal_case, upper_snake_case, write_text


@dataclass(slots=True)
class MachineGenerationResult:
    java_files: list[Path] = field(default_factory=list)
    import_lines: list[str] = field(default_factory=list)


class MachineGenerator:
    def generate(self, layout: ProjectLayout, spec: ModSpec) -> MachineGenerationResult:
        result = MachineGenerationResult()
        if not spec.machines:
            return result

        block_dir = layout.package_dir / "block"
        block_entity_dir = layout.package_dir / "block" / "entity"
        menu_dir = layout.package_dir / "menu"
        client_dir = layout.package_dir / "client"

        for machine in spec.machines:
            block_name = self.block_class_name(machine)
            block_entity_name = self.block_entity_class_name(machine)
            menu_name = self.menu_class_name(machine)
            screen_name = self.screen_class_name(machine)

            block_path = block_dir / f"{block_name}.java"
            block_entity_path = block_entity_dir / f"{block_entity_name}.java"
            menu_path = menu_dir / f"{menu_name}.java"
            screen_path = client_dir / f"{screen_name}.java"

            write_text(block_path, self._render_block_class(spec, machine))
            write_text(block_entity_path, self._render_block_entity_class(spec, machine))
            write_text(menu_path, self._render_menu_class(spec, machine))
            write_text(screen_path, self._render_screen_class(spec, machine))
            result.java_files.extend([block_path, block_entity_path, menu_path, screen_path])
            result.import_lines.extend(
                [
                    f"import {spec.package_name}.block.{block_name};",
                    f"import {spec.package_name}.block.entity.{block_entity_name};",
                    f"import {spec.package_name}.menu.{menu_name};",
                ]
            )

        client_path = client_dir / f"{layout.main_class_name}Client.java"
        write_text(client_path, self._render_client_class(layout.main_class_name, spec))
        result.java_files.append(client_path)
        return result

    def main_imports(self, spec: ModSpec) -> list[str]:
        if not spec.machines:
            return []
        return [
            "import net.minecraft.world.flag.FeatureFlags;",
            "import net.minecraft.world.inventory.MenuType;",
            "import net.minecraft.world.level.block.entity.BlockEntityType;",
        ]

    def registry_declarations(self) -> list[str]:
        return [
            "    public static final DeferredRegister<BlockEntityType<?>> BLOCK_ENTITY_TYPES = DeferredRegister.create(Registries.BLOCK_ENTITY_TYPE, MODID);",
            "    public static final DeferredRegister<MenuType<?>> MENU_TYPES = DeferredRegister.create(Registries.MENU, MODID);",
        ]

    def constructor_registrations(self) -> list[str]:
        return [
            "        BLOCK_ENTITY_TYPES.register(modEventBus);",
            "        MENU_TYPES.register(modEventBus);",
        ]

    def machine_declarations(self, machine: MachineSpec) -> str:
        constant_name = upper_snake_case(machine.identifier)
        block_name = self.block_class_name(machine)
        block_entity_name = self.block_entity_class_name(machine)
        menu_name = self.menu_class_name(machine)
        block_entity_constant = f"{constant_name}_BLOCK_ENTITY"
        menu_constant = f"{constant_name}_MENU"
        return "\n".join(
            [
                f'    public static final DeferredBlock<{block_name}> {constant_name} = ',
                f'            BLOCKS.registerBlock("{machine.identifier}", properties -> new {block_name}({self._machine_constructor_args(machine)}));',
                f'    public static final DeferredItem<BlockItem> {constant_name}_ITEM = ',
                f'            ITEMS.registerSimpleBlockItem("{machine.identifier}", {constant_name});',
                f'    public static final DeferredHolder<BlockEntityType<?>, BlockEntityType<{block_entity_name}>> {block_entity_constant} = ',
                f'            BLOCK_ENTITY_TYPES.register("{machine.identifier}", () -> new BlockEntityType<>({block_entity_name}::new, {constant_name}.get()));',
                f'    public static final DeferredHolder<MenuType<?>, MenuType<{menu_name}>> {menu_constant} = ',
                f'            MENU_TYPES.register("{machine.identifier}", () -> new MenuType<>({menu_name}::new, FeatureFlags.DEFAULT_FLAGS));',
            ]
        )

    def block_class_name(self, machine: MachineSpec) -> str:
        return pascal_case(machine.identifier) + "Block"

    def block_entity_class_name(self, machine: MachineSpec) -> str:
        return pascal_case(machine.identifier) + "BlockEntity"

    def menu_class_name(self, machine: MachineSpec) -> str:
        return pascal_case(machine.identifier) + "Menu"

    def screen_class_name(self, machine: MachineSpec) -> str:
        return pascal_case(machine.identifier) + "Screen"

    def _machine_constructor_args(self, machine: MachineSpec) -> str:
        return (
            "properties"
            ".mapColor(MapColor.STONE)"
            f".strength({machine.strength:.2f}F, {machine.resistance:.2f}F)"
            f'.sound(resolveSound("{machine.sound.lower()}"))'
            + (".requiresCorrectToolForDrops()" if machine.requires_correct_tool else "")
        )

    def _render_block_class(self, spec: ModSpec, machine: MachineSpec) -> str:
        class_name = self.block_class_name(machine)
        block_entity_name = self.block_entity_class_name(machine)
        block_entity_constant = f"{upper_snake_case(machine.identifier)}_BLOCK_ENTITY"
        return "\n".join(
            [
                f"package {spec.package_name}.block;",
                "",
                "import com.mojang.serialization.MapCodec;",
                "",
                f"import {spec.package_name}.{pascal_case(spec.mod_id) if pascal_case(spec.mod_id).endswith('Mod') else pascal_case(spec.mod_id) + 'Mod'};",
                f"import {spec.package_name}.block.entity.{block_entity_name};",
                "",
                "import net.minecraft.core.BlockPos;",
                "import net.minecraft.server.level.ServerPlayer;",
                "import net.minecraft.world.InteractionResult;",
                "import net.minecraft.world.entity.player.Player;",
                "import net.minecraft.world.level.Level;",
                "import net.minecraft.world.level.block.BaseEntityBlock;",
                "import net.minecraft.world.level.block.RenderShape;",
                "import net.minecraft.world.level.block.entity.BlockEntity;",
                "import net.minecraft.world.level.block.entity.BlockEntityTicker;",
                "import net.minecraft.world.level.block.entity.BlockEntityType;",
                "import net.minecraft.world.level.block.state.BlockState;",
                "import net.minecraft.world.phys.BlockHitResult;",
                "",
                f"public final class {class_name} extends BaseEntityBlock {{",
                f"    public static final MapCodec<{class_name}> CODEC = simpleCodec({class_name}::new);",
                "",
                f"    public {class_name}(Properties properties) {{",
                "        super(properties);",
                "    }",
                "",
                "    @Override",
                f"    protected MapCodec<{class_name}> codec() {{",
                "        return CODEC;",
                "    }",
                "",
                "    @Override",
                "    public BlockEntity newBlockEntity(BlockPos pos, BlockState state) {",
                f"        return new {block_entity_name}(pos, state);",
                "    }",
                "",
                "    @Override",
                "    protected RenderShape getRenderShape(BlockState state) {",
                "        return RenderShape.MODEL;",
                "    }",
                "",
                "    @Override",
                "    protected InteractionResult useWithoutItem(BlockState state, Level level, BlockPos pos, Player player, BlockHitResult hitResult) {",
                f"        if (!level.isClientSide() && level.getBlockEntity(pos) instanceof {block_entity_name} machine && player instanceof ServerPlayer serverPlayer) {{",
                "            serverPlayer.openMenu(machine);",
                "        }",
                "        return level.isClientSide() ? InteractionResult.SUCCESS : InteractionResult.SUCCESS_SERVER;",
                "    }",
                "",
                "    @Override",
                f"    public <T extends BlockEntity> BlockEntityTicker<T> getTicker(Level level, BlockState state, BlockEntityType<T> blockEntityType) {{",
                "        if (level.isClientSide()) {",
                "            return null;",
                "        }",
                f"        return createTickerHelper(blockEntityType, {self._main_class_name(spec)}.{block_entity_constant}.get(), {block_entity_name}::serverTick);",
                "    }",
                "}",
                "",
            ]
        )

    def _render_block_entity_class(self, spec: ModSpec, machine: MachineSpec) -> str:
        class_name = self.block_entity_class_name(machine)
        menu_name = self.menu_class_name(machine)
        constant_name = upper_snake_case(machine.identifier)
        title_key = f"container.{spec.mod_id}.{machine.identifier}"
        slot_count = max(1, machine.inventory_slots)
        max_progress = max(1, machine.max_progress)
        energy_capacity = max(0, machine.energy_capacity)
        energy_per_tick = max(0, machine.energy_per_tick)
        return "\n".join(
            [
                f"package {spec.package_name}.block.entity;",
                "",
                f"import {spec.package_name}.{self._main_class_name(spec)};",
                f"import {spec.package_name}.menu.{menu_name};",
                "",
                "import net.minecraft.core.BlockPos;",
                "import net.minecraft.network.chat.Component;",
                "import net.minecraft.world.Container;",
                "import net.minecraft.world.SimpleContainer;",
                "import net.minecraft.world.entity.player.Inventory;",
                "import net.minecraft.world.entity.player.Player;",
                "import net.minecraft.world.inventory.AbstractContainerMenu;",
                "import net.minecraft.world.inventory.ContainerData;",
                "import net.minecraft.world.level.Level;",
                "import net.minecraft.world.level.block.entity.BlockEntity;",
                "import net.minecraft.world.level.block.state.BlockState;",
                "",
                f"public final class {class_name} extends BlockEntity implements net.minecraft.world.MenuProvider {{",
                f"    public static final int SLOT_COUNT = {slot_count};",
                f"    public static final int INPUT_SLOTS = {max(0, machine.input_slots)};",
                f"    public static final int OUTPUT_SLOTS = {max(0, machine.output_slots)};",
                f"    public static final int ENERGY_CAPACITY = {energy_capacity};",
                f"    public static final int ENERGY_PER_TICK = {energy_per_tick};",
                f"    public static final int MAX_PROGRESS = {max_progress};",
                "",
                "    private final SimpleContainer inventory = new SimpleContainer(SLOT_COUNT) {",
                "        @Override",
                "        public void setChanged() {",
                "            super.setChanged();",
                f"            {class_name}.this.setChanged();",
                "        }",
                "    };",
                "    private int progress;",
                "    private int energy;",
                "    private final ContainerData dataAccess = new ContainerData() {",
                "        @Override",
                "        public int get(int index) {",
                "            return switch (index) {",
                f"                case 0 -> {class_name}.this.progress;",
                "                case 1 -> MAX_PROGRESS;",
                f"                case 2 -> {class_name}.this.energy;",
                "                case 3 -> ENERGY_CAPACITY;",
                "                default -> 0;",
                "            };",
                "        }",
                "",
                "        @Override",
                "        public void set(int index, int value) {",
                "            switch (index) {",
                f"                case 0 -> {class_name}.this.progress = value;",
                f"                case 2 -> {class_name}.this.energy = value;",
                "                default -> { }",
                "            }",
                "        }",
                "",
                "        @Override",
                "        public int getCount() {",
                "            return 4;",
                "        }",
                "    };",
                "",
                f"    public {class_name}(BlockPos pos, BlockState state) {{",
                f"        super({self._main_class_name(spec)}.{constant_name}_BLOCK_ENTITY.get(), pos, state);",
                "    }",
                "",
                "    public static void serverTick(Level level, BlockPos pos, BlockState state, " + class_name + " machine) {",
                "        if (level.isClientSide()) {",
                "            return;",
                "        }",
                "        boolean active = false;",
                "        if (machine.energy < ENERGY_CAPACITY) {",
                "            machine.energy = Math.min(ENERGY_CAPACITY, machine.energy + ENERGY_PER_TICK);",
                "            active = true;",
                "        }",
                "        if (machine.energy >= ENERGY_PER_TICK && !machine.inventory.isEmpty()) {",
                "            machine.energy -= ENERGY_PER_TICK;",
                "            machine.progress++;",
                "            active = true;",
                "            if (machine.progress >= MAX_PROGRESS) {",
                "                machine.progress = 0;",
                "            }",
                "        } else if (machine.progress > 0) {",
                "            machine.progress = 0;",
                "            active = true;",
                "        }",
                "        if (active) {",
                "            setChanged(level, pos, state);",
                "            level.sendBlockUpdated(pos, state, state, 3);",
                "        }",
                "    }",
                "",
                "    public Container inventory() {",
                "        return this.inventory;",
                "    }",
                "",
                "    public ContainerData dataAccess() {",
                "        return this.dataAccess;",
                "    }",
                "",
                "    @Override",
                "    public Component getDisplayName() {",
                f'        return Component.translatable("{title_key}");',
                "    }",
                "",
                "    @Override",
                "    public AbstractContainerMenu createMenu(int containerId, Inventory playerInventory, Player player) {",
                f"        return new {menu_name}(containerId, playerInventory, this.inventory, this.dataAccess);",
                "    }",
                "}",
                "",
            ]
        )

    def _render_menu_class(self, spec: ModSpec, machine: MachineSpec) -> str:
        class_name = self.menu_class_name(machine)
        block_entity_name = self.block_entity_class_name(machine)
        constant_name = upper_snake_case(machine.identifier)
        slot_count = max(1, machine.inventory_slots)
        data_count = 4
        slot_lines = self._machine_slot_lines(slot_count)
        return "\n".join(
            [
                f"package {spec.package_name}.menu;",
                "",
                f"import {spec.package_name}.{self._main_class_name(spec)};",
                f"import {spec.package_name}.block.entity.{block_entity_name};",
                "",
                "import net.minecraft.world.Container;",
                "import net.minecraft.world.SimpleContainer;",
                "import net.minecraft.world.entity.player.Inventory;",
                "import net.minecraft.world.entity.player.Player;",
                "import net.minecraft.world.inventory.AbstractContainerMenu;",
                "import net.minecraft.world.inventory.ContainerData;",
                "import net.minecraft.world.inventory.SimpleContainerData;",
                "import net.minecraft.world.inventory.Slot;",
                "import net.minecraft.world.item.ItemStack;",
                "",
                f"public final class {class_name} extends AbstractContainerMenu {{",
                f"    private static final int MACHINE_SLOT_COUNT = {slot_count};",
                f"    private static final int DATA_COUNT = {data_count};",
                "    private final Container container;",
                "    private final ContainerData data;",
                "",
                f"    public {class_name}(int containerId, Inventory playerInventory) {{",
                "        this(containerId, playerInventory, new SimpleContainer(MACHINE_SLOT_COUNT), new SimpleContainerData(DATA_COUNT));",
                "    }",
                "",
                f"    public {class_name}(int containerId, Inventory playerInventory, Container container, ContainerData data) {{",
                f"        super({self._main_class_name(spec)}.{constant_name}_MENU.get(), containerId);",
                "        checkContainerSize(container, MACHINE_SLOT_COUNT);",
                "        checkContainerDataCount(data, DATA_COUNT);",
                "        this.container = container;",
                "        this.data = data;",
                "        container.startOpen(playerInventory.player);",
                *slot_lines,
                "",
                "        for (int row = 0; row < 3; ++row) {",
                "            for (int column = 0; column < 9; ++column) {",
                "                this.addSlot(new Slot(playerInventory, column + row * 9 + 9, 8 + column * 18, 84 + row * 18));",
                "            }",
                "        }",
                "        for (int column = 0; column < 9; ++column) {",
                "            this.addSlot(new Slot(playerInventory, column, 8 + column * 18, 142));",
                "        }",
                "        this.addDataSlots(data);",
                "    }",
                "",
                "    @Override",
                "    public boolean stillValid(Player player) {",
                "        return this.container.stillValid(player);",
                "    }",
                "",
                "    @Override",
                "    public ItemStack quickMoveStack(Player player, int index) {",
                "        ItemStack copy = ItemStack.EMPTY;",
                "        Slot slot = this.slots.get(index);",
                "        if (slot != null && slot.hasItem()) {",
                "            ItemStack stack = slot.getItem();",
                "            copy = stack.copy();",
                "            if (index < MACHINE_SLOT_COUNT) {",
                "                if (!this.moveItemStackTo(stack, MACHINE_SLOT_COUNT, this.slots.size(), true)) {",
                "                    return ItemStack.EMPTY;",
                "                }",
                "            } else if (!this.moveItemStackTo(stack, 0, MACHINE_SLOT_COUNT, false)) {",
                "                return ItemStack.EMPTY;",
                "            }",
                "            if (stack.isEmpty()) {",
                "                slot.setByPlayer(ItemStack.EMPTY);",
                "            } else {",
                "                slot.setChanged();",
                "            }",
                "        }",
                "        return copy;",
                "    }",
                "",
                "    @Override",
                "    public void removed(Player player) {",
                "        super.removed(player);",
                "        this.container.stopOpen(player);",
                "    }",
                "",
                "    public int progressScaled() {",
                "        int progress = this.data.get(0);",
                "        int maxProgress = Math.max(1, this.data.get(1));",
                "        return progress * 24 / maxProgress;",
                "    }",
                "",
                "    public int energyScaled() {",
                "        int energy = this.data.get(2);",
                "        int capacity = Math.max(1, this.data.get(3));",
                "        return energy * 52 / capacity;",
                "    }",
                "",
                "    public int progress() {",
                "        return this.data.get(0);",
                "    }",
                "",
                "    public int maxProgress() {",
                "        return Math.max(1, this.data.get(1));",
                "    }",
                "",
                "    public int energy() {",
                "        return this.data.get(2);",
                "    }",
                "",
                "    public int energyCapacity() {",
                "        return Math.max(1, this.data.get(3));",
                "    }",
                "}",
                "",
            ]
        )

    def _render_screen_class(self, spec: ModSpec, machine: MachineSpec) -> str:
        class_name = self.screen_class_name(machine)
        menu_name = self.menu_class_name(machine)
        title = machine.menu_title or machine.display_name_en_us
        return "\n".join(
            [
                f"package {spec.package_name}.client;",
                "",
                f"import {spec.package_name}.menu.{menu_name};",
                "",
                "import net.minecraft.client.gui.GuiGraphicsExtractor;",
                "import net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;",
                "import net.minecraft.network.chat.Component;",
                "import net.minecraft.world.entity.player.Inventory;",
                "",
                f"public final class {class_name} extends AbstractContainerScreen<{menu_name}> {{",
                f"    public {class_name}({menu_name} menu, Inventory playerInventory, Component title) {{",
                "        super(menu, playerInventory, title, 176, 166);",
                "    }",
                "",
                "    @Override",
                "    public void extractBackground(GuiGraphicsExtractor graphics, int mouseX, int mouseY, float partialTick) {",
                "        super.extractBackground(graphics, mouseX, mouseY, partialTick);",
                "        int x = this.leftPos;",
                "        int y = this.topPos;",
                "        graphics.fill(x, y, x + this.imageWidth, y + this.imageHeight, 0xFF2B2D31);",
                "        graphics.fill(x + 6, y + 6, x + this.imageWidth - 6, y + this.imageHeight - 6, 0xFF3A3D45);",
                "        graphics.fill(x + 56, y + 35, x + 74, y + 53, 0xFF111318);",
                "        graphics.fill(x + 116, y + 35, x + 134, y + 53, 0xFF111318);",
                "        graphics.fill(x + 78, y + 37, x + 102, y + 51, 0xFF242832);",
                "        graphics.fill(x + 78, y + 37, x + 78 + this.menu.progressScaled(), y + 51, 0xFFFFC857);",
                "        graphics.fill(x + 152, y + 18, x + 160, y + 70, 0xFF151922);",
                "        int energyHeight = this.menu.energyScaled();",
                "        graphics.fill(x + 152, y + 70 - energyHeight, x + 160, y + 70, 0xFF41C7F2);",
                "    }",
                "",
                "    @Override",
                "    protected void extractLabels(GuiGraphicsExtractor graphics, int mouseX, int mouseY) {",
                "        graphics.text(this.font, this.title, 8, 8, 0xFFFFFFFF, false);",
                "        graphics.text(this.font, Component.literal(\"Energy \" + this.menu.energy() + \"/\" + this.menu.energyCapacity()), 8, 62, 0xFFE7ECF4, false);",
                "        graphics.text(this.font, Component.literal(\"Progress \" + this.menu.progress() + \"/\" + this.menu.maxProgress()), 8, 72, 0xFFE7ECF4, false);",
                "    }",
                "}",
                "",
            ]
        )

    def _render_client_class(self, main_class_name: str, spec: ModSpec) -> str:
        lines = [
            f"package {spec.package_name}.client;",
            "",
            f"import {spec.package_name}.{main_class_name};",
        ]
        for machine in spec.machines:
            lines.append(f"import {spec.package_name}.client.{self.screen_class_name(machine)};")
        lines.extend(
            [
                "",
                "import net.neoforged.api.distmarker.Dist;",
                "import net.neoforged.bus.api.SubscribeEvent;",
                "import net.neoforged.fml.common.EventBusSubscriber;",
                "import net.neoforged.neoforge.client.event.RegisterMenuScreensEvent;",
                "",
                f"@EventBusSubscriber(modid = {main_class_name}.MODID, value = Dist.CLIENT)",
                f"public final class {main_class_name}Client {{",
                f"    private {main_class_name}Client() {{",
                "    }",
                "",
                "    @SubscribeEvent",
                "    public static void registerScreens(RegisterMenuScreensEvent event) {",
            ]
        )
        for machine in spec.machines:
            lines.append(
                f"        event.register({main_class_name}.{upper_snake_case(machine.identifier)}_MENU.get(), {self.screen_class_name(machine)}::new);"
            )
        lines.extend(["    }", "}", ""])
        return "\n".join(lines)

    def _machine_slot_lines(self, slot_count: int) -> list[str]:
        if slot_count == 1:
            return ["        this.addSlot(new Slot(container, 0, 80, 35));"]
        if slot_count == 2:
            return [
                "        this.addSlot(new Slot(container, 0, 56, 35));",
                "        this.addSlot(new Slot(container, 1, 116, 35));",
            ]
        lines: list[str] = []
        for index in range(slot_count):
            column = index % 3
            row = index // 3
            x = 44 + column * 36
            y = 24 + row * 18
            lines.append(f"        this.addSlot(new Slot(container, {index}, {x}, {y}));")
        return lines

    def _main_class_name(self, spec: ModSpec) -> str:
        class_name = pascal_case(spec.mod_id)
        return class_name if class_name.endswith("Mod") else f"{class_name}Mod"

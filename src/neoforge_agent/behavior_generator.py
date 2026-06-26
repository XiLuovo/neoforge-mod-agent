from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .models import (
    BehaviorActionSpec,
    BehaviorEventSpec,
    BlockSpec,
    FoodEffectSpec,
    ItemBehaviorSpec,
    ItemSpec,
    ModSpec,
    SwordSpec,
)
from .project_generator import ProjectLayout
from .tools import pascal_case, upper_snake_case, write_text


EFFECT_CONSTANTS = {
    "minecraft:speed": "MobEffects.SPEED",
    "minecraft:regeneration": "MobEffects.REGENERATION",
    "minecraft:strength": "MobEffects.STRENGTH",
    "minecraft:resistance": "MobEffects.RESISTANCE",
    "minecraft:jump_boost": "MobEffects.JUMP_BOOST",
    "minecraft:haste": "MobEffects.HASTE",
}

PARTICLE_CONSTANTS = {
    "minecraft:happy_villager": "ParticleTypes.HAPPY_VILLAGER",
    "minecraft:heart": "ParticleTypes.HEART",
    "minecraft:flame": "ParticleTypes.FLAME",
    "minecraft:smoke": "ParticleTypes.SMOKE",
    "minecraft:large_smoke": "ParticleTypes.LARGE_SMOKE",
    "minecraft:enchant": "ParticleTypes.ENCHANT",
    "minecraft:enchanted_hit": "ParticleTypes.ENCHANTED_HIT",
}

SOUND_CONSTANTS = {
    "minecraft:entity.experience_orb.pickup": "SoundEvents.EXPERIENCE_ORB_PICKUP",
    "minecraft:block.amethyst_block.chime": "SoundEvents.AMETHYST_BLOCK_CHIME",
    "minecraft:block.enchantment_table.use": "SoundEvents.ENCHANTMENT_TABLE_USE",
    "minecraft:item.firecharge.use": "SoundEvents.FIRECHARGE_USE",
    "minecraft:enchant.thorns.hit": "SoundEvents.THORNS_HIT",
}


@dataclass(slots=True)
class BehaviorGenerationResult:
    java_files: list[Path] = field(default_factory=list)
    import_lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BehaviorGenerator:
    def generate(self, layout: ProjectLayout, spec: ModSpec) -> BehaviorGenerationResult:
        result = BehaviorGenerationResult()
        item_package_dir = layout.package_dir / "item"
        item_package_name = f"{spec.package_name}.item"
        block_package_dir = layout.package_dir / "block"
        block_package_name = f"{spec.package_name}.block"

        for item in spec.items:
            if item.behavior is None:
                continue
            class_name = self.item_class_name(item.identifier)
            java_path = item_package_dir / f"{class_name}.java"
            events = self._events_for_behavior(item.behavior)
            write_text(java_path, self._render_behavior_item_class(item_package_name, class_name, events))
            result.java_files.append(java_path)
            result.import_lines.append(f"import {item_package_name}.{class_name};")
            result.warnings.extend(self._warnings_for_events(item.identifier, events))

        for sword in spec.swords:
            if sword.behavior is None and sword.on_hit is None:
                continue
            class_name = self.item_class_name(sword.identifier)
            java_path = item_package_dir / f"{class_name}.java"
            events = [
                *self._events_for_behavior(sword.behavior),
                *self._legacy_sword_events(sword),
            ]
            write_text(java_path, self._render_behavior_item_class(item_package_name, class_name, events))
            result.java_files.append(java_path)
            result.import_lines.append(f"import {item_package_name}.{class_name};")
            result.warnings.extend(self._warnings_for_events(sword.identifier, events))

        for block in [*spec.blocks, *spec.ores]:
            if block.behavior is None:
                continue
            if block.block_kind != "cube":
                result.warnings.append(
                    f"Block '{block.identifier}' has behavior, but Behavior DSL block generation currently supports block_kind=cube only."
                )
                continue
            class_name = self.block_class_name(block.identifier)
            java_path = block_package_dir / f"{class_name}.java"
            events = self._events_for_behavior(block.behavior)
            write_text(java_path, self._render_behavior_block_class(block_package_name, class_name, events))
            result.java_files.append(java_path)
            result.import_lines.append(f"import {block_package_name}.{class_name};")
            result.warnings.extend(self._warnings_for_events(block.identifier, events, owner="block"))

        return result

    def item_class_name(self, identifier: str) -> str:
        return pascal_case(identifier) + "Item"

    def block_class_name(self, identifier: str) -> str:
        return pascal_case(identifier) + "Block"

    def item_registration(self, item: ItemSpec) -> str | None:
        if item.behavior is None:
            return None
        class_name = self.item_class_name(item.identifier)
        constant_name = upper_snake_case(item.identifier)
        return (
            f'    public static final DeferredItem<Item> {constant_name} = '
            f'ITEMS.registerItem("{item.identifier}", {class_name}::new);'
        )

    def sword_registration(self, sword: SwordSpec) -> str | None:
        if sword.behavior is None and sword.on_hit is None:
            return None
        class_name = self.item_class_name(sword.identifier)
        constant_name = upper_snake_case(sword.identifier)
        return (
            f'    public static final DeferredItem<Item> {constant_name} = '
            f'ITEMS.registerItem("{sword.identifier}", {class_name}::new, properties -> '
            f'properties.sword(resolveToolMaterial("{sword.tool_material.lower()}"), {sword.attack_damage_bonus:.2f}F, {sword.attack_speed:.2f}F));'
        )

    def block_registration_class(self, block: BlockSpec) -> str | None:
        if block.behavior is None or block.block_kind != "cube":
            return None
        return self.block_class_name(block.identifier)

    def food_effect_imports(self, spec: ModSpec) -> list[str]:
        if not any(food.effects for food in spec.foods):
            return []
        return [
            "import java.util.List;",
            "import net.minecraft.world.effect.MobEffectInstance;",
            "import net.minecraft.world.effect.MobEffects;",
            "import net.minecraft.world.item.component.Consumables;",
            "import net.minecraft.world.item.consume_effects.ApplyStatusEffectsConsumeEffect;",
        ]

    def food_effect_properties(self, food_effects: list[FoodEffectSpec]) -> str:
        effect_expressions = [self._food_effect_expression(effect) for effect in food_effects]
        if len(effect_expressions) == 1:
            return f"Consumables.defaultFood().onConsume({effect_expressions[0]}).build()"
        return (
            "Consumables.defaultFood().onConsume(new ApplyStatusEffectsConsumeEffect("
            f"List.of({', '.join(self._mob_effect_instance_expression(effect) for effect in food_effects)}), 1.0F)).build()"
        )

    def _events_for_behavior(self, behavior: ItemBehaviorSpec | None) -> list[BehaviorEventSpec]:
        if behavior is None:
            return []
        if behavior.events:
            return behavior.events
        if behavior.behavior_type == "right_click_effect":
            actions = [
                BehaviorActionSpec(
                    action_type="apply_effect",
                    target="self",
                    effect=behavior.effect or "minecraft:regeneration",
                    duration_ticks=behavior.duration_ticks or 100,
                    amplifier=behavior.amplifier,
                )
            ]
        else:
            actions = [
                BehaviorActionSpec(
                    action_type="heal",
                    target="self",
                    amount=behavior.amount or 0,
                )
            ]
        if behavior.consume:
            actions.append(BehaviorActionSpec(action_type="consume_item", count=1))
        return [
            BehaviorEventSpec(
                trigger="right_click",
                actions=actions,
                cooldown_ticks=behavior.cooldown_ticks,
            )
        ]

    def _legacy_sword_events(self, sword: SwordSpec) -> list[BehaviorEventSpec]:
        if sword.on_hit is None:
            return []
        return [
            BehaviorEventSpec(
                trigger="hit_entity",
                actions=[
                    BehaviorActionSpec(
                        action_type="ignite",
                        target="target",
                        seconds=sword.on_hit.seconds,
                    )
                ],
            )
        ]

    def _food_effect_expression(self, effect: FoodEffectSpec) -> str:
        probability = f"{effect.probability:.2f}F"
        return f"new ApplyStatusEffectsConsumeEffect({self._mob_effect_instance_expression(effect)}, {probability})"

    def _mob_effect_instance_expression(self, effect: FoodEffectSpec) -> str:
        effect_constant = EFFECT_CONSTANTS.get(effect.effect, "MobEffects.REGENERATION")
        return f"new MobEffectInstance({effect_constant}, {effect.duration_ticks}, {effect.amplifier})"

    def _render_behavior_item_class(
        self,
        package_name: str,
        class_name: str,
        events: list[BehaviorEventSpec],
    ) -> str:
        lines = [
            f"package {package_name};",
            "",
            "import net.minecraft.core.BlockPos;",
            "import net.minecraft.core.particles.ParticleTypes;",
            "import net.minecraft.core.particles.SimpleParticleType;",
            "import net.minecraft.server.level.ServerLevel;",
            "import net.minecraft.sounds.SoundEvent;",
            "import net.minecraft.sounds.SoundEvents;",
            "import net.minecraft.sounds.SoundSource;",
            "import net.minecraft.world.InteractionHand;",
            "import net.minecraft.world.InteractionResult;",
            "import net.minecraft.world.effect.MobEffectInstance;",
            "import net.minecraft.world.effect.MobEffects;",
            "import net.minecraft.world.entity.Entity;",
            "import net.minecraft.world.entity.EquipmentSlot;",
            "import net.minecraft.world.entity.LivingEntity;",
            "import net.minecraft.world.entity.player.Player;",
            "import net.minecraft.world.item.Item;",
            "import net.minecraft.world.item.ItemStack;",
            "import net.minecraft.world.level.Level;",
            "",
            f"public final class {class_name} extends Item {{",
            f"    public {class_name}(Properties properties) {{",
            "        super(properties);",
            "    }",
        ]

        if self._events_for_trigger(events, "right_click"):
            lines.extend(["", *self._render_use_method(events)])
        if self._events_for_trigger(events, "hit_entity"):
            lines.extend(["", *self._render_hurt_enemy_method(events)])
        if self._events_for_trigger(events, "inventory_tick"):
            lines.extend(["", *self._render_inventory_tick_method(events)])
        if self._uses_particles(events) or self._uses_sounds(events):
            lines.extend(["", *self._render_helpers()])

        lines.extend(["}", ""])
        return "\n".join(lines)

    def _render_behavior_block_class(
        self,
        package_name: str,
        class_name: str,
        events: list[BehaviorEventSpec],
    ) -> str:
        lines = [
            f"package {package_name};",
            "",
            "import net.minecraft.core.BlockPos;",
            "import net.minecraft.core.particles.ParticleTypes;",
            "import net.minecraft.core.particles.SimpleParticleType;",
            "import net.minecraft.server.level.ServerLevel;",
            "import net.minecraft.sounds.SoundEvent;",
            "import net.minecraft.sounds.SoundEvents;",
            "import net.minecraft.sounds.SoundSource;",
            "import net.minecraft.world.InteractionResult;",
            "import net.minecraft.world.effect.MobEffectInstance;",
            "import net.minecraft.world.effect.MobEffects;",
            "import net.minecraft.world.entity.player.Player;",
            "import net.minecraft.world.level.Level;",
            "import net.minecraft.world.level.block.Block;",
            "import net.minecraft.world.level.block.state.BlockState;",
            "import net.minecraft.world.phys.BlockHitResult;",
            "",
            f"public final class {class_name} extends Block {{",
            f"    public {class_name}(Properties properties) {{",
            "        super(properties);",
            "    }",
        ]

        if self._events_for_trigger(events, "block_use"):
            lines.extend(["", *self._render_block_use_method(events)])
        if self._uses_particles(events) or self._uses_sounds(events):
            lines.extend(["", *self._render_helpers()])

        lines.extend(["}", ""])
        return "\n".join(lines)

    def _render_use_method(self, events: list[BehaviorEventSpec]) -> list[str]:
        action_lines = self._render_events(events, "right_click", context="item")
        return [
            "    @Override",
            "    public InteractionResult use(Level level, Player player, InteractionHand hand) {",
            "        ItemStack stack = player.getItemInHand(hand);",
            "        if (!level.isClientSide()) {",
            *action_lines,
            "        }",
            "        return level.isClientSide() ? InteractionResult.SUCCESS : InteractionResult.SUCCESS_SERVER;",
            "    }",
        ]

    def _render_hurt_enemy_method(self, events: list[BehaviorEventSpec]) -> list[str]:
        action_lines = self._render_events(events, "hit_entity", context="hit")
        return [
            "    @Override",
            "    public void hurtEnemy(ItemStack stack, LivingEntity target, LivingEntity attacker) {",
            "        if (attacker instanceof Player player && !attacker.level().isClientSide()) {",
            "            Level level = attacker.level();",
            *action_lines,
            "        }",
            "        super.hurtEnemy(stack, target, attacker);",
            "    }",
        ]

    def _render_inventory_tick_method(self, events: list[BehaviorEventSpec]) -> list[str]:
        action_lines = self._render_events(events, "inventory_tick", context="tick")
        return [
            "    @Override",
            "    public void inventoryTick(ItemStack stack, ServerLevel level, Entity owner, EquipmentSlot slot) {",
            "        if (owner instanceof Player player) {",
            *action_lines,
            "        }",
            "        super.inventoryTick(stack, level, owner, slot);",
            "    }",
        ]

    def _render_block_use_method(self, events: list[BehaviorEventSpec]) -> list[str]:
        action_lines = self._render_events(events, "block_use", context="block")
        return [
            "    @Override",
            "    protected InteractionResult useWithoutItem(BlockState state, Level level, BlockPos pos, Player player, BlockHitResult hitResult) {",
            "        if (!level.isClientSide()) {",
            *action_lines,
            "        }",
            "        return level.isClientSide() ? InteractionResult.SUCCESS : InteractionResult.SUCCESS_SERVER;",
            "    }",
        ]

    def _render_events(self, events: list[BehaviorEventSpec], trigger: str, *, context: str) -> list[str]:
        lines: list[str] = []
        for event in self._events_for_trigger(events, trigger):
            condition = self._event_condition(event, context=context)
            lines.append(f"            if ({condition}) {{")
            rendered_actions = self._render_actions(event.actions, context=context)
            lines.extend(rendered_actions or ["                // No supported actions were declared for this behavior event."])
            if event.cooldown_ticks > 0 and context in {"item", "hit", "tick"}:
                lines.append(f"                player.getCooldowns().addCooldown(stack, {event.cooldown_ticks});")
            lines.append("            }")
        return lines

    def _render_actions(self, actions: list[BehaviorActionSpec], *, context: str) -> list[str]:
        lines: list[str] = []
        for action in actions:
            lines.extend(self._render_action(action, context=context))
        return lines

    def _render_action(self, action: BehaviorActionSpec, *, context: str) -> list[str]:
        action_type = action.action_type
        entity = self._entity_expr(action, context)
        if action_type == "heal":
            amount = action.amount if action.amount is not None else 0
            return [f"                {entity}.heal({amount:.2f}F);"]
        if action_type == "apply_effect":
            effect = EFFECT_CONSTANTS.get(action.effect or "", "MobEffects.REGENERATION")
            duration = action.duration_ticks or 100
            return [f"                {entity}.addEffect(new MobEffectInstance({effect}, {duration}, {action.amplifier}));"]
        if action_type == "ignite":
            seconds = action.seconds or 1
            return [f"                {entity}.igniteForSeconds({seconds}.0F);"]
        if action_type == "consume_item" and context in {"item", "hit", "tick"}:
            count = action.count or 1
            return [f"                stack.consume({count}, player);"]
        if action_type == "cooldown" and context in {"item", "hit", "tick"}:
            ticks = action.cooldown_ticks or 0
            return [f"                player.getCooldowns().addCooldown(stack, {ticks});"]
        if action_type == "spawn_particles":
            particle = PARTICLE_CONSTANTS.get(action.particle or "", "ParticleTypes.HAPPY_VILLAGER")
            count = action.count or 8
            x, y, z = self._particle_position_expr(action, context)
            return [f"                spawnParticles(level, {x}, {y}, {z}, {particle}, {count});"]
        if action_type == "play_sound":
            sound = SOUND_CONSTANTS.get(action.sound or "", "SoundEvents.EXPERIENCE_ORB_PICKUP")
            source = "SoundSource.BLOCKS" if context == "block" else "SoundSource.PLAYERS"
            volume = action.volume if action.volume is not None else 0.8
            pitch = action.pitch if action.pitch is not None else 1.0
            return [f"                playSound(level, {self._sound_pos_expr(action, context)}, {sound}, {source}, {volume:.2f}F, {pitch:.2f}F);"]
        return []

    def _event_condition(self, event: BehaviorEventSpec, *, context: str) -> str:
        parts = [self._render_condition(condition) for condition in event.conditions]
        parts = [part for part in parts if part]
        if event.interval_ticks > 0:
            parts.append(f"level.getGameTime() % {event.interval_ticks}L == 0L")
        if event.cooldown_ticks > 0 and context in {"item", "hit", "tick"}:
            parts.append("!player.getCooldowns().isOnCooldown(stack)")
        return " && ".join(parts) if parts else "true"

    def _render_condition(self, condition: object) -> str:
        condition_type = getattr(condition, "condition_type", "")
        if condition_type == "sneaking":
            return "player.isShiftKeyDown()"
        if condition_type == "not_sneaking":
            return "!player.isShiftKeyDown()"
        if condition_type == "health_below":
            threshold = getattr(condition, "threshold", None)
            return f"player.getHealth() < {(threshold if threshold is not None else 10):.2f}F"
        if condition_type == "health_above":
            threshold = getattr(condition, "threshold", None)
            return f"player.getHealth() > {(threshold if threshold is not None else 10):.2f}F"
        if condition_type == "random_chance":
            chance = getattr(condition, "chance", None)
            return f"level.getRandom().nextFloat() < {(chance if chance is not None else 1.0):.4f}F"
        return ""

    def _entity_expr(self, action: BehaviorActionSpec, context: str) -> str:
        if context == "hit" and action.target == "target":
            return "target"
        return "player"

    def _particle_position_expr(self, action: BehaviorActionSpec, context: str) -> tuple[str, str, str]:
        if context == "block":
            return ("pos.getX() + 0.5D", "pos.getY() + 1.0D", "pos.getZ() + 0.5D")
        entity = self._entity_expr(action, context)
        return (f"{entity}.getX()", f"{entity}.getY() + 1.0D", f"{entity}.getZ()")

    def _sound_pos_expr(self, action: BehaviorActionSpec, context: str) -> str:
        if context == "block":
            return "pos"
        return f"{self._entity_expr(action, context)}.blockPosition()"

    def _render_helpers(self) -> list[str]:
        return [
            "    private static void spawnParticles(Level level, double x, double y, double z, SimpleParticleType particle, int count) {",
            "        if (level instanceof ServerLevel serverLevel) {",
            "            serverLevel.sendParticles(particle, x, y, z, Math.max(1, count), 0.25D, 0.5D, 0.25D, 0.05D);",
            "        }",
            "    }",
            "",
            "    private static void playSound(Level level, BlockPos pos, SoundEvent sound, SoundSource source, float volume, float pitch) {",
            "        level.playSound(null, pos, sound, source, volume, pitch);",
            "    }",
        ]

    def _events_for_trigger(self, events: list[BehaviorEventSpec], trigger: str) -> list[BehaviorEventSpec]:
        return [event for event in events if event.trigger == trigger]

    def _uses_particles(self, events: list[BehaviorEventSpec]) -> bool:
        return any(action.action_type == "spawn_particles" for event in events for action in event.actions)

    def _uses_sounds(self, events: list[BehaviorEventSpec]) -> bool:
        return any(action.action_type == "play_sound" for event in events for action in event.actions)

    def _warnings_for_events(
        self,
        identifier: str,
        events: list[BehaviorEventSpec],
        *,
        owner: str = "item",
    ) -> list[str]:
        warnings: list[str] = []
        for event in events:
            if owner == "block" and event.cooldown_ticks:
                warnings.append(f"Block behavior '{identifier}' declares cooldown_ticks; block cooldown is ignored.")
            for action in event.actions:
                if action.action_type == "apply_effect" and action.effect not in EFFECT_CONSTANTS:
                    warnings.append(
                        f"Behavior '{identifier}' requested unsupported effect '{action.effect}', falling back to minecraft:regeneration."
                    )
                if action.action_type == "spawn_particles" and action.particle not in PARTICLE_CONSTANTS:
                    warnings.append(
                        f"Behavior '{identifier}' requested unsupported particle '{action.particle}', falling back to minecraft:happy_villager."
                    )
                if action.action_type == "play_sound" and action.sound not in SOUND_CONSTANTS:
                    warnings.append(
                        f"Behavior '{identifier}' requested unsupported sound '{action.sound}', falling back to minecraft:entity.experience_orb.pickup."
                    )
                if owner == "block" and action.action_type in {"consume_item", "cooldown"}:
                    warnings.append(
                        f"Block behavior '{identifier}' declares item-only action '{action.action_type}', which is ignored."
                    )
        return warnings

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .models import EntityGoalSpec, EntitySpec, ModSpec
from .project_generator import ProjectLayout
from .tools import pascal_case, upper_snake_case, write_text


@dataclass(slots=True)
class EntityGenerationResult:
    java_files: list[Path] = field(default_factory=list)
    import_lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class EntityGenerator:
    def generate(self, layout: ProjectLayout, spec: ModSpec) -> EntityGenerationResult:
        result = EntityGenerationResult()
        if not spec.entities:
            return result

        entity_dir = layout.package_dir / "entity"
        client_dir = layout.package_dir / "client"
        entity_package = f"{spec.package_name}.entity"
        client_package = f"{spec.package_name}.client"

        for entity in spec.entities:
            entity_name = self.entity_class_name(entity)
            renderer_name = self.renderer_class_name(entity)
            entity_path = entity_dir / f"{entity_name}.java"
            renderer_path = client_dir / f"{renderer_name}.java"

            write_text(entity_path, self._render_entity_class(entity_package, entity_name, entity))
            write_text(renderer_path, self._render_renderer_class(spec, client_package, renderer_name, entity_name, entity))
            result.java_files.extend([entity_path, renderer_path])
            result.import_lines.append(f"import {entity_package}.{entity_name};")
            result.warnings.extend(self._warnings_for(entity))

        client_path = client_dir / f"{layout.main_class_name}EntityClient.java"
        write_text(client_path, self._render_client_class(layout.main_class_name, spec))
        result.java_files.append(client_path)
        return result

    def main_imports(self, spec: ModSpec) -> list[str]:
        if not spec.entities:
            return []
        return [
            "import net.minecraft.resources.ResourceKey;",
            "import net.minecraft.resources.Identifier;",
            "import net.minecraft.world.entity.EntityType;",
            "import net.minecraft.world.entity.MobCategory;",
            "import net.neoforged.neoforge.event.entity.EntityAttributeCreationEvent;",
        ]

    def registry_declarations(self) -> list[str]:
        return [
            "    public static final DeferredRegister<EntityType<?>> ENTITY_TYPES = DeferredRegister.create(Registries.ENTITY_TYPE, MODID);",
        ]

    def constructor_registrations(self) -> list[str]:
        return [
            "        ENTITY_TYPES.register(modEventBus);",
            "        modEventBus.addListener(this::registerEntityAttributes);",
        ]

    def entity_declarations(self, entity: EntitySpec) -> str:
        constant_name = upper_snake_case(entity.identifier)
        class_name = self.entity_class_name(entity)
        category = self._mob_category(entity)
        builder_chain = (
            f"EntityType.Builder.of({class_name}::new, MobCategory.{category})"
            f".sized({entity.width:.2f}F, {entity.height:.2f}F)"
            f".clientTrackingRange({entity.tracking_range})"
            f".updateInterval({entity.update_interval})"
        )
        if entity.fire_immune:
            builder_chain += ".fireImmune()"
        return "\n".join(
            [
                f"    public static final DeferredHolder<EntityType<?>, EntityType<{class_name}>> {constant_name} = ",
                f'            ENTITY_TYPES.register("{entity.identifier}", () -> {builder_chain}',
                f'                    .build(ResourceKey.create(Registries.ENTITY_TYPE, Identifier.fromNamespaceAndPath(MODID, "{entity.identifier}"))));',
            ]
        )

    def attribute_registration_method(self, spec: ModSpec) -> list[str]:
        if not spec.entities:
            return []
        lines = [
            "    private void registerEntityAttributes(EntityAttributeCreationEvent event) {",
        ]
        for entity in spec.entities:
            constant_name = upper_snake_case(entity.identifier)
            class_name = self.entity_class_name(entity)
            lines.append(f"        event.put({constant_name}.get(), {class_name}.createAttributes().build());")
        lines.extend(["    }", ""])
        return lines

    def entity_class_name(self, entity: EntitySpec) -> str:
        return pascal_case(entity.identifier) + "Entity"

    def renderer_class_name(self, entity: EntitySpec) -> str:
        return pascal_case(entity.identifier) + "Renderer"

    def _render_entity_class(self, package_name: str, class_name: str, entity: EntitySpec) -> str:
        goal_lines = self._goal_lines(entity)
        attributes = entity.attributes
        attack_damage = entity.attack.damage if entity.attack and entity.attack.damage is not None else attributes.attack_damage
        return "\n".join(
            [
                f"package {package_name};",
                "",
                "import net.minecraft.world.entity.EntityType;",
                "import net.minecraft.world.entity.Mob;",
                "import net.minecraft.world.entity.PathfinderMob;",
                "import net.minecraft.world.entity.ai.attributes.AttributeSupplier;",
                "import net.minecraft.world.entity.ai.attributes.Attributes;",
                "import net.minecraft.world.entity.ai.goal.FloatGoal;",
                "import net.minecraft.world.entity.ai.goal.LookAtPlayerGoal;",
                "import net.minecraft.world.entity.ai.goal.MeleeAttackGoal;",
                "import net.minecraft.world.entity.ai.goal.RandomLookAroundGoal;",
                "import net.minecraft.world.entity.ai.goal.WaterAvoidingRandomStrollGoal;",
                "import net.minecraft.world.entity.ai.goal.target.HurtByTargetGoal;",
                "import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;",
                "import net.minecraft.world.entity.player.Player;",
                "import net.minecraft.world.level.Level;",
                "",
                f"public final class {class_name} extends PathfinderMob {{",
                f"    public {class_name}(EntityType<? extends {class_name}> entityType, Level level) {{",
                "        super(entityType, level);",
                f"        this.xpReward = {max(0, entity.xp_reward)};",
                "    }",
                "",
                "    @Override",
                "    protected void registerGoals() {",
                "        super.registerGoals();",
                *goal_lines,
                "    }",
                "",
                "    public static AttributeSupplier.Builder createAttributes() {",
                "        return Mob.createMobAttributes()",
                f"                .add(Attributes.MAX_HEALTH, {attributes.max_health:.2f}D)",
                f"                .add(Attributes.MOVEMENT_SPEED, {attributes.movement_speed:.3f}D)",
                f"                .add(Attributes.ATTACK_DAMAGE, {attack_damage:.2f}D)",
                f"                .add(Attributes.ARMOR, {attributes.armor:.2f}D)",
                f"                .add(Attributes.FOLLOW_RANGE, {attributes.follow_range:.2f}D)",
                f"                .add(Attributes.KNOCKBACK_RESISTANCE, {attributes.knockback_resistance:.2f}D);",
                "    }",
                "}",
                "",
            ]
        )

    def _render_renderer_class(
        self,
        spec: ModSpec,
        package_name: str,
        renderer_name: str,
        entity_name: str,
        entity: EntitySpec,
    ) -> str:
        return "\n".join(
            [
                f"package {package_name};",
                "",
                f"import {spec.package_name}.{self._main_class_name(spec)};",
                f"import {spec.package_name}.entity.{entity_name};",
                "",
                "import net.minecraft.client.renderer.entity.EntityRendererProvider;",
                "import net.minecraft.client.renderer.entity.NoopRenderer;",
                "",
                f"public final class {renderer_name} extends NoopRenderer<{entity_name}> {{",
                f"    public {renderer_name}(EntityRendererProvider.Context context) {{",
                "        super(context);",
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
            "",
            "import net.neoforged.api.distmarker.Dist;",
            "import net.neoforged.bus.api.SubscribeEvent;",
            "import net.neoforged.fml.common.EventBusSubscriber;",
            "import net.neoforged.neoforge.client.event.EntityRenderersEvent;",
            "",
            f"@EventBusSubscriber(modid = {main_class_name}.MODID, value = Dist.CLIENT)",
            f"public final class {main_class_name}EntityClient {{",
            f"    private {main_class_name}EntityClient() {{",
            "    }",
            "",
            "    @SubscribeEvent",
            "    public static void registerEntityRenderers(EntityRenderersEvent.RegisterRenderers event) {",
        ]
        for entity in spec.entities:
            lines.append(
                f"        event.registerEntityRenderer({main_class_name}.{upper_snake_case(entity.identifier)}.get(), {self.renderer_class_name(entity)}::new);"
            )
        lines.extend(["    }", "}", ""])
        return "\n".join(lines)

    def _goal_lines(self, entity: EntitySpec) -> list[str]:
        goals = entity.goals or self._default_goals(entity)
        lines: list[str] = []
        for goal in goals:
            goal_type = goal.goal_type
            priority = max(0, goal.priority)
            if goal_type == "float":
                lines.append(f"        this.goalSelector.addGoal({priority}, new FloatGoal(this));")
            elif goal_type == "melee_attack":
                speed = goal.speed if goal.speed is not None else (entity.attack.speed if entity.attack else 1.0)
                lines.append(f"        this.goalSelector.addGoal({priority}, new MeleeAttackGoal(this, {speed:.2f}D, true));")
            elif goal_type == "random_stroll":
                speed = goal.speed if goal.speed is not None else 1.0
                lines.append(f"        this.goalSelector.addGoal({priority}, new WaterAvoidingRandomStrollGoal(this, {speed:.2f}D));")
            elif goal_type == "look_at_player":
                distance = goal.distance if goal.distance is not None else 8.0
                lines.append(f"        this.goalSelector.addGoal({priority}, new LookAtPlayerGoal(this, Player.class, {distance:.2f}F));")
            elif goal_type == "random_look_around":
                lines.append(f"        this.goalSelector.addGoal({priority}, new RandomLookAroundGoal(this));")
            elif goal_type == "hurt_by_target":
                lines.append(f"        this.targetSelector.addGoal({priority}, new HurtByTargetGoal(this));")
            elif goal_type == "target_player":
                lines.append(f"        this.targetSelector.addGoal({priority}, new NearestAttackableTargetGoal<>(this, Player.class, true));")
        return lines or ["        this.goalSelector.addGoal(0, new FloatGoal(this));"]

    def _default_goals(self, entity: EntitySpec) -> list[EntityGoalSpec]:
        attack_type = entity.attack.attack_type if entity.attack else "none"
        aggressive = entity.entity_kind in {"monster", "boss"} or attack_type == "melee"
        goals = [
            EntityGoalSpec(goal_type="float", priority=0),
            EntityGoalSpec(goal_type="random_stroll", priority=5, speed=0.9),
            EntityGoalSpec(goal_type="look_at_player", priority=6, distance=8.0),
            EntityGoalSpec(goal_type="random_look_around", priority=7),
        ]
        if aggressive:
            goals.insert(1, EntityGoalSpec(goal_type="melee_attack", priority=2, speed=entity.attack.speed if entity.attack else 1.0))
            goals.append(EntityGoalSpec(goal_type="hurt_by_target", priority=1))
            goals.append(EntityGoalSpec(goal_type="target_player", priority=2))
        return goals

    def _mob_category(self, entity: EntitySpec) -> str:
        return {
            "monster": "MONSTER",
            "boss": "MONSTER",
            "creature": "CREATURE",
            "pet": "CREATURE",
            "npc": "MISC",
            "ambient": "AMBIENT",
        }.get(entity.category.lower(), "MONSTER")

    def _warnings_for(self, entity: EntitySpec) -> list[str]:
        warnings: list[str] = []
        if entity.attack and entity.attack.attack_type != "melee":
            warnings.append(
                f"Entity '{entity.identifier}' requested attack type '{entity.attack.attack_type}', falling back to melee/no-op goal templates."
            )
        return warnings

    def _main_class_name(self, spec: ModSpec) -> str:
        class_name = pascal_case(spec.mod_id)
        return class_name if class_name.endswith("Mod") else f"{class_name}Mod"

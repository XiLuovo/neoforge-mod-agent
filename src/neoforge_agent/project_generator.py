from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig
from .models import ModSpec
from .tools import ensure_directory, pascal_case, write_text


@dataclass(frozen=True, slots=True)
class ProjectLayout:
    project_dir: Path
    package_dir: Path
    resources_dir: Path
    asset_dir: Path
    mixins_config_path: Path
    main_class_name: str


class ProjectGenerator:
    TEMPLATE_MOD_ID = "examplemod"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig.default()

    def generate(self, project_dir: Path, spec: ModSpec, *, clean_roots: bool = True) -> ProjectLayout:
        layout = self._prepare_layout(project_dir, spec, clean_roots=clean_roots)
        self._rewrite_gradle_properties(project_dir, spec)
        self._rewrite_mods_toml(project_dir, spec)
        self._rewrite_mixins_config(layout, spec)
        self._write_pack_mcmeta(layout, spec)
        return layout

    def _prepare_layout(self, project_dir: Path, spec: ModSpec, *, clean_roots: bool) -> ProjectLayout:
        java_root = project_dir / "src" / "main" / "java"
        if clean_roots and java_root.exists():
            shutil.rmtree(java_root)

        package_dir = ensure_directory(java_root.joinpath(*spec.package_name.split(".")))
        resources_dir = project_dir / "src" / "main" / "resources"
        assets_root = resources_dir / "assets"
        if clean_roots and assets_root.exists():
            shutil.rmtree(assets_root)
        asset_dir = ensure_directory(assets_root / spec.mod_id)

        main_class_name = pascal_case(spec.mod_id)
        if not main_class_name.endswith("Mod"):
            main_class_name = f"{main_class_name}Mod"

        return ProjectLayout(
            project_dir=project_dir,
            package_dir=package_dir,
            resources_dir=resources_dir,
            asset_dir=asset_dir,
            mixins_config_path=resources_dir / f"{spec.mod_id}.mixins.json",
            main_class_name=main_class_name,
        )

    def _rewrite_gradle_properties(self, project_dir: Path, spec: ModSpec) -> None:
        gradle_properties_path = project_dir / "gradle.properties"
        content = gradle_properties_path.read_text(encoding="utf-8")
        replacements = {
            "mod_id": spec.mod_id,
            "mod_name": spec.display_name,
            "mod_license": spec.license_name,
            "mod_version": spec.version,
            "mod_group_id": spec.package_name,
        }
        for key, value in replacements.items():
            content = self._replace_property(content, key, value)
        content = self._replace_property(content, "systemProp.https.protocols", "TLSv1.2")
        content = self._replace_property(content, "systemProp.jdk.tls.client.protocols", "TLSv1.2")
        write_text(gradle_properties_path, content)

    def _rewrite_mods_toml(self, project_dir: Path, spec: ModSpec) -> None:
        mods_toml_path = project_dir / "src" / "main" / "templates" / "META-INF" / "neoforge.mods.toml"
        content = mods_toml_path.read_text(encoding="utf-8")
        description = (spec.description or f"{spec.display_name} for NeoForge {self.config.neo_version}.").replace(
            "'''",
            '"""',
        )
        content = re.sub(
            r"description='''\n.*?\n'''",
            f"description='''\n{description}\n'''",
            content,
            count=1,
            flags=re.DOTALL,
        )

        authors_value = ", ".join(spec.authors)
        if authors_value:
            content = re.sub(
                r'^#authors=""\s*$',
                f'authors="{authors_value}"',
                content,
                count=1,
                flags=re.MULTILINE,
            )

        write_text(mods_toml_path, content)

    def _rewrite_mixins_config(self, layout: ProjectLayout, spec: ModSpec) -> None:
        old_mixins_path = layout.resources_dir / f"{self.TEMPLATE_MOD_ID}.mixins.json"
        if old_mixins_path.exists():
            data = json.loads(old_mixins_path.read_text(encoding="utf-8"))
        else:
            data = {
                "required": False,
                "package": f"{spec.package_name}.mixin",
                "compatibilityLevel": f"JAVA_{spec.java_version}",
                "mixins": [],
            }

        data["required"] = False
        data["package"] = f"{spec.package_name}.mixin"
        data["compatibilityLevel"] = f"JAVA_{spec.java_version}"

        write_text(layout.mixins_config_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        if old_mixins_path.exists() and old_mixins_path != layout.mixins_config_path:
            old_mixins_path.unlink()

    def _write_pack_mcmeta(self, layout: ProjectLayout, spec: ModSpec) -> None:
        pack_mcmeta_path = layout.resources_dir / "pack.mcmeta"
        payload = {
            "pack": {
                "description": f"{spec.mod_id} resources",
                "pack_format": 61,
            }
        }
        write_text(pack_mcmeta_path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def _replace_property(self, content: str, key: str, value: str) -> str:
        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
        replacement = f"{key}={value}"
        if pattern.search(content):
            return pattern.sub(replacement, content)
        suffix = "" if content.endswith("\n") else "\n"
        return f"{content}{suffix}{replacement}\n"

## V2.7 Equipment Sets And Recipes Smoke

```powershell
py -3.11 -m agent.cli generate --build --audit "Create a ruby mod with ruby tool set." --workspace-name v27-tool-set --overwrite --json
py -3.11 -m agent.cli generate --build --audit "Create a ruby mod with ruby armor set." --workspace-name v27-armor-set --overwrite --json
py -3.11 -m agent.cli generate --build "Create a ruby mod with ruby." --workspace-name v27-modify-equipment --overwrite --json
py -3.11 -m agent.cli modify workspace\v27-modify-equipment "Add ruby tool set." --build --audit --json
py -3.11 -m agent.cli modify workspace\v27-modify-equipment "Add ruby tool set." --no-build --audit --json
py -3.11 -m agent.cli generate "Create a ruby mod with ruby tool set." --planner llm --llm-provider mock --workspace-name v27-llm-tool-set --overwrite --no-build --audit --json
py -3.11 -m agent.cli generate "Create a ruby mod with ruby armor set." --planner llm --llm-provider mock --workspace-name v27-llm-armor-set --overwrite --no-build --audit --json
py -3.11 -m agent.cli quality-gate --run-name v27-equipment-quality-gate --json
```

Expected:

- tool set generation creates `ruby`, `ruby_sword`, `ruby_pickaxe`, `ruby_axe`, `ruby_shovel`, `ruby_hoe`
- armor set generation creates `ruby`, `ruby_helmet`, `ruby_chestplate`, `ruby_leggings`, `ruby_boots`
- all generated equipment uses `tool_material` / `armor_material` value `ruby`
- shaped recipe JSON files are generated for every equipment piece
- audit checks models, textures, lang keys, registration, and recipe references
- build succeeds for rules planner tool and armor set smoke projects
- repeated modify skips existing equipment and recipe features
- mock LLM emits the same equipment and recipe ModSpec structure without using a real API

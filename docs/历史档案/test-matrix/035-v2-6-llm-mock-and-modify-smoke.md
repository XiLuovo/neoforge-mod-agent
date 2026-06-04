## V2.6 LLM Mock And Modify Smoke

```powershell
py -3.11 -m agent.cli generate "Create a ruby mod with ruby pickaxe." --planner llm --llm-provider mock --workspace-name v26-llm-pickaxe --overwrite --no-build --audit --json
py -3.11 -m agent.cli generate "Create a ruby mod with ruby armor set." --planner llm --llm-provider mock --workspace-name v26-llm-armor --overwrite --no-build --audit --json
py -3.11 -m agent.cli generate "Create a ruby mod with ruby." --workspace-name v26-modify-content-base --overwrite --no-build --json
py -3.11 -m agent.cli modify workspace\v26-modify-content-base "Add ruby pickaxe and ruby armor set." --no-build --audit --json
py -3.11 -m agent.cli modify workspace\v26-modify-content-base "Add ruby pickaxe and ruby armor set." --no-build --audit --json
```

Expected:

- mock LLM emits `tool` and `armor` ModSpec features
- modify adds `ruby_pickaxe` and the four armor pieces
- repeated modify reports existing tool/armor features as `skipped`
- audit succeeds after each generated or modified workspace

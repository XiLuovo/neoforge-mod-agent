## V8 Resource Quality Upgrade

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_generation_audit tests.test_dashboard tests.test_capabilities -v
py -3.11 -m unittest discover -s tests -v
py -3.11 -m agent.cli eval --run-name v80-readme-metrics-eval --planner llm --llm-provider mock --no-build --audit --json
py -3.11 -m agent.cli repair-eval --run-name v80-readme-metrics-repair-eval --json
py -3.11 -m agent.cli generate-from-spec .\examples\resource_quality_showcase.json --workspace-name v80-resource-smoke --overwrite --audit --no-build --json
py -3.11 -m agent.cli dashboard --run-name v80-resource-dashboard --json
py -3.11 -m agent.cli generate-from-spec .\examples\ruby_item.json --workspace-name v80-readme-metrics-build --overwrite --build --audit --json
```

Expected:

- Project version reports `8.0.0`.
- `compileall` succeeds for `src` and `tests`.
- Focused V8 tests pass for resource quality generation, dashboard rendering, and capability catalog entries.
- Full unittest discovery passes: 163 tests.
- Default eval passes 12/12 with audit enabled and `generated_files_total = 258`.
- Repair eval remains 5/5 full success.
- `workspace/v80-resource-smoke/.agent/resource-quality-report.json` exists and uses V8 schema version `8`.
- `workspace/v80-resource-smoke/.agent/texture-atlas.png` exists.
- `workspace/v80-resource-smoke/.agent/previews/ruby_gallery.png` exists.
- Dashboard HTML includes `Resource Preview`.
- Gradle build produces `workspace/v80-readme-metrics-build/build/libs/ruby_mod-0.2.0.jar`.

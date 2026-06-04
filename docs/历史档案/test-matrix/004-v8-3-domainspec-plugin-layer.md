## V8.3 DomainSpec Plugin Layer

```powershell
py -3.11 -m compileall -q src tests
py -3.11 -m unittest tests.test_domain_spec tests.test_cli_parser tests.test_capabilities -v
py -3.11 -m agent.cli domains --json
py -3.11 -m agent.cli agent generate "Create a ruby mod with ruby." --planner llm --llm-provider mock --workspace-name v83-domain-spec-smoke-20260514 --overwrite --no-build --json
py -3.11 -m agent.cli audit v83-domain-spec-smoke-20260514 --json
py -3.11 -m unittest discover -s tests -v
```

Expected:

- `domains --json` lists `minecraft.neoforge` as `stable`, plus `spring.api` and `unity.component` as `planned`.
- Generated `.agent/modspec.json` includes `domain = minecraft.neoforge` and `domain_spec_type = ModSpec`.
- Agent run payload includes `payload.runtime.domain_spec`.
- Smoke audit for `workspace/v83-domain-spec-smoke-20260514` passes with 0 errors.

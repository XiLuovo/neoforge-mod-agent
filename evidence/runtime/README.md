# Minecraft Runtime Evidence

这里保存人工 Minecraft runtime 验收的源记录。所有 case 初始都是 `runtime_unverified`；只有实际启动对应 workspace、完成 checklist、记录观察结果并附上截图或日志后，才能改为 `passed` 或 `failed`。

当前结果：`4/4 checked`、`4 passed`、`0 failed / blocked / unverified`。第三例保留了首次 `/place feature ruby_mod:ruby_ore` 失败记录；第四例验证了修正后的 Deepslate target 和 `Y<0` 自然生成。

## 当前候选

1. `runtime_basic_ruby`：最小客户端启动、Mod 加载和 Ruby 物品注册。
2. `runtime_speed_crystal_behavior`：右键触发 Speed II 约 10 秒，并确认物品不消耗。
3. `runtime_modify_worldgen`：modify lane 生成的物品、方块、双向配方、自然矿脉、configured feature 放置和挖掘掉落均已检查；首次失败尝试与复验记录同时保留。
4. `runtime_deepslate_worldgen_revalidation`：新 generator 输出同时覆盖 Stone / Deepslate targets；在实心 Deepslate 中放置成功，并在 `Y≈-28` 的新生成深板岩地形中观察到自然 Ruby Ore。

暂不把 `progression_mod` 作为首批通过目标：当前静态检查发现 compressor 没有产出流程，structure template pool 也没有可见结构元素。它更适合作为后续 runtime failure → repair 的案例。

## 命令

```powershell
py -3.11 scripts/runtime_evidence_portfolio.py prepare --overwrite
py -3.11 scripts/runtime_evidence_portfolio.py check
py -3.11 scripts/runtime_evidence_portfolio.py check --require-complete
```

普通 `check` 允许未验证模板存在；`--require-complete` 会在任一 case 仍为 `runtime_unverified` 时失败。

## 启动约定

这些 workspace 均要求 Java 25。PowerShell 中先设置：

```powershell
$env:GRADLE_USER_HOME = (Resolve-Path .\.gradle-user-home)
```

进入目标 workspace 后运行：

```powershell
.\gradlew.bat runClient --console=plain --no-configuration-cache
```

每个 case 的截图、视频或日志放在：

```text
evidence/runtime/attachments/<case-id>/
```

附件不得包含账号、API key、私人聊天窗口或与项目无关的本机信息。自然 worldgen 必须在新生成区块中观察；`/place feature` 成功只能证明 feature 注册和加载，不能替代自然生成检查。

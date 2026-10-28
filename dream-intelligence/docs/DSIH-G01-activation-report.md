# DSIH-G01｜48 小时加速观察 Activation

## A. Window

```text
start: 2026-09-29 03:06:13 +08:00（Asia/Shanghai）
end:   2026-10-01 03:06:13 +08:00（Asia/Shanghai）
status: ACTIVE
```

窗口记录：[dsih-g01-window.json](evidence/dsih-g01-window.json)。起点按成功启动的加速进程时间取整到秒，结束时间精确为起点后 48 小时。

## B. Baseline

正式配置已在任何频率改动前保存：[dsih-g01-before.json](evidence/dsih-g01-before.json)。

```text
NewsNow: 每 60 分钟，UTC
GitHub: 每 120 分钟，UTC
RSS: 每 240 分钟，UTC
Auto Analysis: 每 240 分钟；首轮在 RSS 首轮后 12 分钟，UTC
Market: 工作日 16:10，Asia/Shanghai
Market Announcements: 工作日 18:30、22:30，Asia/Shanghai
Feishu Daily Brief: 每天 08:30，Asia/Shanghai
```

基线 PID `21216`；数据库行数：sources 9、items 164、analysis 16、feedback 1、watchlist 2、market_watchlist 1、market_snapshots 30、market_announcements 10、market_announcement_documents 6、market_announcement_reads 1、notification_deliveries 1。基线日志大小 890 字节。

## C. Accelerated Schedules

```text
NewsNow: 每 15 分钟
GitHub: 每 30 分钟
RSS: 每 60 分钟
Auto Analysis: 每 120 分钟；首轮仍在 RSS 首轮后 12 分钟
Market: 工作日 16:10，Asia/Shanghai（不变）
Announcements: 工作日 08:30、10:30、12:30、14:30、16:30、18:30、20:30、22:30，Asia/Shanghai
Daily Brief: 每天 08:30，Asia/Shanghai（不变）
```

临时配置只选择 Scheduler trigger；窗口结束或配置无效后，新启动的 Scheduler 会回到正式频率。逐项比对结果见 [dsih-g01-after.json](evidence/dsih-g01-after.json)，所有检查通过。

## D. Runtime

```text
scheduler PID: 39584（Activation 验收时）
single instance: YES
job count: 7
loaded profile: phase_g_48h
```

任务计划程序状态 Running。Activation 本身没有手动执行任何业务 Job；切换前后 11 张业务表行数一致。当前日志 1241 字节，API Key 与飞书 Webhook 值均未出现。

## E. Revert

```text
revert script: scripts/revert_phase_g_acceleration.ps1
Windows one-time task: Dream Intelligence Phase G Revert（已启用）
trigger: 2026-10-01 03:06:13 +08:00
multiple instances: IgnoreNew
missed-run handling: StartWhenAvailable
```

恢复脚本只关闭临时频率选择、通过现有启停脚本安全重启 Scheduler、确认单进程和七项正式 trigger，并写入 `docs/evidence/dsih-g01-revert-result.json`；成功后禁用自身任务。PowerShell 语法检查及 Windows PowerShell 5.1 下的只读 `-CheckOnly` 检查通过，输出 `PHASE_G_REVERT_READY`。实际恢复需在窗口结束时由 Windows 执行，Activation 阶段未提前运行。

## F. Scope

```text
business rules modified? NO
manual jobs triggered? NO
additional Scheduler started? NO
Daily Brief frequency increased? NO
backend tests: 120 passed
```

现有依赖仍有一条 Starlette/httpx 弃用提示，不影响测试。观察期只记录自然运行情况，不继续开发业务功能。

## G. Final

**PASS**。原配置基线、48 小时窗口、七项临时 trigger、单实例常驻、每日一次 Daily Brief、一次性自动恢复任务及安全恢复脚本均已验证。现在进入自然运行观察，期满后再做 48 小时审计。

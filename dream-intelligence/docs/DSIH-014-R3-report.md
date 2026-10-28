# DSIH-014-R3｜Scheduler Self-Heal v0.1 验收记录

## A. Diagnosis Boundary

```text
known cause of 2026-09-29 exit?: UNKNOWN
confirmed consequence: Scheduler absent at 2026-09-30 08:30; Brief did not trigger
```

## B. Watchdog

```text
task: Dream Intelligence Scheduler Watchdog
trigger: 当前用户 AtLogOn，InteractiveToken
interval: 每 10 分钟，无限定结束时间
multiple instances: IgnoreNew
hidden: true
installed: YES（2026-10-01 01:00 Asia/Shanghai）
```

注册后只读核验：Watchdog 已 Enabled，触发器 XML 为 `PT10M`，执行时限为 `PT2M`。2026-10-08 复核时，主任务 Running / Enabled，Watchdog Ready / Enabled；G01 Revert 已在 2026-10-01 03:06:13 正常执行，结果 0，随后自身 Disabled，未被本工单改动。

## C. Recovery Acceptance

```text
registration baseline PID: 0
intentional kill: 未执行；已有真实自然掉线，无需人为再模拟
watchdog normal result: 2026-10-08 验收 `NOOP_RUNNING`，PID 17796 前后不变
watchdog natural recovery: 2026-10-03 至 10-07 日志共 12 次 `RECOVERED`
recovered PID: 最后一次自然恢复为 37668；手动停止后按原脚本恢复为 2248
single instance: 恢复后 DSIH venv 中长期 Scheduler 精确匹配 PID 仅 1 个；独立 OS lock 测试 3/3 PASS
7 jobs registered: 2026-10-08 恢复后日志确认 `job_count=7`、`schedule_profile=formal`
```

## D. Manual Stop

```text
main task disabled: YES（验收期间 Disabled，Scheduler PID=0）
watchdog result: NOOP_DISABLED，执行后仍 Disabled / PID=0
PID: 重新 Enable/Start 后 2248，主任务 Running / Enabled
```

## E. Runtime Logging

```text
runtime log: logs/scheduler-runtime.log（已产生真实运行记录）
exit code captured: YES（CHILD_EXITED 与 LAUNCHER_FAILED 均有退出时间/码；日志不能单独证明退出根因）
secrets present?: NO（按本机已配置 API Key 和 Webhook 值对 runtime/watchdog 日志做精确匹配，均未发现）
```

## F. Phase G

```text
G01 quality: PARTIAL
reason: 2026-09-29 夜间 Scheduler 掉线，2026-09-30 08:30 Brief 未运行
G01 Revert task preserved?: YES（2026-10-01 03:06:13 +08:00 自然执行成功；状态文件 active=false，正式频率已恢复）
```

2026-10-01 至 10-08 的数据库发送记录为 10-01、10-03、10-06、10-07、10-08 各一条 `SENT`；10-02、10-04、10-05 无发送记录。最近三天连续成功，但此前并非每日无漏发。Watchdog 多次恢复说明守护有作用，也说明进程仍曾掉线；不得把它表述为连续稳定运行。

## G. Tests

```text
Backend: 此前完整测试 120 passed；本次未改业务代码，未重复运行全量测试
TypeScript: 此前 PASS
Frontend build: 此前 PASS
PowerShell: 此前新增三个脚本语法检查 PASS；本次 `NOOP_RUNNING`、自然 `RECOVERED`、`NOOP_DISABLED` 均已实测
Single-instance lock: 3/3 PASS（第一次隔离环境运行受临时目录权限影响；在实际 Windows 用户环境复核全过）
```

## H. Scope Audit

```text
business jobs modified? NO
Phase G revert modified? NO
new business feature? NO
```

## I. Final

**PASS WITH WARNINGS**。Watchdog 安装、正常 NOOP、真实掉线后的自动恢复、人工停止保护、恢复后单实例和 7 个 Job 均通过。Launcher 已记录退出时间/码，日志未发现已配置的 API Key 或 Webhook 值。警告：10-02、10-04、10-05 缺 Daily Brief 发送记录，且此前有多次进程退出；虽然 10-06 至 10-08 连续发送成功，仍不可将 G01 视为完整稳定样本。下一步应单独开展 G02 观察，本工单到此停止。

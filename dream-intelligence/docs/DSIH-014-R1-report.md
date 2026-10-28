# DSIH-014-R1｜Feishu Daily Brief Scheduler 验收

## A. Config

```text
webhook configured?: YES（仅核对 SET，未显示地址）
brief time configured?: YES，08:30（Windows 用户环境变量）
brief timezone configured?: YES，Asia/Shanghai（Windows 用户环境变量）
secret logged?: NO
```

## B. Scheduler

```text
job count: 7
brief cron: 每天 08:30
brief timezone: Asia/Shanghai
max_instances: 1
coalesce: true
existing 6 jobs changed?: NO（测试对比全部 trigger、max_instances、coalesce）
```

时间和时区从环境变量读取；缺少或非法配置时不注册 Brief Job，并输出 `FEISHU_BRIEF_SCHEDULE_NOT_CONFIGURED`。验收时未发现持续运行的 Scheduler 进程；实际每日自动触发仍需运行现有 Scheduler 命令。未为本工单额外启动它，以免同时运行其它六项定时采集和分析。

## C. Real Send

```text
delivery_date: 2026-09-29（Asia/Shanghai）
first run: SENT
HTTP calls: 1
provider status: HTTP 200，业务码 0
message received?: 待手机端确认
```

发送前预览：Must Read 2 条、Relevant 显示 3 条、Market 1 只、未读公告显示 3 条；未改动原 Builder 内容。

## D. Duplicate Guard

```text
second same-day run: SKIP_ALREADY_SENT_TODAY
HTTP calls: 0
delivery rows: 1（feishu / daily_brief / 2026-09-29 / SENT）
```

## E. Database

```text
notification_deliveries before/after: 表不存在 → 1 条 SENT
existing business tables changed?: NO（10 张原表行数均与发送前一致）
read state changed?: NO（market_announcement_reads 仍为 1 条）
```

## F. Tests

```text
Backend: 116 tests passed
TypeScript: tsc --noEmit passed
Frontend build: Vite build passed
```

自动测试使用临时 SQLite 和 Fake Sender，覆盖配置、7 项注册、六项不变、时区日期、成功、失败、空内容、同日去重、手动 dry-run 和 `--once-brief` 独立运行；测试没有真实外发。

## G. Scope Audit

```text
Builder modified? NO
LLM called? NO
Critical Alert added? NO
Interactive callback added? NO
```

## H. Final

`PASS WITH WARNINGS`：真实发送、同日去重和自动测试均通过。手机端确认待补；当前未发现持续运行的 Scheduler 进程，因此每日自动触发尚未经过运行态验证。

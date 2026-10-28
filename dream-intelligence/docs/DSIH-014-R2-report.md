# DSIH-014-R2｜Windows 常驻运行与登录自启动验收

## A. Runtime

```text
project path: C:\Users\zhuxu\Documents\ChatGPT\信息收集平台\dream-intelligence
python executable: C:\Users\zhuxu\Documents\ChatGPT\信息收集平台\dream-intelligence\backend\.venv\Scripts\python.exe（Python 3.12.14）
launcher: scripts/run_scheduler_background.ps1
log: logs/scheduler.log（验收时存在、可读；超过 5 MB 时按启动/输出进行单份归档）
```

Launcher 在真实 `backend` 工作目录运行现有 `python -u -m app.commands.run_scheduler`，仅记录六项配置的 `SET/MISSING` 状态。没有复制或改写业务调度逻辑。

## B. Windows Task

```text
task name: Dream Intelligence Scheduler
exists: YES
enabled: YES
trigger: 当前用户 At Log On（MSFT_TaskLogonTrigger）
multiple instances: IgnoreNew
hidden: YES
logon type: Interactive
restart policy: 5 分钟后重启，最多 3 次
battery policy: 允许电池供电下启动并持续运行
```

Action 指向本项目的绝对 Launcher 路径，工作目录为项目根目录。登录触发由 Task Scheduler 配置验证；本工单未注销或重启电脑。

## C. Scheduler Process

```text
running: YES（最终检查时任务状态 Running）
PID: 21216（最终验收时，重启后会变化）
job count: 7（启动日志确认）
7 jobs unchanged?: YES（七项注册配置未改）
```

## D. Single Instance

```text
second launch result: SCHEDULER_ALREADY_RUNNING，退出码 2
existing process survived?: YES（原 PID 11088 保持运行）
stale lock test: PASS（持锁进程终止后可重新取得 OS 文件锁）
```

单实例锁只作用于长期运行入口；全部 `--once*` 一次性入口保持原语义。锁文件不含 PID、配置值或 Secret。

## E. Operations

```text
status: PASS（任务存在、启用状态、任务状态、PID、日志路径）
stop: PASS（先禁用任务，再停止 DSIH；未误杀另一个测试 Python 进程）
restart: PASS（重新启用任务并启动；最终为单个 PID 21216、7 jobs）
```

运维入口：`scripts/install_scheduler_task.ps1`、`scripts/scheduler_status.ps1`、`scripts/stop_scheduler.ps1`、`scripts/start_scheduler.ps1`。

## F. Environment Safety

```text
DSIH_LLM_BASE_URL: SET
DSIH_LLM_API_KEY: SET
DSIH_LLM_MODEL: SET
DSIH_FEISHU_WEBHOOK_URL: SET
DSIH_FEISHU_BRIEF_TIME: SET
DSIH_FEISHU_BRIEF_TIMEZONE: SET
```

日志只包含以上状态；按已配置的 API Key 和 Webhook 值扫描当前日志，均未出现。未记录或展示密钥值。

## G. Database

```text
manual business jobs triggered? NO
unexpected DB mutation? NO（验收前后 11 张现有表行数均一致）
```

验收期间未到自然计划时间，日志中没有业务 Job 执行摘要。

## H. Tests

```text
Backend: 119 tests passed
TypeScript: tsc --noEmit PASS
Frontend build: Vite PASS
PowerShell: 6 个脚本语法检查 PASS；实际 Task 安装/启停/状态 PASS
```

后端测试覆盖跨进程持锁、第二实例拒绝、异常退出后恢复、锁文件不含 Secret、一次性入口不受常驻锁影响。当前依赖的 FastAPI TestClient 发出一条 Starlette/httpx 弃用提示，不影响测试结果。

## I. Scope Audit

```text
Business scheduler jobs modified? NO
New business feature added? NO
Windows Service added? NO
Secrets logged? NO
```

## J. Final

**PASS**。Windows 登录触发任务已安装并启用，现有 Scheduler 当前在后台常驻；七项任务、单实例、状态查询、安全停止与恢复均已验证。下一步按工单进入 Phase G 真实使用观察，不在本工单增加功能。

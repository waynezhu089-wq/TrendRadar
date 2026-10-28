# DSIH-014-R2｜Windows 常驻运行与开机自启动 v0.1

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase F → Phase G 过渡  
优先级：P0

前置已验收：
- DSIH-014：飞书 Daily Brief 真人真实发送成功
- DSIH-014-R1：第 7 个 Scheduler Job 已注册
- 当前 Daily Brief：每天 `08:30`，`Asia/Shanghai`
- 同日重复发送保护已通过
- 当前问题：**Scheduler 尚未常驻运行，因此所有定时任务虽然“注册正确”，但电脑重启后不会自动恢复**

本工单只解决：

> **让 DSIH Scheduler 在 Windows 登录后自动常驻运行，并能安全停止、查看状态和日志。**

不开发任何新业务功能。

---

# 1. 本工单唯一目标

完成：

```text
Windows 登录
    ↓
Task Scheduler 自动启动 DSIH Scheduler
    ↓
后台常驻
    ↓
现有 7 个 Job 自动运行
```

同时提供：

```text
状态检查
日志
手动停止
手动启动
重复进程保护
```

---

# 2. 技术路线

优先使用 Windows 原生：

```text
Windows Task Scheduler
```

不要引入：

```text
NSSM
Docker
Windows Service Framework
Supervisor
PM2
第三方守护进程
```

1.0 保持本机轻量。

---

# 3. 启动时机

使用：

```text
At log on / 用户登录时
```

目标用户为当前 Windows 用户。

不要使用需要额外服务账号、密码托管或管理员长期凭据的复杂方案。

原因：
- 现有 `DSIH_LLM_*`
- `DSIH_FEISHU_WEBHOOK_URL`
- `DSIH_FEISHU_BRIEF_TIME`
- `DSIH_FEISHU_BRIEF_TIMEZONE`

目前都配置在 Windows 用户环境变量中。

登录触发最容易保证这些变量可见。

---

# 4. 必须复用现有 Scheduler

后台进程必须运行现有：

```bash
python -m app.commands.run_scheduler
```

禁止：
- 另写一套 Scheduler；
- 把 APScheduler 逻辑复制到 PowerShell；
- 改现有 7 个 Job 业务逻辑。

---

# 5. Python / 工作目录

先审计当前实际运行环境。

启动脚本必须使用：
- 当前项目实际 Python interpreter；
- 项目真实绝对路径；
- 正确工作目录。

项目当前路径预计：

```text
C:\Users\zhuxu\Documents\ChatGPT\信息收集平台\dream-intelligence
```

但 Codex 必须现场确认，不得仅凭工单猜。

若存在项目虚拟环境：

```text
优先使用项目 venv 的 python.exe
```

否则使用当前验收命令实际使用的 Python。

---

# 6. Launcher

新增一个轻量启动脚本，例如：

```text
scripts/run_scheduler_background.ps1
```

职责只包括：

```text
Set-Location 到项目
创建 logs 目录（如不存在）
启动现有 run_scheduler
stdout / stderr 进入日志
```

建议日志：

```text
logs/scheduler.log
```

不要在 Launcher 里写业务逻辑。

---

# 7. 日志

至少保证常驻 Scheduler 的输出可追踪。

日志中应能看到：

```text
scheduler started
7 jobs registered
job run summaries
warnings / failures
scheduler stopped
```

不得记录：
- DeepSeek API Key；
- Feishu Webhook；
- token / secret。

本工单不建设日志数据库。

---

# 8. 日志体积

避免日志无限增长。

优先：
- 复用现有 Python logging 的 rotating handler；
- 或 Launcher 启动时进行极简日志归档/截断。

保持轻量。

如果为此需要大规模重构现有 logging：

```text
不要做
```

最低要求是：
- 当前日志文件存在；
- 本工单验收期间可读。

复杂 log rotation 可 Backlog。

---

# 9. 单实例保护

必须避免：

```text
登录后 Task Scheduler 已运行一个 Scheduler
+
用户再次手动启动第二个常驻 Scheduler
```

至少有两层保护：

## A. Windows Task Scheduler

Task 设置：

```text
Multiple instances = Do not start a new instance
```

或等价：

```text
IgnoreNew
```

## B. 应用侧最小单实例保护

仅针对：

```text
长期运行模式：python -m app.commands.run_scheduler
```

增加轻量单实例锁。

允许实现：
- PID/lock file + 有效 PID 校验；
- Windows 文件锁；
- 其它不引入重量依赖的方案。

要求：

```text
第二个长期 Scheduler 启动
→ 明确退出
→ SCHEDULER_ALREADY_RUNNING
```

不得杀掉已有进程。

---

# 10. 一次性 CLI 不受常驻锁误伤

现有显式一次性入口：

```text
--once
--once-analysis
--once-market
--once-announcements
--once-brief
```

这些用于验收 / 运维。

不要因为长期进程锁而全部不可用，除非某个入口与常驻运行存在真实并发风险。

若需要保护：
- 给出明确错误；
- 不偷偷并发；
- 不大规模重构 CLI。

优先原则：

```text
长期常驻：严格单实例
一次性命令：保持原验收语义
```

---

# 11. Windows Scheduled Task

任务名建议：

```text
Dream Intelligence Scheduler
```

要求：

```text
Trigger: At log on
Action: 运行 background launcher
Hidden: true（如原生支持）
MultipleInstances: IgnoreNew
```

设置：

```text
失败后重启：5 分钟后
最多：3 次
```

若 Windows 原生配置难以稳定设置 restart：
- 可作为 Warning；
- 不为此引入第三方服务工具。

---

# 12. 不要求“用户未登录也运行”

v0.1 不要求：

```text
Run whether user is logged on or not
```

也不要求：
- Windows Service；
- 开机未登录即运行。

当前定义：

> 用户登录 Windows 后，DSIH 自动常驻。

这足够支撑个人 1.0。

---

# 13. 管理命令 / 脚本

提供最小运维入口，例如：

```text
scripts/install_scheduler_task.ps1
scripts/scheduler_status.ps1
scripts/stop_scheduler.ps1
```

可按当前项目风格适当合并。

最低要能完成：

### Install
```text
安装 / 更新 Windows Scheduled Task
```

### Status
输出：

```text
Task exists?
Task state
Scheduler process running?
PID
Log path
```

不得输出 Secret。

### Stop
只停止 DSIH Scheduler 常驻进程。

不要误杀其它 Python。

---

# 14. Start / Stop 的边界

手动停止后：

```text
Scheduled Task 不应立即无限重启
```

如 Windows Task Scheduler 的“失败重启”把人为 Stop 当失败：
- 停止脚本应先 Disable / Stop Task；
- 或使用等价安全顺序。

安装/启动脚本可再 Enable。

保持运维语义清晰。

---

# 15. 环境变量检查

Launcher 启动前只检查是否存在：

```text
DSIH_LLM_BASE_URL
DSIH_LLM_API_KEY
DSIH_LLM_MODEL

DSIH_FEISHU_WEBHOOK_URL
DSIH_FEISHU_BRIEF_TIME
DSIH_FEISHU_BRIEF_TIMEZONE
```

不要输出值。

如果部分缺失：

```text
Scheduler 仍允许启动
```

因为现有系统各 Job 已有自己的缺失配置保护。

日志只记录：

```text
VAR_NAME = SET / MISSING
```

---

# 16. 现有 7 个 Job 全部冻结

不得修改：

```text
NewsNow
GitHub
RSS
Auto Analysis
Market Collector
Market Announcements
Feishu Daily Brief
```

包括：
- 周期；
- Cron；
- 时区；
- offset；
- quota；
- Selector；
- Builder。

---

# 17. 真实验收

## Step A — 安装 Scheduled Task

执行安装脚本。

确认：

```text
Task exists = YES
Trigger = At log on
MultipleInstances = IgnoreNew
```

---

## Step B — 启动常驻 Scheduler

手动触发 Task 一次，不必注销登录。

确认：

```text
process running = YES
7 jobs registered
log created
```

---

## Step C — 第二实例保护

再次尝试启动长期 Scheduler。

必须：

```text
SCHEDULER_ALREADY_RUNNING
```

且已有 Scheduler 不受影响。

---

## Step D — 状态检查

执行 status：

```text
task exists
task enabled
task state
scheduler PID
log path
```

全部正常。

---

## Step E — Stop / Start

安全停止一次：

```text
scheduler process stopped
```

再通过 Scheduled Task 启动：

```text
scheduler process running
```

确认没有产生双实例。

---

## Step F — 登录自启动证据

本工单不要求真的重启整台电脑。

使用 Windows Task Scheduler 配置证据证明：

```text
AtLogOn trigger
```

即可。

如果用户愿意真人注销/重新登录，可作为额外证据，但不是 P0 Stop Rule。

---

# 18. 数据库边界

本工单本身不应主动执行任何业务 Job。

安装 / 状态 / 启停验证期间：

```text
不要为了验收手动触发采集/分析/飞书发送
```

因此预期：

```text
业务表 0 人为写入
```

注意：
如果 Scheduler 常驻期间某个 Job 恰好到了真实计划时间而自然运行：
- 如实记录；
- 不视为错误；
- 不伪造“数据库完全没变化”。

---

# 19. 测试

至少新增 / 验证：

```text
long-running scheduler acquires single-instance lock
second long-running process rejected
stale lock can recover safely
lock never exposes secrets
one-shot CLI compatibility
launcher command uses correct project/python
status identifies only DSIH scheduler
stop does not kill unrelated Python process
```

PowerShell 安装逻辑可做：
- 静态配置验证；
- 或本机实际任务验收。

后端现有测试必须继续全部通过。

另外继续：

```text
TypeScript PASS
Frontend build PASS
```

---

# 20. 明确禁止

禁止：

```text
Windows Service
Docker
NSSM
PM2

修改业务 Scheduler Job
新增业务功能

Critical Alert
Watchlist Alert
新 UI

LLM Prompt 修改
Market 修改
公告逻辑修改

远程部署
云服务器
```

---

# 21. Stop Rule

满足：

```text
Windows Scheduled Task 安装成功
+
At Logon trigger 正确
+
Scheduler 可后台常驻
+
7 个 Job 保持原配置
+
第二个长期实例会被拒绝
+
status 可确认 PID / Task / log
+
stop / restart 可控
+
Secret 不泄露
+
现有测试通过
```

立即停止。

---

# 22. 验收报告

保存：

```text
docs/DSIH-014-R2-report.md
```

## A. Runtime

```text
project path:
python executable:
launcher:
log:
```

## B. Windows Task

```text
task name:
exists:
enabled:
trigger:
multiple instances:
restart policy:
```

## C. Scheduler Process

```text
running:
PID:
job count:
7 jobs unchanged?:
```

## D. Single Instance

```text
second launch result:
existing process survived?:
stale lock test:
```

## E. Operations

```text
status:
stop:
restart:
```

## F. Environment Safety

只记录：

```text
DSIH_LLM_BASE_URL: SET/MISSING
DSIH_LLM_API_KEY: SET/MISSING
DSIH_LLM_MODEL: SET/MISSING
DSIH_FEISHU_WEBHOOK_URL: SET/MISSING
DSIH_FEISHU_BRIEF_TIME: SET/MISSING
DSIH_FEISHU_BRIEF_TIMEZONE: SET/MISSING
```

不得记录值。

## G. Database

```text
manual business jobs triggered? NO
unexpected DB mutation?:
```

## H. Tests

```text
Backend:
TypeScript:
Frontend build:
```

## I. Scope Audit

```text
Business scheduler jobs modified? NO
New business feature added? NO
Windows Service added? NO
Secrets logged? NO
```

## J. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 23. 后续边界

本工单通过后：

> **暂停增加功能，正式进入 Phase G｜真实使用。**

建议连续真实使用：

```text
3–7 天
```

重点记录：
- Daily Brief 是否真的每天值得看；
- Must Read 是否太多/太少；
- Relevant 是否有噪音；
- NewsNow 是否仍过量；
- Watchlist Boost 是否有效；
- Market 公告提醒是否实用；
- 飞书是否制造新的通知焦虑；
- 自动运行是否稳定。

不要立即开发 Critical Alert。

真实使用后再决定 DSIH 1.0 最后一轮修正。

---

# 24. 核心原则

这一步不是增加新能力。

而是：

> **让已经完成的能力真正“放着自己跑”。**

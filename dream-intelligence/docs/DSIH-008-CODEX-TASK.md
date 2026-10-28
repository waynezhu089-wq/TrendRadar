# DSIH-008｜Lightweight Scheduler v0.1

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：从“手动验证”进入“自动采集运行”  
优先级：P0

当前正式基线：

```text
sources = 9
items = 92
analysis = 9
```

已验证：
- NewsNow Connector
- GitHub Connector
- RSS Connector
- Analyzer v0.1.1
- Today Intelligence v0.1
- 全部生产 Mock 已退场
- RSS / GitHub / NewsNow 均有真实数据闭环

本工单只增加：

> **轻量定时采集。**

不自动调用 LLM。

---

# 1. 为什么本轮只调度采集

当前 NewsNow 已存在大量未分析 Raw Item。

如果本轮直接做：

```text
定时采集
+
自动 analyze_pending
```

可能造成：

```text
无关中文热点持续消耗 LLM
高价值 GitHub / RSS 被普通 Raw backlog 淹没
```

因此本轮只验证：

```text
Scheduler
→ Connectors
→ Raw Items
```

自动 Analyzer 队列另开工单设计。

---

# 2. 调度方式

优先使用轻量方案：

```text
APScheduler
```

或项目已有同等级轻量依赖。

禁止：

```text
Celery
Redis Queue
Kafka
Temporal
Airflow
Kubernetes CronJob
```

1.0 不需要分布式调度。

---

# 3. 运行形态

推荐独立进程：

```bash
python -m app.commands.run_scheduler
```

不要把 Scheduler 强耦合进 FastAPI Web 进程。

原因：

```text
避免多 worker 重复调度
API 重启不等于调度架构
未来可独立部署
```

如果当前项目结构有更自然但同样轻量的入口，可以最小调整。

---

# 4. v0.1 固定调度

使用当前项目需求中的简单频率：

```text
NewsNow   每 60 分钟
GitHub    每 2 小时
RSS       每 4 小时
```

不做 UI 配置。

可以把它们集中成小型代码常量 / config：

```text
NEWSNOW_INTERVAL_MINUTES = 60
GITHUB_INTERVAL_MINUTES = 120
RSS_INTERVAL_MINUTES = 240
```

测试可通过依赖注入或测试配置缩短间隔。

不要要求真实验收等待 4 小时。

---

# 5. Job 职责

每个 Job 只调用现有 Connector 能力。

例如：

```text
collect_newsnow_job()
collect_github_job()
collect_rss_job()
```

Job 本身不要重新实现：

```text
HTTP
normalize
dedup
database insert
```

必须复用当前已经验证的采集路径。

---

# 6. 不自动调用 Analyzer

本工单严格：

```text
LLM calls = 0
```

Scheduler 不得调用：

```text
Analyzer
analyze_pending
DeepSeek
Priority calculation
```

新 Raw Item 等后续 Auto Analysis Queue 决定如何消费。

---

# 7. 重入与重叠保护

同一种 Job 不允许并发重叠执行。

例如 NewsNow 上一轮未完成时：

```text
下一次 NewsNow 不再启动第二实例
```

若使用 APScheduler，采用其轻量原生能力即可，例如：

```text
max_instances = 1
coalesce = true
```

不要设计分布式锁。

---

# 8. 单 Job 失败隔离

要求：

```text
NewsNow FAIL
≠ GitHub 停止
≠ RSS 停止
```

某个 Source 内已有 Connector 单源失败隔离继续沿用。

Scheduler 只负责记录结果，不重新实现错误恢复框架。

---

# 9. 运行日志

每次 Job 至少输出：

```text
job
started_at
finished_at
received
inserted
skipped
failed
status
```

例如：

```text
[GitHub]
received=3
inserted=0
skipped=3
failed=0
status=OK
```

日志不要输出：

```text
API Key
GitHub Token
完整 LLM Secret
```

本工单不建立新日志数据库表。

普通应用日志即可。

---

# 10. 空结果处理

如果某源：

```text
HTTP 成功
但 received = 0
```

不要伪装成“新增成功”。

记录实际：

```text
received=0
inserted=0
```

如果 Connector 已能区分 warning / failed，沿用。

不要为 DeepMind 单独写特殊规则。

---

# 11. 启动时行为

Scheduler 启动后：

```text
不要立刻无条件把所有 Job 重跑一遍
```

优先正常按计划运行。

为了方便人工验收，允许提供：

```bash
python -m app.commands.run_scheduler --once
```

或等价的“一次执行全部采集 Job”模式。

`--once` 必须复用同一批 Job 函数，不另写一套采集逻辑。

---

# 12. 优雅停止

支持：

```text
Ctrl+C / SIGINT
```

正常退出 Scheduler。

不留下损坏事务。

不要求实现复杂进程守护。

---

# 13. 数据库行为

本工单允许：

```text
新增真实 Raw Items
更新现有 Source 的 last_run（如果当前 Connector 已这么做）
```

不得：

```text
修改已有 Raw Item 内容
修改已有 Analysis
新增 Analysis
删除数据
```

因此：

```text
analysis 必须保持 9
```

---

# 14. Today 行为

Scheduler 本身不修改 Today。

因为新 Raw Item 未分析：

```text
Today card 数量不应仅因 Scheduler 采集而增加
```

必须继续：

```text
GET /api/v1/today → 200
```

---

# 15. 测试

至少新增：

```text
scheduler registers 3 jobs
intervals correct
same job max_instances=1 / equivalent overlap protection
one job failure does not stop other jobs
--once reuses production job functions
scheduler jobs do not call Analyzer
graceful shutdown smoke test（可轻量）
```

自动测试不得依赖真实等待 60/120/240 分钟。

使用 fake connector / monkeypatch / small test scheduler。

---

# 16. 真实验收

不等待计划周期。

使用：

```text
--once
```

执行一次真实采集：

```text
NewsNow
GitHub
RSS
```

记录结果。

允许：
- 全部是 SKIP
- 出现上游刚发布的新 Raw Item
- 某单源发生真实外部 warning

但必须满足：

```text
Scheduler process 能正常启动
三个 Job 均被执行
单 Job 失败不拖垮整体
analysis 仍为 9
Today 仍为 200
```

---

# 17. 不做持久化 Job Store

v0.1 不需要：

```text
scheduler_jobs table
APScheduler SQLAlchemyJobStore
任务历史数据库
复杂运行 Dashboard
```

进程重启后重新根据代码注册 3 个固定 Job 即可。

---

# 18. 明确禁止

禁止：

```text
自动 LLM 分析
自动 Priority
自动飞书通知

Watchlist
Feedback
Market Watch

新增 Connector
新增 RSS Source
Browser Scout

Celery
Redis
Kafka
Temporal
Airflow

MCP
RAG
Agent
Embedding
```

---

# 19. Stop Rule

满足：

```text
Scheduler 可启动
+
3 个固定采集 Job 注册正确
+
--once 真实跑通
+
失败隔离通过
+
无 LLM 调用
+
analysis 保持 9
+
Today 200
+
全部测试通过
```

立即停止。

---

# 20. 验收报告

保存：

```text
docs/DSIH-008-report.md
```

## A. Scheduler

```text
Implementation:
Process entry:
Timezone:
Persistent job store? NO
```

## B. Registered Jobs

```text
NewsNow interval:
GitHub interval:
RSS interval:
Overlap protection:
```

## C. Once Run

逐 Job：

```text
received:
inserted:
skipped:
failed:
status:
```

## D. Failure Isolation

```text
Test:
Result:
```

## E. Database

```text
sources before/after:
items before/after:
analysis before/after:
existing Raw mutated? NO
existing Analysis mutated? NO
```

## F. Today

```text
HTTP:
Card counts:
New unanalyzed Raw leaked into Today? NO
```

## G. LLM Audit

```text
LLM called? NO
Analyzer invoked? NO
```

## H. Tests

```text
Backend:
TypeScript:
Frontend build:
```

## I. Scope Audit

```text
Analyzer modified? NO
Priority modified? NO
Today modified? NO
Connector logic duplicated? NO
New Connector added? NO
Feishu added? NO
Queue infrastructure added? NO
```

## J. Warnings

记录真实外部源 warning。

## K. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 21. 后续边界

本工单完成后，下一阶段才讨论：

```text
Auto Analysis Queue v0.1
```

它需要先解决：

```text
哪些 Raw Item 应优先消耗 LLM？
每轮最多分析多少？
GitHub / RSS 是否应优先于普通 NewsNow？
如何避免 backlog 无限消耗模型？
```

不要在本工单提前实现。

---

# 22. 核心原则

这一步只让 DSIH 从：

```text
“我手动点一下才采集”
```

变成：

```text
“系统自己按时采集”
```

还不让它自动决定 LLM 成本与分析队列。

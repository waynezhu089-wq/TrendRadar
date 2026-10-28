# DSIH-009-R1｜将已验证 Auto Analysis Queue 接入 Scheduler

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：1.0 自动运行闭环  
优先级：P0

前置已验收：
- DSIH-008：Scheduler v0.1 PASS
- DSIH-009：Auto Analysis Queue v0.1 PASS
- Selector 已真实验证，规则冻结
- `analyze_queue --dry-run / --once` 已可用

本工单只做：

> 把 **DSIH-009 已验证的分析队列** 注册为 Scheduler 第 4 个 Job。

不修改筛选规则，不扩大来源，不新增业务功能。

---

# 1. Scheduler 最终 4 个 Job

保持已有：

```text
NewsNow Collector    每 60 分钟
GitHub Collector     每 120 分钟
RSS Collector        每 240 分钟
```

新增：

```text
Auto Analysis Queue  每 240 分钟
```

Auto Analysis 必须复用 DSIH-009 已验证的：

```text
selector
→ max 6
→ GitHub > RSS > NewsNow
→ NewsNow max 2
→ NewsNow gate terms
→ 7-day lookback
→ Analyzer v0.1.1
```

禁止复制一套新筛选逻辑。

---

# 2. 分析规则全部冻结

本工单禁止修改：

```text
7-day lookback
MAX_TOTAL = 6
GitHub quota = 3
RSS quota = 3
NewsNow quota = 2
ANALYSIS_GATE_TERMS
Tier order
Candidate ordering
Priority formula
Analyzer prompt/profile
Today thresholds
```

如果集成时发现接口不适配：

```text
STOP / BLOCKED
```

不要借机调参。

---

# 3. Scheduler Job

新增轻量 Job，例如：

```text
run_auto_analysis_job()
```

它只负责调用现有分析队列核心服务。

不得在 Scheduler 中重新实现：

```text
candidate selection
LLM calls
repair
Priority
DB writes
```

---

# 4. 调度频率与错峰

Auto Analysis：

```text
interval = 240 minutes
```

为避免和 RSS Collector 同时启动，首次运行应与 RSS 采集 **错开约 10–15 分钟**。

目标关系：

```text
RSS collect
   ↓
约 10–15 min
   ↓
Auto Analysis
```

不要求复杂 Cron。

只需使用 APScheduler 可维护的轻量 `next_run_time` / start offset 等方式。

---

# 5. 重叠保护

Auto Analysis Job 必须：

```text
max_instances = 1
coalesce = true
```

或现有调度框架中的等价设置。

上一轮分析未结束：

```text
下一轮不得并发启动
```

不要使用 Redis / 分布式锁。

---

# 6. Provider 故障策略

区分两类失败：

## A. 单 Item JSON / Schema 失败

继续使用 Analyzer v0.1.1：

```text
最多 1 次 repair
```

该 Item 最终失败后：

```text
继续后续候选
```

## B. Provider / 网络级失败

例如：

```text
LLM_REQUEST_ERROR
连接失败
认证失败
Provider 5xx / timeout（达到现有单次请求边界后）
```

若已明确是 Provider 级不可用：

```text
当前 Analysis Job 立即停止剩余候选
```

避免同一次任务对 6 条候选连续制造无意义失败。

要求：

```text
不立即自旋重试
不触发第二个 Job
等待下一次 240 分钟调度周期
```

不要新增复杂熔断器或持久化 cooldown。

---

# 7. CLI 安全兼容

现有：

```bash
python -m app.commands.run_scheduler --once
```

必须保持 **collector-only** 行为，不得因本工单突然开始调用 LLM。

新增显式验收入口，例如：

```bash
python -m app.commands.run_scheduler --once-analysis
```

其行为：

```text
只执行一次 Auto Analysis Job
```

必须复用与定时任务相同的 Job 函数。

不要新增 `--once-all`，除非当前 CLI 结构确实必须；优先最小改动。

---

# 8. Dry-run 继续保留

DSIH-009 的：

```bash
python -m app.commands.analyze_queue --dry-run
```

必须继续可用。

Scheduler 不需要自己的 dry-run。

---

# 9. Job 日志

每次 Auto Analysis Job 至少记录：

```text
job=auto_analysis
started_at
finished_at
selected
analyzed
skipped
failed
normal_llm_calls
repair_calls
status
```

若 Provider 级失败导致提前停止：

```text
status=PROVIDER_UNAVAILABLE
aborted_remaining=<N>
```

不得输出 Secret / API Key。

---

# 10. Scheduler 与 Today 的关系

Scheduler 只写 Analysis。

Today 继续使用现有规则自动读取。

本工单禁止：

```text
修改 Today API
修改 Today bucket
主动 push UI
```

---

# 11. 正式数据库边界

允许：

```text
在 --once-analysis 或未来定时 Job 中新增 Analysis
```

禁止：

```text
修改 Raw Item
修改旧 Analysis
删除数据
修改 Source
```

如果当前没有 eligible candidate：

```text
selected = 0
LLM calls = 0
status = OK
```

这也是合法验收结果。

不得为了制造测试样本污染正式数据库。

---

# 12. 自动测试

至少新增：

```text
scheduler registers auto-analysis as 4th job
auto-analysis interval = 240 min
analysis job is offset from RSS
max_instances=1 / overlap protection
coalesce=true / equivalent
job reuses existing queue service
selector constants unchanged
scheduler --once remains collector-only
--once-analysis invokes analysis job only
zero candidates => zero LLM calls
provider-level failure aborts remaining candidates for this run
schema failure remains per-item isolated
collector jobs continue even if analysis job fails
```

使用 Fake LLM / fake services。

不得真实联网完成自动测试。

---

# 13. 真实验收

## Step A — Scheduler Registration

启动 Scheduler，记录 4 个 Job：

```text
NewsNow
GitHub
RSS
Auto Analysis
```

确认 interval / offset / overlap protection。

不需要等待 4 小时。

## Step B — Collector Compatibility

执行：

```text
run_scheduler --once
```

必须仍只采集：

```text
NewsNow / GitHub / RSS
```

确认：

```text
LLM called? NO
```

## Step C — Analysis Integration

执行：

```text
run_scheduler --once-analysis
```

允许两种结果：

### 当前有候选
```text
selected <= 6
NewsNow <= 2
真实分析按现有规则完成
```

### 当前无候选
```text
selected = 0
LLM calls = 0
```

两种都可 PASS。

## Step D — Today

```text
GET /api/v1/today → 200
```

如 Step C 新增 Analysis，应自然出现在对应 bucket。

---

# 14. 回归

必须：

```text
Backend tests PASS
Today API 200
TypeScript PASS
Frontend build PASS
```

---

# 15. 明确禁止

禁止：

```text
修改 Selector
修改 Gate Terms
修改 Quota
修改 Analyzer
修改 Prompt/Profile
修改 Priority
修改 Today

新增 Connector / Source
RSS 扩源
Watchlist
Feedback
Market Watch
Feishu

Celery
Redis
Kafka
Temporal
Airflow

MCP
RAG
Embedding
Agent
```

---

# 16. Stop Rule

满足：

```text
第 4 个 Job 注册成功
+
240 分钟周期正确
+
与 RSS 错峰
+
重叠保护有效
+
--once 保持 collector-only
+
--once-analysis 复用真实 Job
+
Provider 故障不会同轮打满剩余候选
+
Today 200
+
全部测试通过
```

立即停止。

---

# 17. 验收报告

保存：

```text
docs/DSIH-009-R1-report.md
```

## A. Scheduler Jobs

```text
NewsNow:
GitHub:
RSS:
Auto Analysis:
Analysis offset:
max_instances:
coalesce:
```

## B. Collector Once

```text
NewsNow:
GitHub:
RSS:
LLM called? NO
```

## C. Analysis Once

```text
selected:
analyzed:
skipped:
failed:
normal LLM calls:
repair calls:
provider abort?:
```

列出候选 item_id / source / title / result。

## D. Cost Guard

```text
selected <= 6?
NewsNow <= 2?
selector policy changed? NO
```

## E. Database

```text
sources before/after:
items before/after:
analysis before/after:
Raw mutation: NO
Old Analysis mutation: NO
```

## F. Today

```text
HTTP:
Must Read:
Relevant:
Other:
```

## G. Failure Isolation

```text
Provider failure test:
Schema failure test:
Collectors unaffected:
```

## H. Regression

```text
Backend:
TypeScript:
Frontend build:
```

## I. Scope Audit

```text
Selector modified? NO
Gate terms modified? NO
Analyzer modified? NO
Priority modified? NO
Today modified? NO
New infrastructure added? NO
```

## J. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 18. 后续边界

本工单通过后，DSIH 将第一次形成：

```text
自动采集
→ 自动候选筛选
→ 有界 AI Analysis
→ Priority
→ Today
```

下一阶段才讨论：

```text
Feedback / Watchlist
```

不要在本工单提前实现。

---

# 19. 核心原则

不是让 DSIH “尽可能多分析”。

而是：

> **让已经验证过的成本闸门安全地自动运行。**

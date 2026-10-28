# DSIH-012-R2｜Market Scheduler v0.1 — 收盘后自动更新

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase E / Market Watch 自动化  
优先级：P0

前置已验收：
- DSIH-012：A 股真实日线链路 PASS
- DSIH-012-R1：最近 30 个交易日日线 + Technical State PASS
- `002782 | SZ | 可立克` 已有 30 个交易日日线
- `collect_market --once` 已验证为“只采最近一个可用交易日”
- Technical State 由数据库快照即时计算，不持久化

本工单只做：

> **把现有 Market 增量采集挂进 Scheduler，在中国 A 股收盘后自动执行。**

不新增指标，不调用 LLM，不做新闻/公告。

---

# 1. 本工单唯一目标

在现有 Scheduler 中增加第 5 个 Job：

```text
Market Collector
```

执行逻辑必须复用现有：

```text
collect_market --once
```

或其底层同一 service。

不得复制第二套 Provider / DB 写入逻辑。

---

# 2. 调度时间

使用明确市场时区：

```text
timezone = Asia/Shanghai
```

第一版固定：

```text
周一至周五
16:10
Asia/Shanghai
```

理由：

```text
A 股 15:00 收盘
给上游数据源留出更新时间
```

不要依赖运行机器本地时区。

---

# 3. 节假日处理

v0.1 不引入中国交易日历。

节假日 / 非交易日：

```text
Provider 返回最近可用交易日
→ UNIQUE(symbol, market, date)
→ 已存在则 SKIP
```

因此允许：

```text
Job 正常运行
inserted = 0
skipped = N
status = OK
```

不要增加节假日服务或交易日历依赖。

---

# 4. Scheduler 现有 Job 不变

保持当前：

```text
NewsNow Collector
GitHub Collector
RSS Collector
Auto Analysis
```

它们的：
- 周期
- offset
- max_instances
- coalesce

全部不改。

新增 Market Job 不得影响现有 4 个 Job。

---

# 5. Market Job 配置

Market Job：

```text
cron: Monday-Friday 16:10
timezone: Asia/Shanghai
max_instances = 1
coalesce = true
```

如果当前 Scheduler 封装不适合 Cron，可做最小适配。

禁止把整个 Scheduler 重构成另一套框架。

---

# 6. Job 逻辑

新增最小函数，例如：

```text
collect_market_job()
```

它只负责：

```text
读取 enabled market_watchlist
→ 调用现有 Market collection service
→ 保存最近交易日 snapshot
→ 输出统计
```

不得在 Job 中重新实现：

```text
Tencent HTTP
symbol normalize
snapshot dedup
technical indicators
```

---

# 7. Job 日志

至少输出：

```text
job=market
started_at
finished_at
watchlist_count
received
inserted
skipped
failed
status
```

每只股票可附：

```text
symbol
market
date
result
```

不得输出任何 Secret。

---

# 8. 失败隔离

单只股票失败：

```text
不影响其它 Market Watchlist 项
```

Market Job 整体失败：

```text
不得影响 NewsNow / GitHub / RSS / Auto Analysis Job
```

继续沿用 Scheduler 的 Job 隔离方式。

不要引入重试队列、熔断器、Redis。

---

# 9. 手动验收入口

现有：

```bash
python -m app.commands.collect_market --once
```

必须保持原样可用。

另外，若当前 Scheduler CLI 结构允许，新增显式：

```bash
python -m app.commands.run_scheduler --once-market
```

只执行一次 Market Job，用于验收。

如果为了加 `--once-market` 需要明显扩大 CLI 重构，则不加；直接复用 `collect_market --once` 作为真实执行验收。

优先最小改动。

---

# 10. Technical State

本工单不修改 Technical State 代码。

当新日线进入：

```text
GET /api/v1/market
```

应自然基于最新数据库快照重新计算：

```text
change_pct
MA5 / MA10 / MA20
20 日区间
5 日均量 / 量比
```

不得新增指标缓存表。

---

# 11. 数据库边界

允许：

```text
market_snapshots 新增最新交易日行
```

禁止修改：

```text
sources
items
analysis
feedback
intelligence watchlist
market_watchlist
旧 market_snapshots
```

同交易日第二次运行：

```text
不得新增重复行
```

---

# 12. 不调用 LLM

严格：

```text
LLM calls = 0
```

不得：

```text
AI Daily Review
涨跌归因
新闻解释
买卖建议
预测
```

---

# 13. 自动测试

至少新增：

```text
scheduler registers Market as 5th job
Market cron = Mon-Fri 16:10
Market timezone = Asia/Shanghai
max_instances=1
coalesce=true
existing 4 jobs unchanged
Market job reuses existing collection service
same trading date dedups
single symbol failure isolation
Market job failure does not affect other jobs
no LLM invocation
technical state reads newest snapshot without code changes
```

自动测试使用 Fake Provider / temp DB。

不要真实等待到 16:10。

---

# 14. 真实验收

不等待真实收盘时间。

执行一次显式 Market Job：

```text
--once-market
```

或现有：

```text
collect_market --once
```

记录：

```text
watchlist_count
inserted
skipped
failed
latest date
```

如果当前数据库已经有当天最新交易日：

```text
inserted=0
skipped=1
```

也可 PASS。

验收重点是：

```text
Job 路径和定时注册正确
```

不是强行制造新交易日。

---

# 15. API / 页面回归

执行后：

```text
GET /api/v1/market → 200
```

确认：
- 最新 snapshot 正常；
- technical 正常；
- `/market` 页面正常。

不得修改页面 UI。

---

# 16. 明确禁止

禁止：

```text
交易日历
节假日 API
第二 Market Provider

新技术指标
图表 / K线
公告 / 新闻
AI Daily Review

买卖建议
目标价
预测
自动交易

修改 Candidate Selector
修改 Analyzer
修改 Priority
修改 Today
修改现有 Scheduler 4 个 Job
```

---

# 17. Stop Rule

满足：

```text
Market 第 5 个 Scheduler Job 注册成功
+
Mon-Fri 16:10 Asia/Shanghai 正确
+
max_instances=1 / coalesce=true
+
真实一次 Market Job 跑通
+
同日 dedup 正常
+
Market API 200
+
Technical State 正常
+
LLM 0 调用
+
现有 4 个 Job 不变
+
全部测试通过
```

立即停止。

---

# 18. 验收报告

保存：

```text
docs/DSIH-012-R2-report.md
```

## A. Scheduler Registration

```text
job count:
Market job:
cron:
timezone:
max_instances:
coalesce:
existing jobs changed? NO
```

## B. Real Once

```text
watchlist_count:
received:
inserted:
skipped:
failed:
latest date:
```

## C. Duplicate Guard

```text
same-date duplicate row? NO
```

## D. Database

```text
sources changed? NO
items changed? NO
analysis changed? NO
feedback changed? NO
intelligence watchlist changed? NO
market_watchlist changed? NO
market_snapshots before/after:
old snapshots mutated? NO
```

## E. Market API

```text
HTTP:
latest snapshot:
technical object:
```

## F. Failure Isolation

```text
single symbol failure:
other scheduler jobs unaffected:
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
existing scheduler jobs modified? NO
Provider modified? NO
Technical indicators modified? NO
Today modified? NO
Trading logic added? NO
```

## J. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 19. 后续边界

本工单通过后，Market Watch 的“行情基础层”可视为完成。

下一阶段不要立刻堆指标。

优先进入：

```text
DSIH-013｜Market News / Announcement Intake v0.1
```

只做与 Market Watchlist 相关的公告 / 新闻采集。

之后再决定是否做：

```text
AI Daily Review
```

---

# 20. 核心原则

Market Scheduler v0.1 只负责：

> **“收盘后自动把最新可用日线放进系统。”**

不负责解释：

> **“为什么涨跌，以及下一步该怎么做。”**

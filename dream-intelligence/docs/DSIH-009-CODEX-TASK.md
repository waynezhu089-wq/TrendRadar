# DSIH-009｜Auto Analysis Queue v0.1 — 候选筛选与有界分析

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：从“自动采集”进入“有成本约束的自动分析”  
优先级：P0

当前已知正式基线（DSIH-008 后）：

```text
sources = 9
items = 138
analysis = 9
```

其中 Scheduler 一次 `--once` 新增了约 46 条 NewsNow Raw Item。

本工单只解决一个问题：

> **哪些未分析 Raw Item 值得优先花 LLM 成本？**

本轮先完成：
- 确定性候选筛选
- dry-run 可解释预览
- 一次有上限的真实分析验证

**暂不把 Analyzer Job 注册进 Scheduler。**

---

# 1. 为什么不能直接 analyze_pending

当前系统中未分析 Raw Item 很多，NewsNow 每小时还会持续增长。

禁止直接：

```text
SELECT all unanalyzed
→ 全部送 DeepSeek
```

否则会造成：

```text
普通热点消耗大量 LLM
GitHub / RSS 高价值内容被 backlog 淹没
成本不可控
```

因此先建立一个最小、确定性、可解释的 Candidate Selector。

---

# 2. 不建 Queue 数据库表

v0.1 不增加：

```text
analysis_queue table
message broker
Celery
Redis
Kafka
```

Queue v0.1 只是：

```text
DB 中未分析 Item
→ deterministic selector
→ bounded candidate list
→ Analyzer
```

已有 `analysis` 表天然充当“是否处理过”的状态。

---

# 3. 候选基本条件

只考虑：

```text
没有 Analysis 的 Item
```

时间字段：

```text
effective_time =
published_at
若 NULL → captured_at
```

只考虑最近：

```text
7 天
```

的 Raw Item。

7 天以前的历史 backlog：

```text
默认不自动分析
```

不删除、不改写，只是不进入自动候选。

---

# 4. Source Tier

按 Source 类型分层：

```text
Tier 1 = github
Tier 2 = rss
Tier 3 = NewsNow / hotboard
```

优先级：

```text
GitHub > RSS > NewsNow
```

原因：
- GitHub / 官方 RSS 是高可信结构化源
- NewsNow 量大、噪声更高

不要把这一层级写入 Priority 公式。

它只决定“谁先获得一次 LLM 分析机会”。

---

# 5. NewsNow 进入候选的轻量门槛

GitHub / RSS：

```text
无需关键词命中
```

NewsNow：

```text
必须至少命中 1 个分析门槛词
```

新增一个极小配置常量，例如：

```text
ANALYSIS_GATE_TERMS = [
  "AI",
  "人工智能",
  "大模型",
  "LLM",
  "模型",
  "视频生成",
  "图生视频",
  "ComfyUI",
  "MiniMax",
  "Seedance",
  "Agent",
  "智能体",
  "MCP",
  "workflow",
  "工作流",
  "browser",
  "浏览器自动化",
  "自动化",
  "开源",
  "GitHub"
]
```

匹配范围：

```text
title
+
content（如有）
```

大小写不敏感。

本轮不要：
- 中文分词
- Embedding
- LLM 预筛
- 语义搜索
- Watchlist 系统

如果现有 `intelligence_profile` 已有可直接复用的结构化关键词配置，可以最小复用；不要解析自然语言 Profile 来动态生成关键词。

---

# 6. 每轮硬上限

一次真实分析 run：

```text
MAX_TOTAL = 6
```

Source quota：

```text
GitHub  最多 3
RSS     最多 3
NewsNow 最多 2
```

总数仍不得超过：

```text
6
```

选择顺序：

```text
1. GitHub：effective_time DESC
2. RSS：effective_time DESC
3. NewsNow：命中关键词数量 DESC
            effective_time DESC
```

如果 Tier 1 / 2 未用满，总额度可以留给后续 Tier，但：

```text
NewsNow 永远最多 2
```

这样即使 backlog 很大，也不会一轮吞掉几十条 LLM 调用。

---

# 7. Candidate Selector

实现一个小型服务 / 纯函数，例如：

```text
select_analysis_candidates(...)
```

返回每条至少：

```text
item_id
source
source_type
title
effective_time
gate_matches
selection_reason
```

`selection_reason` 示例：

```text
GITHUB_RECENT
RSS_RECENT
NEWSNOW_GATE_MATCH: AI, 视频生成
```

必须可解释。

不要做复杂评分引擎。

---

# 8. Dry Run

提供命令，例如：

```bash
python -m app.commands.analyze_queue --dry-run
```

Dry-run：

```text
0 LLM calls
0 DB writes
```

输出：

```text
candidate count
item_id
source
title
tier
gate matches
selection reason
```

并输出被排除的统计：

```text
too_old
newsnow_no_gate_match
already_analyzed
selected
```

不需要打印所有被排除标题。

---

# 9. Once Run

提供：

```bash
python -m app.commands.analyze_queue --once
```

行为：

```text
selector
→ 最多 6 条
→ 逐条调用现有 dsih-analyzer-v0.1.1
→ 写 Analysis
```

必须复用现有：

```text
Analyzer
repair retry
Priority calculation
duplicate guard
```

不要复制分析逻辑。

---

# 10. 单条失败隔离

例如：

```text
candidate 1 PASS
candidate 2 schema fail + repair fail
candidate 3...
```

要求：

```text
candidate 2 FAIL
但 3/4/5/6 继续
```

最终报告：

```text
selected
analyzed
skipped
failed
repair_count
```

---

# 11. LLM 硬成本保护

一次 `--once`：

```text
最多 6 个 Item
```

每 Item：

```text
最多 1 次正常调用
+
现有机制允许的 1 次 repair
```

因此理论最大：

```text
12 次 provider calls
```

但正常目标 <= 6。

不得自动递归处理下一批。

---

# 12. 本轮不接 Scheduler

**DSIH-008 Scheduler 不修改。**

本工单不注册：

```text
Auto Analysis Job
```

原因：

先观察 selector 真实选出来的是什么，再决定是否适合长期自动运行。

---

# 13. Today 验证

完成一次真实 `--once` 后：

```text
GET /api/v1/today
```

必须：

```text
HTTP 200
```

记录新 Analysis 分布：

```text
Must Read
Relevant
Other
```

以及本轮 6 条（或实际少于 6 条）各自 bucket。

不得调整 Today 阈值。

---

# 14. 数据库边界

允许：

```text
新增 Analysis
```

禁止：

```text
修改 Raw Item
删除 Raw Item
修改旧 Analysis
修改 Source
```

如果本轮选中 N 条并全部成功：

```text
analysis 9 → 9 + N
```

---

# 15. 自动测试

至少新增：

```text
only unanalyzed items eligible
7-day lookback
published_at NULL falls back to captured_at
github tier before rss before newsnow
newsnow requires gate term
newsnow case-insensitive matching
newsnow max 2
total max 6
deterministic ordering
dry-run causes zero LLM calls and zero writes
one candidate failure does not stop later candidates
already analyzed candidate is skipped
```

使用 Fake LLM / in-memory DB。

不要用真实 API 做自动测试。

---

# 16. 真实验收步骤

## Step A — Dry Run

对正式 DB 执行：

```text
--dry-run
```

保存完整候选列表到报告。

先验证：

```text
候选数量 <= 6
NewsNow <= 2
高可信 GitHub/RSS 优先
```

## Step B — Real Once

仅当 Step A 满足规则后：

```text
--once
```

最多分析 6 条。

## Step C — Duplicate Guard

对同一时点立即再次 dry-run：

已成功分析的 Item 不得再次出现。

不要第二次真实调用模型。

---

# 17. 报告必须展示候选

保存：

```text
docs/DSIH-009-report.md
```

## A. Policy

```text
Lookback:
Max total:
GitHub quota:
RSS quota:
NewsNow quota:
Gate terms:
```

## B. Dry Run

逐条：

```text
item_id
source
source_type
title
effective_time
gate_matches
selection_reason
```

统计：

```text
already_analyzed:
too_old:
newsnow_no_gate_match:
selected:
```

## C. Real Once

逐条：

```text
item_id
result
category
priority
dreamstream_relevance
recommended_action
provider_calls
repair_used
```

## D. Database

```text
sources before/after:
items before/after:
analysis before/after:
Raw mutation: NO
Old Analysis mutation: NO
```

## E. Today

```text
HTTP:
Must Read:
Relevant:
Other:
new item buckets:
```

## F. Cost Guard

```text
selected <= 6?
NewsNow <= 2?
normal LLM calls:
repair calls:
total provider calls:
```

## G. Tests

```text
Backend:
TypeScript:
Frontend build:
```

## H. Scope Audit

```text
Scheduler modified? NO
Connector modified? NO
Priority modified? NO
Today rules modified? NO
New DB table added? NO
Queue framework added? NO
```

## I. Quality Notes

人工可审计地列出：
- 是否选到明显无关 NewsNow
- 是否漏掉明显高相关但没被门槛词命中的样本（如观察到）
- 不在本单现场调规则

## J. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 18. Stop Rule

满足：

```text
Selector deterministic
+
Dry-run 合理
+
真实分析 <=6 条
+
成本上限有效
+
失败隔离有效
+
Today 200
+
测试通过
```

立即停止。

---

# 19. 后续

只有 DSIH-009 人工验收通过后，下一张工单才允许：

```text
DSIH-009-R1
→ 把这个已验证 Selector 注册进 Scheduler
```

在这之前不得自动周期性调用 DeepSeek。

---

# 20. 核心原则

这一阶段不是追求“把所有新闻都分析”。

而是：

> **只让最值得花模型成本的少数 Raw Item 获得 Analysis。**

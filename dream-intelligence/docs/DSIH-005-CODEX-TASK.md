# DSIH-005｜Today Intelligence v0.1

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase D / Today  
优先级：P0

前置状态：
- DSIH-003：NewsNow 真实 Connector 已 PASS
- DSIH-004：真实 DeepSeek Analyzer 已 PASS
- DSIH-004-R2：Today nullable published_at 回归已修复
- DSIH-004-R3：正负样本相对排序已 PASS

本工单只把现有 Analysis 正确组织成 Today Intelligence。

---

# 1. 本工单唯一目标

将现有 `/api/v1/today` 从“简单返回已有卡片”升级为第一版真正的 Today：

```text
Analysis
  ↓
Deterministic Today Rules
  ↓
Must Read / Relevant / Other
  ↓
Priority 排序
  ↓
React Today
```

不新增采集、不新增 AI 调用。

---

# 2. Analyzer 冻结边界

本工单禁止修改：

```text
Prompt
Intelligence Profile
Priority Formula
recommended_action 逻辑
Analyzer
LLM Client
```

R3 已证明：

```text
Priority High > Medium > Low
Dream Stream relevance High > Medium > Low
```

`recommended_action` 当前仅视为辅助字段。

**Today v0.1 不得以 recommended_action=IGNORE 作为唯一过滤条件。**

---

# 3. Today v0.1 最小规则

使用代码中的确定性规则，不调用 LLM。

建议常量：

```text
MUST_READ_PRIORITY = 70
RELEVANT_PRIORITY = 40
RELEVANT_DREAMSTREAM = 50
```

规则：

```text
Must Read:
priority >= 70

Relevant:
非 Must Read 且
(priority >= 40 OR dreamstream_relevance >= 50)

Other:
其余已分析 Intelligence
```

注意：
- 规则必须集中在一个小模块 / 函数中。
- 不建立规则引擎。
- 不引入 YAML DSL。
- 不引入动态配置 UI。

---

# 4. 排序

每个区内：

```text
priority DESC
dreamstream_relevance DESC
analyzed_at DESC
```

NULL 时间必须安全处理。

---

# 5. Today 数据范围

Today 只显示：

```text
存在 analysis 的 item
```

Raw Item 没有 Analysis：

```text
不进入 Intelligence Card
```

不要给 Raw Item 生成假 Summary / 假 Priority。

---

# 6. Stats

Today API 至少返回：

```json
{
  "stats": {
    "raw_items": 81,
    "analyzed": 4,
    "relevant": 3,
    "must_read": 1
  }
}
```

数值必须来自数据库实时查询，不写死。

字段命名可按现有 API 兼容性做最小调整，但含义必须清晰。

---

# 7. Sections

建议 API 返回：

```json
{
  "sections": {
    "must_read": [],
    "relevant": [],
    "other": []
  }
}
```

如果当前前端结构更适合扁平数组，也可以：

```json
{
  "items": [
    {
      "...": "...",
      "today_bucket": "MUST_READ"
    }
  ]
}
```

选择改动最小的一种。

不要同时维护两套重复结构。

---

# 8. Channel

现有 category 继续使用：

```text
AI
AI_VIDEO
GITHUB
CHINA_TRENDS
MARKET
OTHER
```

Today 至少能按 category 显示标签 / 分组信息。

本工单不要求实现左侧完整频道页面。

不新增：
- AI 页面
- AI Video 页面
- GitHub 页面
- Market 页面

只做 Today。

---

# 9. Frontend

Today 页面保持轻量。

最低展示：

```text
TODAY

Raw
Analyzed
Relevant
Must Read

🔥 Must Read
[Cards]

Worth Watching
[Cards]
```

Other 可以：
- 折叠
- 或低视觉权重显示
- 或暂不在主视觉展开

但数据不能丢失。

不要做复杂动画、图表、Dashboard 大改版。

---

# 10. Card

沿用现有 Intelligence Card。

允许增加：

```text
Must Read / Relevant 小标签
```

除此之外不要重做 Card。

继续显示：

```text
title
category
summary
why_it_matters
priority
dreamstream_relevance
source
published_at（若有）
tags
```

---

# 11. Mock Data

现有 Mock Analysis 可以继续保留用于开发测试。

但 UI / API 不得特殊判断：

```text
if source == "Mock Source"
```

Mock 与真实 Analysis 走同一套 Today Rules。

---

# 12. recommended_action 的处理

当前 R3 中，高相关和中相关 synthetic fixture 均出现 `IGNORE`，主要因为模型明确识别了 synthetic / 无来源信息。

因此 v0.1：

```text
recommended_action
```

只作为卡片元数据。

**不得用于 Today 主排序和硬过滤。**

以后有真实来源的正样本后再单独校准。

---

# 13. 测试

至少新增：

```text
Must Read threshold test
Relevant by priority test
Relevant by Dream Stream relevance test
Other bucket test
Ordering test
NULL published_at safety
Raw item without analysis excluded
Stats derived from DB
```

现有全部测试必须继续通过。

---

# 14. 正式数据库验收

当前正式数据库基线：

```text
sources = 4
items = 81
analysis = 4
```

本工单不修改这些行数。

不得调用 DeepSeek。

验收：

```text
GET /api/v1/today
→ 200
```

并确认：

```text
4 张已有 Intelligence
按照新规则进入正确 bucket
```

---

# 15. 禁止事项

禁止：

```text
重新调用 LLM
修改 Analyzer
调整 Priority
修改 NewsNow

RSS
GitHub Connector
Market Watch

Feedback
Watchlist

Scheduler
Feishu
MCP

Full-text enrichment
Jina Reader
Browser Scout

复杂去重
Embedding
RAG
Agent
```

---

# 16. Stop Rule

满足：

```text
Today Rules 完成
+
API 正确分桶/排序
+
Stats 来自 DB
+
React 正确展示
+
全部测试通过
```

立即停止。

---

# 17. 验收报告

保存：

```text
docs/DSIH-005-report.md
```

结构：

## A. Rules
```text
Must Read:
Relevant:
Other:
Ordering:
```

## B. API
```text
Status:
Stats:
Bucket counts:
```

## C. Current DB Result
列出现有 4 条 Intelligence：

```text
item_id:
title:
priority:
dreamstream_relevance:
bucket:
```

## D. Frontend
```text
Today loads:
Must Read visible:
Relevant visible:
Other behavior:
```

## E. Database
```text
sources before/after:
items before/after:
analysis before/after:
```

必须不变。

## F. Tests
```text
Backend:
TypeScript:
Frontend build:
```

## G. Scope Audit
```text
LLM called? NO
Analyzer modified? NO
Priority modified? NO
NewsNow modified? NO
New Connector added? NO
Scheduler added? NO
Feishu added? NO
MCP added? NO
```

## H. Deviations
没有则：

```text
None
```

## I. Final
只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 18. 核心原则

Today 的职责不是“展示所有新闻”。

它只负责回答：

> **今天已经被 DSIH 分析过的信息里，什么最值得先看？**

第一版只用简单、可解释、确定性的规则。

不要提前建设推荐系统。

# DSIH-007-R1｜官方 RSS Raw Item 真实 Intelligence 验证

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：DSIH-007 最小纵向闭环验证  
优先级：P0

当前正式基线：

```text
sources = 9
items = 92
analysis = 6
```

已完成：
- NewsNow Connector
- GitHub Connector
- RSSConnector
- Analyzer v0.1.1
- Today Intelligence v0.1
- 生产 Mock 已退场

DSIH-007 已从 3 个官方 Feed 各写入 3 条 Raw Item：

```text
OpenAI News
Google DeepMind Blog
Hugging Face Blog
```

本工单不开发新功能，只验证：

```text
Official RSS Raw Item
→ 现有 Analyzer v0.1.1
→ Analysis
→ Today
```

---

# 1. 本工单唯一目标

从现有正式数据库中：

```text
每个 RSS Source 只选择 1 条最新已保存 Raw Item
```

共 3 条：

```text
OpenAI 1
DeepMind 1
Hugging Face 1
```

使用现有 DeepSeek Analyzer 做真实 Analysis。

不重新抓 RSS。

---

# 2. 选样规则

必须从 DSIH-007 已写入数据库的真实 RSS Raw Item 中选择。

每个 Source：

```text
按 published_at DESC
若 published_at=NULL，则按 captured_at DESC
```

取最新 1 条。

报告中记录：

```text
item_id
source
title
url
published_at
```

不得人工挑“看起来更容易高分”的文章。

---

# 3. 使用现有冻结能力

必须原样使用：

```text
dsih-analyzer-v0.1.1
当前 Prompt
当前 Intelligence Profile
当前 Priority v0.1-no-hotness
当前 Today Rules
当前 DeepSeek Provider
```

禁止修改：

```text
Prompt
Profile
Priority
Today thresholds
Category
recommended_action enum
```

---

# 4. 云 API 调用边界

只允许：

```text
3 次正常分析
```

每条如发生 JSON / Schema 失败：

```text
允许现有机制最多 1 次 repair
```

不得 A/B 测试。

不得切换模型。

不得输出 API Key。

---

# 5. 每条必须记录

对 3 条结果分别记录：

```text
Source
Title
Category
Summary
Why it matters

Importance
Novelty
Credibility
Personal relevance
Dream Stream relevance
Actionability

Priority
Tags
Recommended action
Analyzer version
```

并验证：

```text
JSON valid?
Priority computed by code?
Raw item unchanged?
```

---

# 6. 质量审核重点

只记录事实，不现场调参。

检查：

### A. Summary
必须忠于 Feed 自带内容。

不得把 `why_it_matters` 的推断塞进 Summary。

### B. 官方来源可信度
OpenAI / DeepMind / Hugging Face 都是官方来源。

模型可以给较高 credibility，但不得仅因“官方”而虚构：

```text
效果已被第三方验证
行业已经采用
生产环境已经部署
```

### C. Dream Stream relevance
根据文章真实内容判断。

不要预设一定高分。

例如：
- 直接涉及生成式视频 / 图像 / Agent / Workflow / 开发工具 → 可能较高
- 基础研究 / 公司新闻 /政策类内容 → 可以中低
- 与 Dream Stream 无直接价值 → 允许低分

### D. Evidence boundary
不得把：

```text
可能相关
可作为参考
未来可集成
```

写成：

```text
已经接入
已在 Dream Stream 使用
是核心组件
已改变生产流程
```

---

# 7. Today 验证

3 条 Analysis 成功写入后：

```text
GET /api/v1/today
```

记录：

```text
HTTP
Must Read
Relevant
Other
```

并列出 3 条 RSS Intelligence 各自 bucket：

```text
MUST_READ
RELEVANT
OTHER
```

不得为结果好看而调整阈值。

---

# 8. 数据库预期

开始：

```text
sources = 9
items = 92
analysis = 6
```

若三条均成功：

```text
sources = 9
items = 92
analysis = 9
```

所有 Raw Item 必须不变。

已有 6 条 Analysis 不得覆盖。

---

# 9. Duplicate Guard

对这 3 个 item_id 再执行一次：

```text
全部 SKIP
LLM called again? NO
Duplicate analysis written? NO
```

---

# 10. DeepMind DSIH-007 警告处理

DSIH-007 中：

```text
DeepMind 第二轮 Feed 未解析出有效条目
```

本工单：

```text
不修 RSS Connector
不重新抓 Feed
不调查外部响应
```

只分析数据库里已成功保存的 DeepMind Raw Item。

该 Connector 警告保留到以后 Scheduler / 稳定性阶段再处理。

---

# 11. 回归

必须确认：

```text
Backend tests PASS
Today API 200
TypeScript PASS
Frontend build PASS
```

除非发现真实回归，否则不新增生产代码。

---

# 12. 明确禁止

禁止：

```text
修改 RSS Connector
重新抓 RSS
新增 Source

修改 Analyzer
修改 Prompt
修改 Profile
修改 Priority
修改 Today

全文网页抓取
Crawl4AI 抓正文
Browser Scout

Scheduler
Feishu
Watchlist
Feedback
Market Watch
MCP
RAG
Embedding
Agent
```

---

# 13. Stop Rule

满足：

```text
3 条官方 RSS Raw Item 已真实分析
+
analysis 6→9
+
第二轮全部 SKIP
+
Today 正常分桶
+
回归通过
```

立即停止。

如果任一条在现有一次 repair 后仍失败：

```text
BLOCKED
```

记录明确错误，不继续调用。

---

# 14. 验收报告

保存：

```text
docs/DSIH-007-R1-report.md
```

## A. Selected RSS Items

列出：

```text
item_id
source
title
url
published_at
```

## B. Real Analysis

3 条完整记录。

## C. Quality Audit

分别记录：

```text
Summary grounded? YES/NO
Why-it-matters evidence-bound? YES/NO
Unsupported factual claim? YES/NO
```

如 NO / YES，必须引用具体文本说明。

## D. Database

```text
sources before/after:
items before/after:
analysis before/after:
Raw item mutation:
Existing analysis mutation:
```

## E. Duplicate Guard

```text
Second run:
LLM called again? NO
Duplicate analysis written? NO
```

## F. Today

```text
HTTP:
Must Read:
Relevant:
Other:
RSS item buckets:
```

## G. Regression

```text
Backend:
Today:
TypeScript:
Frontend build:
```

## H. Scope Audit

```text
Production code modified? NO
RSS Connector modified? NO
Analyzer modified? NO
Prompt modified? NO
Priority modified? NO
Today rules modified? NO
New Source added? NO
```

## I. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 15. 核心原则

本工单只回答：

> 官方 AI 信息进入 DSIH 后，现有 Analyzer 能不能把它转化成可信、可解释、可排序的 Intelligence？

不扩功能。

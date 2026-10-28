# DSIH-006-R1｜GitHub Raw Item 真实 Intelligence 验证

## 0. 工单定位

这是 DSIH-006 的最小闭环续单。

当前状态：
- GitHubConnector 已 PASS
- 3 个真实 GitHub Release 已进入 SQLite
- sources = 7
- items = 84
- analysis = 4
- Analyzer v0.1 已冻结
- Today v0.1 已完成

本工单不开发新功能，只验证：

```text
GitHub Raw Item
→ 现有 DeepSeek Analyzer
→ Analysis
→ Today
```

---

# 1. 本工单唯一目标

只对 DSIH-006 新增的 **3 条 GitHub Release Raw Item** 做真实 AI Analysis。

目标是验证：
1. GitHub 高相关信息能否被现有 Analyzer 正确识别；
2. 能否得到比普通社会热点更高的 Dream Stream relevance / Priority；
3. Today 是否能自然把这些真实 GitHub Intelligence 放入 Must Read / Relevant。

---

# 2. 必须使用现有能力

必须保持：
- `dsih-analyzer-v0.1`
- 当前 Prompt
- 当前 Intelligence Profile
- 当前 Priority v0.1-no-hotness
- 当前 OpenAI-compatible DeepSeek Client
- 当前 Today Rules

禁止修改以上任何一项。

---

# 3. 仅分析 3 条 GitHub Item

只选择 DSIH-006 本轮新增的 3 条：

```text
Comfy-Org/ComfyUI
browser-use/browser-use
unclecode/crawl4ai
```

必须按数据库中的真实 item_id 精确选择。

不要分析其它 NewsNow 未分析 Item。

如果现有 CLI 不支持指定 item_id：
- 优先使用已有 `Analyzer.analyze_one` 或等价生产接口做一次性运行；
- 可使用临时脚本/标准输入；
- 不得为本工单新增生产功能或重构 CLI。

---

# 4. 云 API

继续使用已配置的：

```text
DSIH_LLM_BASE_URL
DSIH_LLM_API_KEY
DSIH_LLM_MODEL
```

不得输出 API Key。

最多：
- 3 次正常分析调用
- 每条最多 1 次现有 JSON 修复重试

禁止 A/B Test、模型比较、Prompt 调参。

---

# 5. 必须记录每条结果

每条记录：

```text
Repository / Source
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
```

并检查：

```text
JSON valid?
Priority computed by code?
Raw item unchanged?
```

---

# 6. Today 验证

分析完成后调用：

```text
GET /api/v1/today
```

记录：

```text
HTTP status
Must Read count
Relevant count
Other count
```

并列出这 3 条 GitHub Intelligence 各自进入哪个 bucket。

不得为了让它进入某 bucket 调整阈值。

---

# 7. 数据库预期

本工单开始前：

```text
sources = 7
items = 84
analysis = 4
```

完成后预期：

```text
sources = 7
items = 84
analysis = 7
```

Raw Items 不得修改。

第二次对同样 3 条执行：

```text
全部 SKIP
LLM 不再次调用
analysis 不重复增加
```

---

# 8. 质量检查

只做事实性检查，不自行调参：

- ComfyUI Release 是否被识别为 AI / AI_VIDEO / GITHUB 中合理类别；
- browser-use 是否体现 Agent / Browser Automation 对 Dream Stream 的基础设施价值；
- Crawl4AI 是否体现网页获取 / Agent / Intelligence 基础设施价值；
- 是否虚构未出现在 Release 内容中的公司、版本、发布日期或具体能力；
- 是否明显出现“与 Dream Stream 高相关却极低分”的异常。

如果结果异常：
- 记录证据；
- 不修改 Prompt / Profile / Priority；
- 交由人工审核。

---

# 9. 回归

必须确认：

```text
Backend tests PASS
Today API 200
Frontend typecheck/build PASS
```

不需要新增测试，除非为了运行本工单发现真实回归。

---

# 10. 明确禁止

禁止：

```text
新增 Connector
RSS
Market Watch
Watchlist
Feedback
Scheduler
Feishu
MCP

修改 Analyzer
修改 Prompt
修改 Profile
修改 Priority
修改 Today Rules
修改 React UI
修改 NewsNow
修改 TrendRadar
```

---

# 11. Stop Rule

满足：

```text
3 条 GitHub Release 已真实分析
+
analysis 4→7
+
第二轮全部 SKIP
+
Today 正常分桶
+
回归通过
```

立即停止。

---

# 12. 验收报告

保存：

```text
docs/DSIH-006-R1-report.md
```

结构：

## A. Selected GitHub Items
列出 3 条 item_id / repo / title

## B. Real Analysis
按第 5 节列 3 条

## C. Database
```text
sources before/after:
items before/after:
analysis before/after:
Raw item mutation:
```

## D. Duplicate Guard
```text
Second run:
LLM called again? NO
Duplicate analysis written? NO
```

## E. Today
```text
HTTP:
Must Read:
Relevant:
Other:
GitHub item buckets:
```

## F. Regression
```text
Backend:
Today:
TypeScript:
Frontend build:
```

## G. Scope Audit
```text
Production code modified? NO
Prompt modified? NO
Profile modified? NO
Priority modified? NO
Today rules modified? NO
New Connector added? NO
```

## H. Final
只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 13. 核心原则

这张单不开发功能。

只回答：

> DSIH 已有的 GitHub Connector + Analyzer + Today，能不能形成第一条真正与 Dream Stream 高相关的真实 Intelligence？

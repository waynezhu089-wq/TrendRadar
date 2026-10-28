# DSIH-011-R1｜Watchlist → Analysis Candidate Boost v0.1

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Watchlist 与 Auto Analysis Queue 的最小联动  
优先级：P0

当前正式基线（DSIH-011 后）：

```text
sources   = 9
items     = 164
analysis  = 16
feedback  = 1
watchlist = 2
```

当前真实 Watchlist：

```text
project | ComfyUI
project | browser-use
```

已完成：
- 自动采集
- Auto Analysis Queue
- Scheduler 自动分析
- Feedback v0.1
- Watchlist v0.1

本工单只回答一个问题：

> **Watchlist 命中的 Raw Item，是否应该更优先获得一次 LLM Analysis 机会？**

---

# 1. 本工单唯一目标

在现有 Candidate Selector 中加入：

```text
watchlist_matches
```

并用于：

```text
候选资格 + 候选排序
```

但 **不修改**：

```text
Priority
Analyzer
Today Rules
Scheduler 周期
总分析上限
各 Source quota
7-day lookback
```

---

# 2. Watchlist 的作用边界

Watchlist 只影响：

```text
Raw Item → 是否优先进入 Analysis Candidate
```

它不影响：

```text
Analysis 分数
Priority
Recommended action
Today bucket
Today order
```

即：

```text
Watchlist = “先分析谁”
不是 “分析后一定高分”
```

---

# 3. 匹配字段

对每个未分析 Raw Item，构造轻量文本：

```text
source.name
title
content
url
```

做：

```text
trim
lowercase
collapse whitespace
```

然后对当前 Watchlist 的：

```text
normalized_value
```

做大小写不敏感的简单 substring 匹配。

例如：

```text
ComfyUI
→ "Comfy-Org/ComfyUI — v0.38.0"
→ MATCH

browser-use
→ "browser-use/browser-use — 0.13.11"
→ MATCH
```

不做：

```text
Embedding
LLM matching
中文分词
alias graph
fuzzy search
semantic search
```

---

# 4. Type 暂不做不同算法

v0.1 的：

```text
keyword
project
company
model
topic
```

全部使用同一个 substring matcher。

`type` 只保留语义，不改变匹配逻辑。

不要为不同 type 建规则树。

---

# 5. Watchlist 命中后的 NewsNow 资格

现有 NewsNow 规则：

```text
必须命中 ANALYSIS_GATE_TERMS
```

修改为：

```text
NewsNow eligible =
gate term match
OR
watchlist match
```

也就是说：

> 用户明确长期关注的对象，即使没有命中通用 AI Gate Term，也允许进入候选池。

但仍受：

```text
7-day lookback
NewsNow quota <= 2
MAX_TOTAL <= 6
```

约束。

---

# 6. 排序规则

在现有 Tier 规则前增加一个排序维度：

```text
1. watchlist_hit DESC
2. Tier：GitHub > RSS > NewsNow
3. 原有各 Tier 内排序
```

也就是：

```text
Watchlist 命中项
优先于
非 Watchlist 命中项
```

但 quota 仍然有效。

例如：

```text
NewsNow watchlist hit
```

不能突破：

```text
NewsNow max 2
```

---

# 7. 多个 Watchlist 命中

如果同一 Raw Item 命中多个 Watchlist：

记录：

```text
watchlist_matches = [...]
watchlist_match_count = N
```

v0.1 **不要因为命中 2 个就比命中 1 个获得额外跨层级加权**。

只需要：

```text
hit / no hit
```

用于第一排序维度。

`match_count` 仅用于解释与未来观察。

---

# 8. Candidate 输出

现有 selector 输出中新增：

```text
watchlist_matches
watchlist_hit
```

`selection_reason` 示例：

```text
WATCHLIST_MATCH: ComfyUI
WATCHLIST_MATCH: browser-use
NEWSNOW_GATE_MATCH: AI, Agent
RSS_RECENT
GITHUB_RECENT
```

如果同时命中 Watchlist + Gate Term：

```text
WATCHLIST_MATCH: MiniMax | NEWSNOW_GATE_MATCH: AI
```

保持可解释。

---

# 9. Dry Run

现有：

```bash
python -m app.commands.analyze_queue --dry-run
```

必须继续：

```text
0 LLM calls
0 DB writes
```

并展示：

```text
item_id
source
title
tier
watchlist_matches
gate_matches
selection_reason
```

---

# 10. Selector 无 Watchlist 时必须完全回退旧行为

若：

```text
watchlist = []
```

则 DSIH-009 的 Candidate Selector 行为必须保持一致。

这是关键兼容要求。

---

# 11. 不修改 Scheduler

DSIH-009-R1 Scheduler 已经调用现有 Candidate Selector。

本工单：

```text
Scheduler code modified? NO
```

Selector 更新后，Scheduler 下一轮自然使用新规则。

不新增 Job。

不改：

```text
Auto Analysis = 240 min
RSS offset = 12 min
```

---

# 12. 正式数据库验收

先对正式 DB 执行：

```text
--dry-run
```

记录当前：

```text
ComfyUI
browser-use
```

是否命中未分析 Raw Item。

允许：

```text
0 个真实 Watchlist hit
```

因为当前相关 GitHub Release 可能已经分析过。

**不得为了制造命中而新增假 Raw Item 到正式数据库。**

---

# 13. 必须使用隔离测试证明真实 Boost 语义

使用 temp/in-memory DB 建最小场景：

```text
Watchlist:
project | ComfyUI

Candidate A:
RSS
最新
非 Watchlist

Candidate B:
GitHub
标题含 ComfyUI

Candidate C:
NewsNow
标题含 ComfyUI
但不命中 ANALYSIS_GATE_TERMS
```

验证：

```text
B watchlist_hit = true
C watchlist_hit = true
C 因 Watchlist 获得 eligibility
Watchlist hit 优先于非命中项
NewsNow quota 仍有效
```

---

# 14. 真实 LLM 验收

本工单默认：

```text
不需要调用 LLM
```

如果正式 dry-run 恰好存在真实未分析 Watchlist hit：

只记录 selector 结果即可。

**不要为了验证 Boost 再调用 DeepSeek。**

本工单验证的是 Candidate Policy，不是 Analyzer。

---

# 15. 数据库边界

正式验收过程中：

```text
0 DB writes
```

不得修改：

```text
sources
items
analysis
feedback
watchlist
```

当前两条 Watchlist 保持：

```text
project | ComfyUI
project | browser-use
```

---

# 16. 自动测试

至少新增：

```text
watchlist match on source/title/content/url
case-insensitive matching
normalized whitespace matching
multiple watchlist matches reported
watchlist hit sorts before non-hit
newsnow watchlist hit bypasses generic gate
newsnow quota remains <= 2
total remains <= 6
7-day lookback still enforced
no watchlist => old selector behavior preserved
watchlist does not alter Priority
watchlist does not alter Today rules
dry-run => zero LLM calls / zero writes
```

使用 temp/in-memory DB。

---

# 17. 旧规则冻结检查

必须增加/保留断言，确认：

```text
LOOKBACK_DAYS = 7
MAX_TOTAL = 6
GITHUB_QUOTA = 3
RSS_QUOTA = 3
NEWSNOW_QUOTA = 2
```

以及现有：

```text
ANALYSIS_GATE_TERMS
```

内容未被本工单修改。

---

# 18. 前端

本工单：

```text
Frontend modified? NO
```

Watchlist 页面保持 DSIH-011 原样。

Today 页面保持原样。

不要加：

```text
“Watchlist Hit”徽章
过滤器
搜索
```

后续真实使用再决定。

---

# 19. 明确禁止

禁止：

```text
修改 Watchlist CRUD
Feedback 自动转 Watchlist

Watchlist → Priority
Watchlist → Analyzer Prompt
Watchlist → Today bucket
Watchlist → 通知
Watchlist → Feishu

修改 Scheduler
修改 Job 周期

Embedding
RAG
Agent
MCP
Semantic Search
Fuzzy Matching

新增 Source
Market Watch
```

---

# 20. Stop Rule

满足：

```text
Watchlist matcher 完成
+
Watchlist hit 可提高 Candidate 排序
+
NewsNow watchlist hit 可绕过 generic gate
+
所有 quota / lookback 保持
+
无 Watchlist 时旧行为一致
+
正式 dry-run 0 writes / 0 LLM
+
测试通过
```

立即停止。

---

# 21. 验收报告

保存：

```text
docs/DSIH-011-R1-report.md
```

## A. Policy

```text
match fields:
match method:
watchlist affects eligibility?:
watchlist affects ordering?:
watchlist affects Priority?: NO
```

## B. Frozen Rules

```text
lookback:
max total:
GitHub quota:
RSS quota:
NewsNow quota:
gate terms changed? NO
```

## C. Production Dry Run

```text
candidate count:
watchlist hit count:
LLM calls: 0
DB writes: 0
```

逐条列：

```text
item_id
source
title
watchlist_matches
gate_matches
selection_reason
```

## D. Isolated Boost Test

记录：
- GitHub Watchlist 命中
- NewsNow Watchlist 命中但无 Gate Term
- 排序结果
- quota 结果

## E. Database

```text
sources changed? NO
items changed? NO
analysis changed? NO
feedback changed? NO
watchlist changed? NO
```

## F. Tests

```text
Backend:
TypeScript:
Frontend build:
```

若前端无修改，仍跑现有 TypeScript / build 回归。

## G. Scope Audit

```text
Scheduler modified? NO
Analyzer modified? NO
Priority modified? NO
Today modified? NO
Watchlist CRUD modified? NO
New infrastructure added? NO
```

## H. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 22. 后续边界

本工单通过后，先不要继续扩大 Watchlist。

下一阶段应决定：

```text
A. 开始真实使用一段时间并积累 Feedback / Watchlist 信号
或
B. 进入 Market Watch v0.1
```

不要自动把 Watchlist 再扩展成通知系统。

---

# 23. 核心原则

Watchlist Boost 只负责：

> **“这是我长期关注的东西，所以先给它一次分析机会。”**

它不负责：

> **“因为我关注，所以它一定重要。”**

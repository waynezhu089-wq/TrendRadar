# DSIH-006-R3｜生产 Mock 退场与真实数据基线清理

## 0. 目的

DSIH 已经具备真实数据闭环：

```text
NewsNow → Raw → Analyzer → Today
GitHub  → Raw → Analyzer → Today
```

当前正式 Today 里仍保留最初骨架阶段的 Mock Intelligence。

本工单只做一件事：

> 让正式数据库和 Today 从此只展示真实采集数据；Mock 仅保留在测试环境。

---

## 1. 当前已知基线

```text
sources = 7
items = 84
analysis = 7
```

其中预计存在 1 组最初 Day 1 Mock：

```text
Mock Source
Mock Item
Mock Analysis
```

不要根据数量直接删除。

必须先通过真实字段确认其身份。

---

## 2. 先审计 Mock 身份

先只读查询并记录：

```text
source id / name / type
item id / title / external_id
analysis item_id / analyzer_version
```

确认它确实属于最初开发 Mock，而不是任何真实 NewsNow / GitHub 数据。

如果身份无法唯一确认：

```text
BLOCKED
```

禁止猜测删除。

---

## 3. 正式数据库清理

确认后，只删除该 Mock 链路：

```text
Mock Analysis
Mock Item
Mock Source
```

按外键安全顺序处理。

不得删除或修改：

```text
NewsNow
GitHub
任何真实 Raw Item
任何真实 Analysis
```

不得重建数据库。

---

## 4. 测试中的 Mock

允许测试继续使用：

```text
Fake / fixture / in-memory Mock
```

但正式数据库初始化 / seed 流程不得再自动插入生产 Mock Intelligence。

如果存在“应用启动时自动补 Mock”的逻辑：

只做最小修正，使其不再污染正式 DB。

不要设计环境管理框架。

---

## 5. Today 验证

清理后：

```text
GET /api/v1/today
```

必须：

```text
HTTP 200
```

Today 中不得再出现 Mock Source / Mock Item。

现有真实 Intelligence 必须保留。

预期当前真实分布大致包含：

```text
ComfyUI → Must Read
browser-use → Must Read
Crawl4AI → Relevant
NewsNow 已分析项 → Other
```

以实际数据库结果为准，不修改阈值。

---

## 6. 数据库预期

若确认确实只有 1 组 Mock：

```text
sources  7 → 6
items    84 → 83
analysis 7 → 6
```

但最终以“只删除已确认 Mock”作为验收标准，不以硬凑数量为目标。

---

## 7. 禁止事项

禁止：

```text
LLM 调用
重新分析
Priority 修改
Analyzer 修改
Today Rules 修改
Connector 修改

RSS
Scheduler
Feishu
Watchlist
Feedback
Market
MCP
```

---

## 8. 测试

至少确认：

```text
Backend tests PASS
Today API 200
TypeScript PASS
Frontend build PASS
```

增加一个最小回归测试，确保正式 seed / startup 不自动插入 Mock（如当前代码确实存在该风险）。

---

## 9. Stop Rule

满足：

```text
Mock 身份已明确
+
正式 DB 只删除 Mock
+
Today 不再显示 Mock
+
真实数据不变
+
回归通过
```

立即停止。

---

## 10. 报告

保存：

```text
docs/DSIH-006-R3-report.md
```

至少包含：

### A. Mock Audit
```text
source:
item:
analysis:
evidence:
```

### B. Database
```text
sources before/after:
items before/after:
analysis before/after:
real rows mutated? NO
```

### C. Today
```text
HTTP:
Must Read:
Relevant:
Other:
Mock present? NO
```

### D. Regression
```text
Backend:
TypeScript:
Frontend build:
```

### E. Scope Audit
```text
LLM called? NO
Analyzer modified? NO
Priority modified? NO
Today rules modified? NO
Connector modified? NO
```

### F. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

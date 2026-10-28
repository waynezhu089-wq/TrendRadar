# DSIH-011｜Watchlist v0.1 — 长期关注对象管理

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase D / Watchlist  
优先级：P0

前置已验收：
- DSIH-009-R1：自动采集 → 自动筛选 → 有界分析 → Today 已闭环
- DSIH-010：Feedback v0.1 已 PASS
- `feedback=watch` 已存在，但它只表示“这条 Intelligence 值得继续跟踪”

本工单新增的是另一件事：

> **用户长期想关注什么。**

---

# 1. 本工单唯一目标

实现最小 Watchlist：

```text
查看
新增
删除
```

支持类型：

```text
keyword
project
company
model
topic
```

本轮只记录用户关注对象。

**不让 Watchlist 影响 Selector、Priority、Analyzer、Today 排名或 Scheduler。**

---

# 2. Watchlist 与 Feedback Watch 严格分开

保持：

```text
feedback.watch
= 对某一条 Intelligence 的反馈
```

新增：

```text
watchlist
= 长期关注对象
```

例如：

```text
project | ComfyUI
project | browser-use
model   | Seedance
company | OpenAI
topic   | AI video
keyword | MiniMax
```

禁止本工单把 `feedback=watch` 自动转换成 Watchlist。

---

# 3. 先审计现有数据库

先确认正式数据库是否已有：

```text
watchlist
```

若已有：
- 复用现有表；
- 不重复建表；
- 仅做必要的最小兼容。

若不存在：
- 使用当前项目已有的 `initialize_database() / create_all` 机制新增最小表；
- 本工单不引入 migration framework。

---

# 4. 最小数据模型

建议：

```text
id
type
value
normalized_value
created_at
```

约束：

```text
type ∈ {keyword, project, company, model, topic}
value 非空
normalized_value 非空
UNIQUE(type, normalized_value)
```

`normalized_value` 只用于去重，例如：

```text
trim
lowercase
collapse whitespace
```

显示仍使用原始 `value`。

不要做：
- aliases
- tags
- notes
- priority
- notification settings
- source bindings
- complex JSON config

---

# 5. API

实现：

```http
GET /api/v1/watchlist
POST /api/v1/watchlist
DELETE /api/v1/watchlist/{id}
```

## POST

请求：

```json
{
  "type": "project",
  "value": "ComfyUI"
}
```

响应至少：

```json
{
  "id": 1,
  "type": "project",
  "value": "ComfyUI"
}
```

---

# 6. API 行为

### 新增重复项

例如：

```text
project | ComfyUI
project | comfyui
project | " ComfyUI "
```

应视为重复。

推荐：

```text
409 Conflict
```

不要静默新增第二行。

### 非法类型

```text
422 / 400
```

按现有 FastAPI 风格。

### 空 value

拒绝。

### 删除不存在 id

```text
404
```

---

# 7. 排序

GET 默认：

```text
type ASC
created_at ASC
```

或现有 UI 更自然的稳定顺序。

必须确定性。

不要做用户自定义拖拽排序。

---

# 8. Frontend

新增一个最小 Watchlist 页面 / 区域。

先审计当前前端导航与路由：

- 如果已有路由框架：新增 `/watchlist`
- 如果当前没有完整路由：采用最小现有结构，不为此重构导航系统

页面至少包含：

```text
Watchlist

[类型选择]
[输入框]
[添加]

已关注：
ComfyUI      project   删除
browser-use  project   删除
...
```

要求：
- 新增成功后立即显示
- 删除成功后立即移除
- 页面刷新后从 API 恢复
- API 失败时显示简短错误
- 不做复杂视觉设计

---

# 9. Today 的边界

本工单不要求 Today 展示 Watchlist 命中。

也不要求 Intelligence Card 上新增“加入 Watchlist”按钮。

原因：

先把长期关注对象本身建立起来。

后续再单独设计：

```text
Watchlist
→ Candidate Selector boost
```

---

# 10. 与自动分析完全解耦

禁止本工单修改：

```text
ANALYSIS_GATE_TERMS
Tier order
Quota
7-day lookback
Auto Analysis Queue
Scheduler
Priority
Analyzer Prompt/Profile
Today Rules
```

即使用户加入：

```text
ComfyUI
```

当前自动筛选结果也不得因此变化。

---

# 11. 正式验收数据

在正式数据库中创建 3 条真实 Watchlist：

```text
project | ComfyUI
project | browser-use
topic   | AI video
```

然后验证：

```text
GET → 3 条
刷新页面 → 仍存在
```

再删除：

```text
topic | AI video
```

最终正式数据库保留：

```text
project | ComfyUI
project | browser-use
```

这样既验证新增、持久化、删除，又留下两条真实有用关注对象。

---

# 12. 数据库边界

允许：

```text
新增 / 删除 watchlist 行
```

禁止修改：

```text
sources
items
analysis
feedback
```

验收前后对这四张现有表做内容一致性检查。

---

# 13. 测试

至少新增：

```text
create watchlist item
list watchlist
delete watchlist item
invalid type rejected
empty value rejected
duplicate normalized value rejected
same value with different type allowed
delete nonexistent id → 404
stable GET ordering
watchlist CRUD does not modify feedback
watchlist CRUD does not modify sources/items/analysis
frontend typecheck/build
```

使用 temp DB / fixture。

---

# 14. 不引入迁移框架

当前 DSIH 1.0 仍是单机 SQLite。

本工单继续沿用已有初始化建表方式即可。

不要新增：

```text
Alembic
Flyway
Liquibase
```

未来涉及真实字段升级 / 多版本演进时再统一处理。

---

# 15. 明确禁止

禁止：

```text
Watchlist → Selector
Watchlist → Priority
Watchlist → Analyzer
Watchlist → Notification
Watchlist → Feishu
Watchlist → Scheduler

Feedback watch 自动转 Watchlist
Card 一键加入 Watchlist
Watchlist 命中提醒

多用户
RBAC
历史版本
复杂搜索
Embedding
RAG
Agent
MCP
Market Watch
```

---

# 16. Stop Rule

满足：

```text
Watchlist 表可用
+
GET / POST / DELETE 可用
+
重复项可正确阻止
+
页面可新增 / 删除 / 刷新恢复
+
正式库最终保留 2 条真实 Watchlist
+
现有 sources/items/analysis/feedback 不变
+
全部测试通过
```

立即停止。

---

# 17. 验收报告

保存：

```text
docs/DSIH-011-report.md
```

## A. Schema

```text
watchlist existed before?:
table creation:
columns:
unique rule:
normalization:
```

## B. API

```text
POST:
GET:
DELETE:
duplicate:
invalid type:
empty value:
```

## C. Real Acceptance

```text
created:
- project | ComfyUI
- project | browser-use
- topic   | AI video

deleted:
- topic | AI video

final:
- project | ComfyUI
- project | browser-use
```

## D. Frontend

```text
page visible:
add works:
delete works:
refresh persistence:
failure behavior:
```

## E. Database

```text
sources changed? NO
items changed? NO
analysis changed? NO
feedback changed? NO
watchlist before/after:
```

## F. Tests

```text
Backend:
TypeScript:
Frontend build:
```

## G. Scope Audit

```text
Selector modified? NO
Analyzer modified? NO
Priority modified? NO
Today Rules modified? NO
Scheduler modified? NO
Notification added? NO
Feedback-watch auto-linked? NO
```

## H. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 18. 后续边界

本工单通过后，下一张才讨论：

```text
DSIH-011-R1｜Watchlist → Analysis Candidate Boost
```

届时只研究：

> Watchlist 命中是否应该提高某条 Raw Item 获得 LLM 分析机会的优先级？

不提前实现。

---

# 19. 核心原则

Watchlist v0.1 只回答：

> **“我长期想关注什么？”**

先把用户意图存下来。

暂时不要让系统因为这些意图自动改变其它行为。

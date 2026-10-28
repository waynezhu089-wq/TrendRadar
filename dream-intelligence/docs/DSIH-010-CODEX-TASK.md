# DSIH-010｜Feedback v0.1 — 真实使用信号采集

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase D / Feedback  
优先级：P0

当前正式状态（DSIH-009-R1 后）：

```text
sources = 9
items = 164
analysis = 16
```

自动闭环已验证：

```text
自动采集
→ 自动候选筛选
→ 有界 LLM Analysis
→ Priority
→ Today
```

本工单只增加：

> 用户对 Intelligence Card 的轻量反馈。

不让 Feedback 影响 Priority、Selector 或 Today 排名。

---

# 1. 目标

在 Today 的真实 Intelligence Card 上支持：

```text
👍 有价值      useful
👎 没价值      not_useful
⭐ 继续跟踪    watch
```

点击后保存到数据库，并在再次打开 Today 时显示当前选中状态。

---

# 2. 先审计现有 Schema

先确认正式数据库中是否已存在：

```text
feedback
```

若存在：
- 优先复用现有表；
- 不擅自重建。

若不存在：
- 新增最小表 / migration。

建议最小字段：

```text
id
item_id
feedback
created_at
updated_at
```

约束：

```text
UNIQUE(item_id)
feedback ∈ {useful, not_useful, watch}
FK item_id → items.id
```

1.0 单用户，因此一条 Item 只保留“当前反馈状态”。

不要做反馈历史表。

---

# 3. Upsert 语义

对同一 `item_id`：

第一次：

```text
useful
```

后续改成：

```text
not_useful
```

必须更新原记录，而不是新增第二行。

要求：

```text
1 item → max 1 current feedback
```

---

# 4. API

实现：

```http
POST /api/v1/feedback
```

请求：

```json
{
  "item_id": 123,
  "feedback": "useful"
}
```

响应至少：

```json
{
  "item_id": 123,
  "feedback": "useful"
}
```

错误：

```text
item 不存在 → 404
feedback 枚举非法 → 422 / 400（按现有 FastAPI 风格）
```

不要新增认证、多用户、权限系统。

---

# 5. Today 返回当前 Feedback

现有 Intelligence Card 响应新增可空字段：

```text
feedback: "useful" | "not_useful" | "watch" | null
```

未反馈：

```text
null
```

不得因为 Feedback 改变：

```text
bucket
priority
order
recommended_action
```

---

# 6. Frontend

沿用现有 Intelligence Card。

加入三个轻量按钮：

```text
👍 有价值
👎 没价值
⭐ 继续跟踪
```

要求：
- 点击调用 `/api/v1/feedback`
- 成功后本地立即更新选中态
- 同一时刻最多一个状态高亮
- 刷新页面后，从 Today API 恢复已保存状态
- 请求失败时不要假装成功

不要重做 Card UI。

不要加动画系统。

---

# 7. “watch” 的边界

本工单中的：

```text
watch
```

只表示：

> 用户认为这条 Intelligence 值得继续跟踪。

它**不是 Watchlist 实体**，也不会：
- 自动创建关键词；
- 自动监控项目；
- 自动发通知；
- 自动影响 Selector。

真正的 Watchlist 另开后续工单。

---

# 8. 不影响 AI / 排名

Feedback v0.1 只是收集真实使用信号。

禁止在本工单中：

```text
反馈 → Priority 调权
反馈 → Prompt 改写
反馈 → Selector Gate Term
反馈 → Must Read 阈值
反馈 → 自动训练
```

等积累真实反馈后再决定如何使用。

---

# 9. 数据安全

允许新增 / 更新：

```text
feedback
```

禁止修改：

```text
sources
items
analysis
```

验收前后必须比较：

```text
sources rows unchanged
items rows unchanged
analysis rows unchanged
```

---

# 10. 测试

至少新增：

```text
create feedback
update same item feedback
unique item feedback / no duplicate row
invalid feedback rejected
nonexistent item rejected
Today returns feedback=null when absent
Today returns persisted feedback when present
feedback does not change bucket/order/priority
frontend typecheck/build
```

测试使用 fixture / temp DB。

---

# 11. 真实验收

只对正式数据库中的 **1 张现有真实 Intelligence Card** 做真人可撤换状态验证。

推荐流程：

```text
1. 记录目标 item_id
2. POST useful
3. GET Today → useful
4. POST watch
5. GET Today → watch
6. 确认 feedback 表只有该 item 1 行
```

最终可以保留：

```text
watch
```

作为第一条真实用户反馈。

不要批量制造反馈。

---

# 12. 页面验收

启动现有前后端。

真人确认：
- 三个按钮可见；
- 点击后选中态正确；
- 刷新后状态仍保留；
- 切换反馈不会产生重复记录；
- Today 其它内容不受影响。

---

# 13. 明确禁止

禁止：

```text
Watchlist 系统
Feedback 历史
多用户
登录 / RBAC
通知
Feishu
Scheduler 改动

Analyzer 改动
Prompt / Profile 改动
Priority 改动
Selector 改动
Today Rules 改动

新 Connector / Source
Market Watch
MCP / RAG / Agent
```

---

# 14. Stop Rule

满足：

```text
Feedback 表/模型可用
+
POST /api/v1/feedback 可 upsert
+
Today 返回当前反馈
+
Card 可点击并恢复状态
+
不影响 Priority/Today 分桶
+
真实 1 条反馈验收通过
+
全部测试通过
```

立即停止。

---

# 15. 验收报告

保存：

```text
docs/DSIH-010-report.md
```

## A. Schema

```text
feedback table existed before?:
migration added?:
columns:
unique constraint:
```

## B. API

```text
POST useful:
POST watch:
invalid enum:
nonexistent item:
```

## C. Real Acceptance

```text
item_id:
title:
initial feedback:
first write:
second write:
rows for item:
final feedback:
```

## D. Today

```text
HTTP:
feedback returned:
bucket unchanged:
priority unchanged:
order unchanged:
```

## E. Frontend

```text
buttons visible:
selected state:
refresh persistence:
request failure behavior:
```

## F. Database

```text
sources changed? NO
items changed? NO
analysis changed? NO
feedback rows before/after:
```

## G. Tests

```text
Backend:
TypeScript:
Frontend build:
```

## H. Scope Audit

```text
Priority modified? NO
Selector modified? NO
Analyzer modified? NO
Today Rules modified? NO
Scheduler modified? NO
Watchlist implemented? NO
```

## I. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 16. 后续边界

本工单通过后，下一步再做：

```text
DSIH-011｜Watchlist v0.1
```

届时把“我想长期关注什么”从单条 Feedback 中独立出来。

---

# 17. 核心原则

Feedback v0.1 不负责“自动变聪明”。

它只负责：

> **开始记录用户真实觉得什么有价值、什么没价值、什么值得继续跟踪。**

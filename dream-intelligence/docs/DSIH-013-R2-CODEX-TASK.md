# DSIH-013-R2｜Announcement Read State v0.1 — 新公告提醒与已读状态

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase E / Market Watch  
优先级：P0

前置已验收：
- DSIH-013：深交所官方公告元数据已入库
- DSIH-013-R1：最近 3 条公告可进行轻量正文读取
- 可读 PDF → `READABLE`
- 难处理 PDF → `SKIPPED_COMPLEX`
- 官方链接始终保留

本工单只解决用户体验问题：

> **哪些公告我还没看？提醒我自己点进去看。**

不做推送、不改 Scheduler、不调用 LLM。

---

# 1. 本工单唯一目标

在现有 Market 公告区域增加：

```text
未读 / 已读
未读数量
标记已读
```

形成：

```text
新公告
→ 页面明显提醒
→ 用户点击“读取正文”或“查看官方公告”
→ 用户自己决定
→ 显式“标记已读”
→ 刷新后保持已读状态
```

---

# 2. 数据模型

不要修改 `market_announcements` 原始公告元数据。

新增独立表：

```text
market_announcement_reads
```

最小字段：

```text
id
announcement_id
read_at
```

约束：

```text
UNIQUE(announcement_id)
FK announcement_id → market_announcements.id
```

语义：

```text
不存在 read 行 = 未读
存在 read 行   = 已读
```

这样不需要为全部历史公告写初始化行。

---

# 3. 现有 10 条公告的初始状态

当前正式库已有 10 条可立克公告。

在本功能上线时：

```text
默认全部视为未读
```

原因：
- 它们是系统已经发现但用户尚未明确确认看过的公告；
- 不批量制造 read 记录。

不要自动把历史公告标记为已读。

---

# 4. API

新增：

```http
POST   /api/v1/market/announcements/{id}/read
DELETE /api/v1/market/announcements/{id}/read
```

## POST

作用：

```text
标记已读
```

要求幂等：

```text
重复 POST 不新增第二行
```

返回至少：

```json
{
  "announcement_id": 1,
  "is_read": true,
  "read_at": "..."
}
```

## DELETE

作用：

```text
恢复未读
```

返回：

```text
204
```

公告不存在：

```text
404
```

---

# 5. Market API

扩展现有：

```http
GET /api/v1/market
```

每条公告增加：

```text
is_read: true | false
```

每只股票增加：

```text
unread_announcement_count
```

例如：

```json
{
  "unread_announcement_count": 7,
  "announcements": [
    {
      "title": "...",
      "is_read": false
    }
  ]
}
```

只统计当前 API 返回范围还是全部公告？

第一版应统计：

```text
该股票数据库中全部未读公告
```

不要只统计最近 5 条，否则用户可能漏掉更早未读公告。

---

# 6. Frontend

现有 `/market` 公告区域增加：

```text
最新公告（未读 10）
```

未读公告显示轻量标识：

```text
● 新公告
```

每条公告保留：

```text
[读取正文]（若 READABLE）
[查看官方公告]
```

新增：

```text
[标记已读]
```

已读后显示：

```text
✓ 已读
[标记未读]
```

不要重做页面。

---

# 7. “点击链接”不要自动视为已读

为了避免：

```text
误点
页面打不开
PDF 打开后没看
```

本工单坚持：

```text
只有用户显式点击“标记已读”
才写 read 状态
```

“读取正文”和“查看官方公告”都不自动改状态。

---

# 8. 正文难读时的行为

如果：

```text
SKIPPED_COMPLEX
```

仍然显示：

```text
正文未自动读取
[查看官方公告]
[标记已读]
```

用户自己打开官方 PDF 后，再决定是否标记已读。

这正是本项目的轻量原则：

> 技术难度高的自动处理直接跳过，但不能让用户漏掉公告。

---

# 9. 正式验收

使用现有可立克真实公告。

开始：

```text
10 条均未读
```

验收流程：

```text
1. GET /api/v1/market → unread count = 10
2. 对公告 1 POST /read
3. GET → 公告 1 is_read=true，unread count=9
4. 刷新页面 → 已读状态保持
5. DELETE /read
6. GET → 公告 1 is_read=false，unread count=10
7. 再 POST /read
8. 最终保留公告 1 为已读
```

最终正式库：

```text
market_announcement_reads = 1
```

其它 9 条仍未读。

---

# 10. 数据库边界

允许新增 / 删除：

```text
market_announcement_reads
```

禁止修改：

```text
sources
items
analysis
feedback
intelligence watchlist
market_watchlist
market_snapshots
market_announcements
market_announcement_documents
```

---

# 11. 不调用 LLM

严格：

```text
LLM calls = 0
```

不得：
- 自动总结公告；
- 判断重要性；
- 判断利好/利空；
- 预测股价。

---

# 12. 不改 Scheduler

本工单：

```text
Scheduler modified? NO
```

公告自动采集调度留到下一工单。

---

# 13. 自动测试

至少新增：

```text
default announcement is unread
mark read creates one row
mark read is idempotent
mark unread deletes state
nonexistent announcement -> 404
market API returns is_read
market API returns total unread count
read state does not modify announcement metadata
read state does not modify document extraction status
frontend refresh restores state
```

使用 temp DB。

---

# 14. 明确禁止

禁止：

```text
Feishu
系统通知
浏览器通知
邮件通知

自动标记已读
点击链接自动已读

Scheduler 改动
公告采集改动
PDF 抽取改动

LLM
OCR
交易逻辑
```

---

# 15. Stop Rule

满足：

```text
未读数量可见
+
每条公告有未读/已读状态
+
标记已读/未读 API 可用
+
刷新持久化
+
难处理 PDF 仍保留官方链接
+
LLM 0 调用
+
Scheduler 不变
+
既有公告/正文数据不变
+
测试通过
```

立即停止。

---

# 16. 验收报告

保存：

```text
docs/DSIH-013-R2-report.md
```

## A. Schema

```text
market_announcement_reads:
unique:
default unread semantics:
```

## B. Real Acceptance

```text
initial unread:
mark read:
unread after read:
mark unread:
unread after reset:
final state:
```

## C. API

```text
POST read:
DELETE read:
GET market is_read:
unread count:
```

## D. Frontend

```text
unread badge:
mark read:
mark unread:
refresh persistence:
official link preserved:
```

## E. Database

```text
market_announcement_reads before/after:
existing tables changed? NO
```

## F. Tests

```text
Backend:
TypeScript:
Frontend build:
```

## G. Scope Audit

```text
LLM called? NO
Scheduler modified? NO
Announcement collector modified? NO
PDF extractor modified? NO
Trading logic added? NO
```

## H. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 17. 后续边界

本工单通过后，下一步才做：

```text
DSIH-013-R3｜Announcement Scheduler v0.1
```

让新公告自动进入系统。

届时新公告会自然变成：

```text
未读
→ Market 页面提醒
→ 易读则自动读取正文
→ 难读则只保留官方链接
```

---

# 18. 核心原则

这一步只负责：

> **“别让我漏掉公告；看没看过，由我自己确认。”**

# DSIH-010 验收报告

## A. Schema

```text
feedback table existed before?: NO
migration added?: NO；沿用现有 initialize_database() 的 create_all 建表机制
columns: id, item_id, feedback, created_at, updated_at
unique constraint: UNIQUE(item_id)
other constraints: feedback 仅允许 useful / not_useful / watch；item_id 外键指向 items.id
```

正式库建表前后的审计见[前快照](evidence/dsih-010-before.json)和[后快照](evidence/dsih-010-after.json)。没有重建原有表。

## B. API

```text
POST useful: 200，返回 item_id=82、feedback=useful
POST watch: 200，由页面按钮调用同一 API，最终返回并保存 watch
invalid enum: 422
nonexistent item: 404
```

同一 Item 的第二次写入更新原行。详见 [useful 验证](evidence/dsih-010-api-useful.json)和[最终 API 验证](evidence/dsih-010-api-final.json)。

## C. Real Acceptance

```text
item_id: 82
title: Comfy-Org/ComfyUI — v0.37.0
initial feedback: null
first write: useful（API）
second write: watch（现有 Card 的按钮）
rows for item: 1
final feedback: watch
```

只对这一张已有真实 Intelligence Card 写入反馈。页面按钮操作后刷新，watch 仍被选中；[页面截图](evidence/dsih-010-browser.png)记录了最终状态。

## D. Today

```text
HTTP: 200
feedback returned: item 82 = watch；未反馈 Card = null
bucket unchanged: YES，item 82 仍为 MUST_READ
priority unchanged: YES，仍为 85
order unchanged: YES
```

写入 useful 前后比较显示 Today 的全部卡片顺序和统计值均不变。最终统计仍为 Raw 164、Analyzed 16、Relevant 4、Must Read 2。反馈只作为可空字段返回，没有参与排序与分桶。

## E. Frontend

```text
buttons visible: YES，👍 有价值 / 👎 没价值 / ⭐ 继续跟踪
selected state: YES，同一时刻只有 watch 高亮
refresh persistence: YES，刷新后从 Today API 恢复 watch
request failure behavior: PASS，API 暂停时显示错误，原 watch 状态保持；随后已恢复服务
```

沿用原有 Card 布局，仅增加轻量按钮和失败提示。按钮请求成功后更新本地卡片状态，失败时不假装保存成功。

## F. Database

| Table | Before | After | 原有行内容变化 |
|---|---:|---:|---|
| sources | 9 | 9 | NO |
| items | 164 | 164 | NO |
| analysis | 16 | 16 | NO |
| feedback | 0 | 1 | 仅新增 item 82 的当前状态 |

前三张表按 `ORDER BY id` 对所有行做 SHA-256 摘要，前后完全一致。`feedback` 当前只有 `item_id=82, feedback=watch` 一行。

## G. Tests

```text
Backend: 68 tests PASS，0 failed
TypeScript: PASS（tsc --noEmit）
Frontend build: PASS（Vite）
```

新增临时 SQLite 测试覆盖创建、同一 Item 更新且不重复、非法值、无效 Item、Today 空/持久反馈、不改变顺序/分桶/优先级，以及浏览器 POST 预检。测试日志见 [dsih-010-tests.log](evidence/dsih-010-tests.log)。现有 Starlette/httpx 依赖弃用提示仍存在。

## H. Scope Audit

```text
Priority modified? NO
Selector modified? NO
Analyzer modified? NO
Today Rules modified? NO
Scheduler modified? NO
Watchlist implemented? NO
```

主要变更：`backend/app/db/models.py`、`backend/app/api/v1/feedback.py`、`backend/app/api/v1/today.py`、`backend/app/main.py`、`backend/app/schemas/feedback.py`、`backend/app/schemas/intelligence.py`、`frontend/src/api/intelligence.ts`、`frontend/src/components/IntelligenceCard.tsx`、`frontend/src/pages/Today.tsx`、`frontend/src/style.css`、`backend/tests/test_feedback.py`。

## I. Final

**PASS WITH WARNINGS**

Feedback 表、Upsert API、Today 可空反馈字段和三个卡片按钮均已验收。正式库只留下 1 条真实 watch 反馈；原有三张表逐行内容未变。唯一警告为既有测试依赖的弃用提示，与本次功能无关。

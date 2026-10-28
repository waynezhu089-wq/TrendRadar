# DSIH-011 验收报告

## A. Schema

```text
watchlist existed before?: NO
table creation: 沿用 initialize_database() / create_all；未引入迁移框架
columns: id, type, value, normalized_value, created_at
unique rule: UNIQUE(type, normalized_value)
normalization: 去首尾空白、合并内部空白、转小写；显示值仍保存原始 value
```

数据库还约束五种 type，以及 `value`、`normalized_value` 非空。建表前审计见[前快照](evidence/dsih-011-before.json)，最终结构与数据见[后快照](evidence/dsih-011-after.json)。

## B. API

```text
POST /api/v1/watchlist: 201，返回 id/type/value/created_at
GET /api/v1/watchlist: 200，按 type、created_at、id 稳定排序
DELETE /api/v1/watchlist/{id}: 204
duplicate normalized value: 409
invalid type: 422
empty/全空白 value: 422
delete nonexistent id: 404
```

临时库测试确认 `project | ComfyUI`、`project | comfyui`、`project | " ComfyUI "` 视为重复；相同值若类型不同可以共存。正式页面重复输入 `project | " comfyui "` 显示冲突提示，没有新增行。最终 API 验证见[记录](evidence/dsih-011-api-final.json)。

## C. Real Acceptance

正式库通过现有页面先创建并刷新确认 3 条：

```text
project | ComfyUI
project | browser-use
topic   | AI video
```

随后从页面删除 `topic | AI video`，刷新后最终只保留：

```text
project | ComfyUI
project | browser-use
```

最终两行的 ID 为 1、2；[页面截图](evidence/dsih-011-browser.png)显示刷新后的状态。

## D. Frontend

```text
page visible: YES，/watchlist；与 Today 之间有简单导航
add works: YES，成功后立即显示
delete works: YES，成功后立即移除
refresh persistence: YES，三条创建后和两条删除后均已刷新核对
failure behavior: YES，重复对象返回 409 时显示错误，原列表保持不变
```

项目原先没有路由框架，因此只按当前路径选择 Today 或 Watchlist 页面，没有引入新导航依赖。

## E. Database

| Table | Before | After | 原有内容变化 |
|---|---:|---:|---|
| sources | 9 | 9 | NO |
| items | 164 | 164 | NO |
| analysis | 16 | 16 | NO |
| feedback | 1 | 1 | NO |
| watchlist | 0 | 2 | 按工单新增三条、删除一条 |

前四张表按 `ORDER BY id` 对全部行做 SHA-256 摘要，前后一致。Today 仍返回 200，统计值保持 Raw 164、Analyzed 16、Relevant 4、Must Read 2；item 82 的 `feedback=watch` 保持不变。

## F. Tests

```text
Backend: 72 tests PASS，0 failed
TypeScript: PASS（tsc --noEmit）
Frontend build: PASS（Vite）
```

新增临时 SQLite 测试覆盖创建、列表、删除、去重、同值异类型、非法类型、空值、缺失 ID、稳定排序、旧表隔离及跨域预检。测试日志见 [dsih-011-tests.log](evidence/dsih-011-tests.log)。现有 Starlette/httpx 依赖弃用提示仍存在。

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

主要变更：`backend/app/db/models.py`、`backend/app/api/v1/watchlist.py`、`backend/app/schemas/watchlist.py`、`backend/app/main.py`、`backend/tests/test_watchlist.py`、`frontend/src/api/watchlist.ts`、`frontend/src/pages/Watchlist.tsx`、`frontend/src/App.tsx`、`frontend/src/style.css`，以及本报告与验收证据。

## H. Final

**PASS WITH WARNINGS**

Watchlist 表、GET/POST/DELETE、页面新增/删除/刷新恢复和重复阻止均通过。正式库最终保留两条指定的 project 关注对象，四张既有表逐行内容不变。唯一警告是既有测试依赖的弃用提示。

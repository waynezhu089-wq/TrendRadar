# DSIH-013-R2 验收报告

## A. Schema

- `market_announcement_reads`: `id`、`announcement_id`、`read_at`。
- `announcement_id` 有唯一约束，并通过外键关联 `market_announcements.id`。
- 默认未读语义：没有 read 行即未读；有 read 行即已读。上线时未批量写入历史公告的 read 行。

## B. Real Acceptance

使用正式库现有可立克（002782.SZ）10 条公告，依工单完成真实往返：

| 步骤 | 结果 |
|---|---|
| initial unread | **10**；最初无 read 行 |
| mark read | 公告 1 `POST /read` 成功，创建 1 行 |
| unread after read | **9**；公告 1 `is_read=true` |
| refresh | 页面仍显示“未读 9”和公告 1“✓ 已读” |
| mark unread | 页面按钮调用 `DELETE /read` 后恢复为未读 |
| unread after reset | **10**；read 行数回到 0 |
| text read without marking | 点击“读取正文”展开纯文本后仍显示“未读 10”；官方链接保留 |
| final state | 再次显式标记公告 1 已读；刷新后未读 **9**，`market_announcement_reads` 仅有公告 1 的 **1** 行，其余 9 条未读 |

## C. API

- `POST /api/v1/market/announcements/{id}/read`: 返回 `announcement_id`、`is_read=true`、`read_at`；重复 POST 幂等，不重复插入。
- `DELETE /api/v1/market/announcements/{id}/read`: **204**；重复 DELETE 仍为 204。
- 不存在的公告：POST、DELETE 均 **404**。
- `GET /api/v1/market`: 每条返回 `is_read`；每只股票返回全部已保存公告的 `unread_announcement_count`，不只统计页面显示的最近 5 条。

## D. Frontend

- 标题显示“最新公告（未读 9）”，每条显示“● 新公告”或“✓ 已读”。
- “标记已读”“标记未读”可操作，操作后数量和标识同步更新；刷新后状态由数据库恢复。
- “读取正文”和“查看官方公告”都不自动标记已读。
- `SKIPPED_COMPLEX` 仍显示“正文未自动读取”，并保留官方链接与显式标记按钮；本次真实三条正文均为 `READABLE`，该分支沿用 R1 实现。
- [最终页面截图](evidence/dsih-013-r2-market.png)。

## E. Database

- `market_announcement_reads`: **表不存在 / 0 行 → 1 行**，最终只对应公告 1。
- 既有九张表（含 `market_announcements`、`market_announcement_documents`）行数及全行 SHA-256 与变更前一致；原始公告元数据和已提取正文未修改。
- [变更前基线](evidence/dsih-013-r2-before.json) · [变更后核对](evidence/dsih-013-r2-db.json)。

## F. Tests

- Backend: `python -m unittest discover -s tests`，**102/102 PASS**。新增临时数据库测试覆盖默认未读、全部公告计数、幂等、已读/未读切换、404、公告元数据及提取结果不变。
- TypeScript: `tsc --noEmit` **PASS**。
- Frontend build: `vite build` **PASS**。
- [后端测试记录](evidence/dsih-013-r2-tests.txt) · [前端构建记录](evidence/dsih-013-r2-frontend-build.txt)。
- 唯一 warning：既有 Starlette `TestClient` 对 `httpx` 的弃用提示；测试仍全部通过。

## G. Scope Audit

- LLM called? **NO**
- Scheduler modified? **NO**
- Announcement collector modified? **NO**
- PDF extractor modified? **NO**
- Trading logic added? **NO**
- 通知/推送、自动已读均未添加。

## H. Final

**PASS WITH WARNINGS** — 未读数量、单条已读状态、显式切换与刷新持久化均通过真实库和页面验收；正式库最终仅公告 1 已读。唯一 warning 为既有测试依赖的弃用提示。

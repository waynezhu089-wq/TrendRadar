# DSIH-013-R3 验收报告

## A. Scheduler Registration

- Job count: **6**。
- Announcement job: `market_announcements` / `Market Announcements`。
- Cron: `mon-fri`, `hour="18,22"`, `minute=30`。
- Timezone: `Asia/Shanghai`；即工作日 **18:30、22:30**。
- `max_instances=1`；`coalesce=True`。
- Existing 5 jobs changed? **NO**。NewsNow 60 分钟、GitHub 120 分钟、RSS 240 分钟、Auto Analysis 240 分钟并晚于 RSS 12 分钟、Market Collector 工作日 16:10 的配置保持原样。
- [注册及下次触发时间核对](evidence/dsih-013-r3-scheduler.json)。本工单未等待真实 Cron 触发，只运行显式单次入口。

## B. Real Once

首次 `--once-announcements` 遇到深交所元数据请求临时失败，返回 `WARNING`，未写入数据；随后单独诊断同一官方接口可返回 10 条，重跑一次 Job 完成验收。最终成功一轮的结果：

| 字段 | 结果 |
|---|---:|
| watchlist_count | 1 |
| ann_received | 10 |
| ann_inserted | 0 |
| ann_skipped | 10 |
| ann_failed | 0 |
| docs_selected | 3 |
| docs_readable | 1 |
| docs_skipped_complex | 2 |
| docs_failed | 0 |
| status | OK |

本轮实际处理：

| ID | 公告 | 正文状态 | 字符数 | 原因 |
|---:|---|---|---:|---|
| 4 | 可立克：招商证券股份有限公司关于深圳可立克科技股份有限公司2026 年向特定对象发行A 股股票之发行保荐书 | READABLE | 26,297 | — |
| 5 | 可立克：深圳可立克科技股份有限公司2026 年向特定对象发行A 股股票募集说明书（申报稿） | SKIPPED_COMPLEX | 0 | TOO_MANY_PAGES |
| 6 | 可立克：公司最近一年的财务报告及其审计报告以及最近一期的财务报告 | SKIPPED_COMPLEX | 0 | TOO_MANY_PAGES |

原有公告 1–3 的终态正文没有重新处理。其余未处理公告留待以后每轮最多三条的边界自然处理，不在本工单继续跑。

## C. Read State

- Unread before: **9**。
- Unread after: **9**。
- Auto-marked read? **NO**。
- Existing read row changed? **NO**；正式库仍只有公告 1 的已读行，内容哈希一致。

## D. Database

- `market_announcements`: **10 → 10**，全行哈希一致；重复公告全部跳过。
- `market_announcement_documents`: **3 → 6**；原有公告 1–3 的正文行哈希一致，新加公告 4–6 的处理状态。
- `market_announcement_reads`: **1 → 1**，全行哈希一致。
- Existing business tables changed? **NO**；`sources`、`items`、`analysis`、`feedback`、`watchlist`、`market_watchlist`、`market_snapshots` 的行数与全行哈希一致。
- [运行前基线](evidence/dsih-013-r3-before.json) · [运行后数据库和接口核对](evidence/dsih-013-r3-db-api.json)。

## E. API

- `GET /api/v1/market`: **200**。
- `unread_announcement_count`: **9**。
- `is_read`: 公告 1 为 `true`，其余当前展示公告为 `false`。
- `read_status`: 当前展示的公告 1–4 为 `READABLE`，公告 5 为 `SKIPPED_COMPLEX`。
- 官方链接：当前展示公告均保留深交所官方 PDF URL。
- Market 行情与技术数据对应的 `market_snapshots` 表哈希未变；API 仍返回 30 个交易日的技术状态。

## F. Failure Isolation

- Single announcement failure: 临时源失败只返回该股票 `FAILED`/Job `WARNING`；测试用 SH 不支持和另一只 SZ 请求失败验证其它股票继续。
- Single PDF failure: 测试中一份 PDF 首轮 `FAILED` 后，后续 PDF 继续处理；下一轮该 `FAILED` 可重试，`READABLE`/`SKIPPED_COMPLEX` 不重读。
- Other scheduler jobs unaffected: 单次入口只调用公告 Job；测试中公告 Job 出现 warning 后，NewsNow Job 仍可独立返回 `OK`。
- 日志只记录计数、状态、公告 ID/标题，不打印 PDF 正文或异常响应体。

## G. LLM Audit

- LLM called? **NO**。
- Analyzer invoked? **NO**；隔离测试也断言 Analyzer 未调用。

## H. Tests

- Backend: `python -m unittest discover -s tests`，**104/104 PASS**。
- TypeScript: `tsc --noEmit` **PASS**。
- Frontend build: `vite build` **PASS**；本工单未改 UI。
- [后端测试记录](evidence/dsih-013-r3-tests.txt) · [前端构建记录](evidence/dsih-013-r3-frontend-build.txt) · [首次临时失败](evidence/dsih-013-r3-once.jsonl) · [成功实跑](evidence/dsih-013-r3-once-retry.jsonl)。
- 后端测试仍出现现有 Starlette `TestClient` 对 `httpx` 的弃用提示，不影响结果。

## I. Scope Audit

- Existing scheduler jobs modified? **NO**。
- Announcement collector logic duplicated? **NO**；Job 复用 `collect_announcements_once`。
- PDF extractor logic duplicated? **NO**；待处理选择复用 R1 的读取与持久化路径。
- OCR added? **NO**。
- Trading logic added? **NO**。
- 推送、LLM、交易日历及新 Market Provider 均未加入。

## J. Final

**PASS WITH WARNINGS** — 第六个 Job 已按工作日上海时间 18:30/22:30 注册；成功实跑完成公告去重和三份正文轻量处理，已读状态与原有业务数据保持不变。首次官方元数据请求临时失败，诊断后重跑成功；测试另有既存依赖弃用提示。

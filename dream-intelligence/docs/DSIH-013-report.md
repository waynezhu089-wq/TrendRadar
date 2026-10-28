# DSIH-013 验收报告

## A. Provider

- provider: `SZSEAnnouncementProvider`，仅支持 `market=SZ`；SH/BJ 明确返回 unsupported。
- official domain: 列表 `www.szse.cn`；原文 PDF `disc.static.szse.cn`。
- request type: 普通 HTTPS `POST`，交易所公开 JSON 接口 `/api/disc/announcement/annList`，按股票代码请求最多 10 条。
- token required?: **NO**
- real network result: **HTTP 200**；官方响应 `announceCount=1661`，本次列表返回 10 条。首条官方 PDF URL 的 **HEAD 200**，未下载 PDF。
- 写库前再次检查公告 URL 为 `https://szse.cn` 或其子域名；第三方 URL 会被拒绝。

## B. Real Collection

- symbol: `002782 | SZ | 可立克`
- received: **10**
- inserted: **10**
- skipped: **0**
- failed: **0**
- source: **SZSE**

前三条真实公告元数据：

| published_at | official title | external_id | official URL |
| --- | --- | --- | --- |
| 2026-09-28 | 可立克：关于2026年度向特定对象发行股票申请获得深圳证券交易所受理的公告 | 1225583788 | [官方 PDF](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-09-28/d764f0b0-daaf-4110-8125-2c027a7b764a.PDF) |
| 2026-09-28 | 可立克：北京市金杜律师事务所关于深圳可立克科技股份有限公司向特定对象发行股票之法律意见书 | 1225583793 | [官方 PDF](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-09-28/59dfcc79-b818-4aaa-8213-fb86e2848331.PDF) |
| 2026-09-28 | 可立克：招商证券股份有限公司关于深圳可立克科技股份有限公司2026 年向特定对象发行A 股股票之上市保荐书 | 1225583791 | [官方 PDF](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-09-28/982f88a5-afda-4cd3-af97-5eca788f1450.PDF) |

公告标题按官方返回原样保存；`external_id` 优先使用官方 `annId`。完整数据库核对结果见[证据文件](evidence/dsih-013-db.json)。

## C. Duplicate Guard

- second run: received **10**, inserted **0**, skipped **10**, failed **0**。
- duplicate rows? **NO**；`market_announcements` 保持 10 行、10 个不同 `external_id`。旧行未覆盖。

## D. API

- `GET /api/v1/market`: **HTTP 200**。
- announcement count: 每只股票最近 **5 条**。
- ordering: `published_at DESC`；同日按首次写入顺序稳定排列。
- official URLs only: **YES**，本次 5 条全部指向 `disc.static.szse.cn`。
- snapshot / technical: 原有 2026-09-28 快照与 30 日技术状态正常返回，内容未更改。

## E. Frontend

- latest announcements visible: **YES**，既有 `/market` 页面显示日期、官方标题和“查看原文”。见[完整页面截图](evidence/dsih-013-market.png)。
- official link works: **YES**；首条链接指向官方 PDF，HEAD 请求返回 200。页面未内嵌或下载 PDF。
- no fabricated summary: **YES**；仅展示官方公告元数据。

## F. Database

[采集前基线](evidence/dsih-013-before.json)记录了七张既有表的行数和全部有序行 SHA-256；两次真实采集后逐表复核：

| Table | Before | After | Content |
| --- | ---: | ---: | --- |
| sources | 9 | 9 | unchanged |
| items | 164 | 164 | unchanged |
| analysis | 16 | 16 | unchanged |
| feedback | 1 | 1 | unchanged |
| intelligence watchlist | 2 | 2 | unchanged |
| market_watchlist | 1 | 1 | unchanged |
| market_snapshots | 30 | 30 | unchanged |
| market_announcements | 0 | 10 | 仅新增可立克官方公告 |

## G. Tests

- Backend: **97 passed**；包括官方响应规范化、稳定 ID、官方域名约束、最多 10 条、日期/空日期、去重、故障隔离、SH/BJ unsupported、API 最近 5 条排序、空公告、既有数据边界。[测试输出](evidence/dsih-013-tests.txt)。
- TypeScript: **PASS**（`tsc --noEmit`）。
- Frontend build: **PASS**（`vite build`）。
- Warning: Starlette 测试客户端发出 `httpx` 弃用提示，不影响结果。

## H. Scope Audit

- LLM called? **NO**
- Scheduler modified? **NO**
- Technical indicators modified? **NO**
- Third-party finance source added? **NO**
- PDF/OCR added? **NO**
- Trading logic added? **NO**

## I. Final

**PASS WITH WARNINGS**

官方公告发现、元数据入库、同公告去重和 Market 展示均已验收。唯一警告是测试客户端依赖的弃用提示。

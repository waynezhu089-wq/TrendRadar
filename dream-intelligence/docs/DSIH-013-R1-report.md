# DSIH-013-R1 验收报告

## A. Extractor

- Library: `pypdf` 6.19.0；仅提取 PDF 现有文本层，正文以纯文本保存。
- OCR used? **NO**
- LLM used/called? **NO / 0**
- 仅允许深交所官方域名；非官方 URL 不下载。下载限制为单份 15 MB、20 秒超时；受保护、空白或明显不可读的 PDF 记为 `SKIPPED_COMPLEX`，网络或解析异常记为可重试的 `FAILED`。

## B. Real 3 Documents

按现有可立克（002782.SZ）公告发布时间选取最近三条，各只在首次运行下载、解析一次；第二次运行三条均 `skipped: true`。

| announcement_id | title | official_url | status | char_count | extractor | error_code |
|---:|---|---|---|---:|---|---|
| 1 | 可立克：关于2026年度向特定对象发行股票申请获得深圳证券交易所受理的公告 | [深交所 PDF](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-09-28/d764f0b0-daaf-4110-8125-2c027a7b764a.PDF) | READABLE | 498 | pypdf | null |
| 2 | 可立克：北京市金杜律师事务所关于深圳可立克科技股份有限公司向特定对象发行股票之法律意见书 | [深交所 PDF](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-09-28/59dfcc79-b818-4aaa-8213-fb86e2848331.PDF) | READABLE | 31,221 | pypdf | null |
| 3 | 可立克：招商证券股份有限公司关于深圳可立克科技股份有限公司2026 年向特定对象发行A 股股票之上市保荐书 | [深交所 PDF](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-09-28/982f88a5-afda-4cd3-af97-5eca788f1450.PDF) | READABLE | 32,669 | pypdf | null |

三条正文抽样开头均为可辨识的中文公告/文件标题。真实三条没有复杂 PDF；空白、加密 PDF 的安全跳过由本地 fixture 测试证明。

## C. API

- Market API: `GET /api/v1/market` **200**；最近五条公告的状态依次为 `READABLE × 3`、未处理 `null × 2`，且列表不含完整正文。
- Text endpoint: `GET /api/v1/market/announcements/1/text` **200**，返回 498 字正文。
- Unavailable behavior: 未处理的公告 4 返回 **409**，提示 `text unavailable; use official URL`；不存在的 ID 返回 **404**。
- Health API: **200**。

## D. Frontend

- READABLE action: `/market` 上点击“读取正文”后，首条公告成功展开中文纯文本，可再收起。
- SKIPPED action: 状态为 `SKIPPED_COMPLEX` 时显示“正文未自动读取”；本次三份真实公告均为 `READABLE`，此状态由代码和测试验证。
- Official link: 每条公告保留“查看官方公告”；未处理公告仍可跳转官方 PDF。
- 页面明确显示“新公告 · 当前未记录个人已读状态”；本次未新增用户已读数据模型。
- 页面验收截图：[dsih-013-r1-market.png](evidence/dsih-013-r1-market.png)。

## E. Database

- `market_announcement_documents`: **0 → 3** 行，分别关联公告 1、2、3，均为 `READABLE`；唯一约束为 `announcement_id`，不存 PDF 二进制。
- Existing tables changed? **NO**。`sources`、`items`、`analysis`、`feedback`、`watchlist`、`market_watchlist`、`market_snapshots`、`market_announcements` 的行数与全行 SHA-256 均与采集前一致。
- 核对记录：[before](evidence/dsih-013-r1-before.json)、[after](evidence/dsih-013-r1-db.json)、[API](evidence/dsih-013-r1-api.json)。

## F. Tests

- Backend: `python -m unittest discover -s tests`，**100/100 PASS**。包含官方域名允许、第三方拒绝、可读/空白/加密 PDF、网络失败、终态跳过与失败重试、正文接口、列表状态及旧表不变。
- TypeScript: `tsc --noEmit` **PASS**。
- Frontend build: `vite build` **PASS**。
- 唯一测试 warning：现有 `fastapi.testclient` 触发 Starlette 关于 `httpx` 的弃用提示，不影响测试结果。本工单未为消除该 warning 调整依赖或架构。
- 记录：[backend tests](evidence/dsih-013-r1-tests.txt)、[frontend build](evidence/dsih-013-r1-frontend-build.txt)。

## G. Scope Audit

- OCR added? **NO**
- LLM called? **NO**
- Scheduler modified? **NO**
- Announcement metadata modified? **NO**
- Trading logic added? **NO**
- 只读取三条真实公告，未扩展至其余七条。

## H. Final

**PASS WITH WARNINGS** — 最近三条官方公告均以普通文本层成功提取并入库；重复运行未重新下载，原有八张表保持不变，API、页面和测试通过。仅有既存测试依赖的弃用提示；复杂 PDF 的跳过行为本次由本地 fixture 验证。

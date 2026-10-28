# DSIH-005｜Today Intelligence v0.1

## A. Rules

- Must Read: priority >= 70。
- Relevant: 非 Must Read，且 priority >= 40 或 dreamstream_relevance >= 50。
- Other: 其余已分析条目。
- Ordering: priority DESC、dreamstream_relevance DESC、analyzed_at DESC NULLS LAST；完全相同时按 Item ID 确定顺序。
- 规则集中 backend/app/today_rules.py。recommended_action 不参与分桶、排序或过滤。Mock 和真实 Analysis 使用相同规则。
- API 沿用单一 items 数组，每张卡增加 today_bucket，不重复返回 sections。
- Relevant 统计为独占 Relevant 桶数量，不含 Must Read。raw_items 是全部 Raw 层 Item 数量（含已分析），analyzed 是有 Analysis 的条目数。
- 不新增日期过滤，沿用现有已分析数据范围。

## B. API

- Status: HTTP 200，实际本地 HTTP 请求。
- Stats: {"raw_items": 81, "analyzed": 4, "relevant": 0, "must_read": 1}。
- Bucket counts: MUST_READ=1、RELEVANT=0、OTHER=3。
- 没有 Analysis 的 77 条 Raw Item 未进入卡片。

## C. Current DB Result

- item_id=1；MiniMax releases new video capability；priority=91；dreamstream_relevance=96；bucket=MUST_READ
- item_id=42；我国南疆塔克拉玛干沙漠发现两处大型地下水水源，这意味着什么？将对当地生态和经济带来哪些影响？；priority=11；dreamstream_relevance=3；bucket=OTHER
- item_id=79；星铁真珠角色PV；priority=7；dreamstream_relevance=5；bucket=OTHER
- item_id=2；中国队亚运王者夺金；priority=4；dreamstream_relevance=0；bucket=OTHER

## D. Frontend

- Today loads: YES，浏览器实际验收 http://127.0.0.1:5173/。
- Must Read visible: YES，显示现有 Mock 卡片，其 MOCK DATA 标记保留。
- Relevant visible: YES，Worth Watching 标题及无相关情报空态；正式库当前没有 Relevant 卡片，未伪造数据。
- Other behavior: 原生 details，默认折叠；键盘 Enter 展开后实际确认 3 张卡，Priority 11、7、4，未丢失数据。
- 卡片保留 category、摘要、原因、分数、来源、tags；仅有 published_at 时显示该时间，NULL 时不显示，不引入替代时间。
- 原来的全站“所有数据均为 Mock”文案不再符合真实库，替换为中性说明。

## E. Database

- sources before/after: 4 / 4。
- items before/after: 81 / 81。
- analysis before/after: 4 / 4。
- 正式 DB 整文件 SHA256 一致。无采集、无模型请求、无迁移。

## F. Tests

- Backend: 27 passed / 0 failed。
- 覆盖 70/40/50 阈值、Other、三层排序、NULL published_at、无 Analysis 排除、实时 DB Stats、IGNORE 不过滤。
- 原有测试保持通过；旧 Stats 断言按本单的新明确字段语义更新。
- TypeScript: tsc --noEmit PASS。
- Frontend build: Vite build PASS。
- 既有 TestClient/httpx 弃用提示仍存在。

## G. Scope Audit

- LLM called? NO
- Analyzer modified? NO
- Priority modified? NO
- NewsNow modified? NO
- New Connector added? NO
- Scheduler added? NO
- Feishu added? NO
- MCP added? NO

冻结目录 intelligence、llm、connectors、config 的文件 SHA256 均未变。无新框架、无新页面、无 Git 提交或推送。

主要改动：today_rules.py、today.py、schemas/intelligence.py、前端 API 类型、Today.tsx、IntelligenceCard.tsx、少量 CSS、后端测试及本报告。

## H. Deviations

None。采用工单允许的扁平 items + today_bucket 结构，Other 默认折叠。

## I. Final

**PASS WITH WARNINGS**

Today API 正确分桶排序，Stats 来自数据库，React 已实际验证。
27 项测试、TypeScript 和构建通过，数据库与冻结模块未变。
唯一警告为已有测试依赖弃用提示。达到 Stop Rule，停止。

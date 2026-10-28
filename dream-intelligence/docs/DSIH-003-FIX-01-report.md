# DSIH-003-FIX-01 验收报告

执行日期：2026-09-28。项目：dream-intelligence。

## A. Request Comparison

- 两者均为 GET，默认端点 https://newsnow.busiyi.world/api/s，可配置。
- TrendRadar 使用 id + bare latest；DSIH 原来仅 id。已添加 bare latest，保留自定义 query，避免重复 id/latest。
- User-Agent：DSIH/0.1 改为普通 Chrome/Windows 风格。
- Accept：扩充为 application/json, text/plain, */*。
- 新增 Accept-Language: zh-CN,zh;q=0.9,en;q=0.8 和 Cache-Control: no-cache。
- timeout：20 秒改为 10 秒。
- redirects：两者默认跟随，未修改。
- proxy：TrendRadar 支持显式代理并沿用 requests 环境行为；DSIH 沿用 urllib 的环境/系统行为，未新增代理配置。
- Connection：参考为 keep-alive；DSIH 保留 urllib 管理的连接行为，未替换客户端。
- 修改前对比已记录：evidence/dsih-003-fix01-comparison.md。
- 仅对普通 HTTP 请求配置作最小调整，未复制 GPL Fetcher 或其它模块。
- 此组合调整后的请求已成功；未逐项消融，因此不声称某一个 header 是 403 的唯一原因。

本轮代码变更：backend/app/connectors/newsnow.py、backend/tests/test_newsnow.py；其它新增为本报告和证据。未新增依赖，无提交或推送。

## B. Single Platform

- Zhihu status: cache。
- HTTP: 200。
- Items: 20。
- 仅请求一次知乎验证；成功后才执行三源采集。
- 证据：evidence/dsih-003-fix01-zhihu.log。

## C. Real Crawl

| 平台 | 第一轮 Received / Inserted / Skipped | 第二轮 Received / Inserted / Skipped |
|---|---|---|
| Weibo | 30 / 30 / 0 | 30 / 0 / 30 |
| Zhihu | 20 / 20 / 0 | 20 / 0 / 20 |
| Bilibili | 30 / 30 / 0 | 30 / 0 / 30 |
| Total | 80 / 80 / 0 | 80 / 0 / 80 |

Failed: 两轮均 0。两次手动命令退出码均 0。
证据：evidence/dsih-003-fix01-run1.log、dsih-003-fix01-run2.log。

## D. Dedup

- Run 1：Inserted 80、Skipped 0；items 总数 81（含原 Mock）。
- Run 2：Inserted 0、Skipped 80；items 总数仍 81。
- Behavior: 相同热点未全量重复插入；external_id 重复数 0。
- 第一轮总数证据：evidence/dsih-003-fix01-count1.log。

## E. Database

- 数据库：C:\Users\zhuxu\Documents\ChatGPT\信息收集平台\dream-intelligence\data\dsih.db。
- sources: 4（原 Mock + 三个真实来源）。
- items: 81（原 Mock + 80 条真实热点）。
- analysis: 1（原 Mock Analysis）。
- 真实来源 items：Weibo 30、Zhihu 20、Bilibili Hot Search 30。
- 真实 items 对应 analysis 数量：0，符合 RAW / INTELLIGENCE 边界。
- 证据：evidence/dsih-003-fix01-database.json。

## F. Regression

- Tests: 原 9 项全部通过，新增请求契约测试 1 项；合计 10 passed / 0 failed。
- 新测试验证 GET、配置 URL/query、bare latest、请求头和 10 秒超时。
- Health: HTTP 200，status=ok。
- Today: HTTP 200，仍然只返回原 Mock 卡片。
- Frontend: npm run build 通过，包含 TypeScript tsc --noEmit 和 Vite build。
- today.py、Today.tsx、IntelligenceCard.tsx 与前次基线 SHA256 相同。
- 非阻塞警告：原有 Starlette TestClient 对 httpx 的弃用提示；无测试失败。
- 本工单未使用浏览器自动化；通过 API、SQL、单元测试和构建验收。

## G. Scope Audit

- Anti-bot framework added? NO
- Browser automation added? NO
- Proxy rotation added? NO
- Self-hosted NewsNow deployed? NO
- LLM added? NO
- RSS added? NO
- GitHub connector added? NO
- Scheduler added? NO
- Feishu added? NO
- MCP added? NO
- TrendRadar modified? NO

未引入 Cookie 获取、challenge solver、CAPTCHA、stealth 或重试循环。

## H. Final

**PASS WITH WARNINGS**

普通 HTTP 配置调整后，知乎单平台及三平台真实采集均成功。
80 条真实热点已进入 DSIH 自己的 SQLite。
第二轮跳过全部 80 条相同热点，items 总数保持 81。
Analysis 仍只有原 Mock；Today 和前端保持不变。
10 个测试及前端 TypeScript/构建通过，仅保留原有测试依赖弃用提示。
DSIH-003 剩余验收已完成，达到 Stop Rule，停止采集和扩展。

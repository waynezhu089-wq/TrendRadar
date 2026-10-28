# DSIH-013｜Market Announcements v0.1 — 官方公司公告采集

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase E / Market Watch  
优先级：P0

前置已验收：
- DSIH-012：A 股真实日线
- DSIH-012-R1：Technical State
- DSIH-012-R2：Market Scheduler
- 当前 Market Watchlist 仅有：
  `002782 | SZ | 可立克`

本工单只做：

> **Market Watchlist → 官方交易所公司公告 → SQLite → Market API / 页面**

不做新闻聚合、不调用 LLM、不解析公告全文。

---

# 1. 本工单唯一目标

为当前深圳证券交易所股票：

```text
002782 | SZ | 可立克
```

接入：

```text
深圳证券交易所官方公司公告
```

形成：

```text
Market Watchlist
→ SZSE Announcement Provider
→ market_announcements
→ /api/v1/market
→ /market
```

---

# 2. 数据源原则

第一版只允许：

```text
深圳证券交易所官方来源
szse.cn / disc.static.szse.cn
```

优先使用公开、结构化、稳定的交易所查询接口或公告列表请求。

如果列表页背后使用公开 JSON 接口：
- 可复用其正常请求契约；
- 只使用普通 HTTP；
- 保持 Provider 隔离。

禁止：

```text
东方财富
新浪财经
雪球
第三方镜像
Google/Bing 搜索结果作为正式数据源
Browser automation
Cloudflare 绕过
代理轮换
```

如果官方列表在当前环境无法通过普通请求稳定获取：

```text
BLOCKED
```

不要擅自换第三方源。

---

# 3. Provider

新增最小接口，例如：

```text
MarketAnnouncementProvider
  fetch_recent(symbol, market, limit=10)
```

第一版实现：

```text
SZSEAnnouncementProvider
```

仅支持：

```text
market = SZ
```

其它市场：

```text
SH / BJ
```

暂不实现，返回明确 unsupported，而不是假数据。

---

# 4. 首轮采集数量

对每只 enabled Market Watchlist 股票：

```text
最多取最近 10 条公告
```

本工单只有可立克，因此最多新增：

```text
10 条
```

不做全历史回填。

---

# 5. 新数据表

新增：

```text
market_announcements
```

最小字段：

```text
id
symbol
market
external_id
title
url
published_at
source
captured_at
raw_json
```

约束：

```text
UNIQUE(symbol, market, external_id)
```

如果官方没有明确公告 ID：

优先使用：

```text
公告 PDF / detail URL 中的稳定唯一标识
```

再不行才使用：

```text
normalized URL
```

不要用标题作为唯一 ID。

---

# 6. Normalize

每条公告至少保存：

```text
symbol
market
external_id
title
url
published_at
source = "SZSE"
captured_at
raw_json
```

要求：
- `title` 使用官方标题；
- `url` 指向官方详情或官方 PDF；
- `published_at` 使用官方披露日期；
- 无日期则 NULL，不用 captured_at 伪造；
- 不修改官方标题；
- 不生成 AI 摘要。

---

# 7. 暂不解析 PDF 正文

本工单明确不做：

```text
PDF 下载
PDF 文本抽取
OCR
公告正文摘要
风险点提取
财务数字结构化
```

只保存：

```text
公告元数据 + 官方链接
```

原因：

先证明“公告发现链路”稳定。

正文解析另开后续工单。

---

# 8. 采集命令

新增显式：

```bash
python -m app.commands.collect_market_announcements --once
```

输出至少：

```text
symbol
market
received
inserted
skipped
failed
source
```

不要注册进 Scheduler。

先手动验证。

---

# 9. 去重

第一次：

```text
最近最多 10 条
→ insert-if-new
```

第二次立即执行：

```text
相同公告全部 SKIP
```

若两次运行之间确实新增官方公告：

允许真实新增，但报告必须列明。

不要覆盖旧公告。

---

# 10. Market API

扩展现有：

```http
GET /api/v1/market
```

对每只股票增加：

```json
{
  "announcements": [
    {
      "title": "...",
      "url": "...",
      "published_at": "...",
      "source": "SZSE"
    }
  ]
}
```

第一版返回：

```text
最近最多 5 条
```

按：

```text
published_at DESC
```

无公告：

```text
[]
```

不要影响行情 snapshot / technical 对象。

---

# 11. Frontend

现有 `/market` 页面增加最小区域：

```text
最新公告
```

每条显示：

```text
日期
标题
查看原文
```

“查看原文”跳转官方 URL。

不要：
- 弹窗 PDF 阅读器
- 摘要
- AI 标签
- 重要性评分
- 红黄绿告警
- 图表

---

# 12. 正式验收

仅对：

```text
002782 | SZ | 可立克
```

真实运行：

```text
collect_market_announcements --once
```

要求至少验证：

```text
真实官方公告可获取
URL 属于 szse.cn / disc.static.szse.cn
```

如果官方当前最近 10 条中有数据：
- 写入真实 rows；
- 第二轮去重。

如果官方接口返回 0：
- 不制造数据；
- 需要区分“真实无公告”与“解析失败”。

---

# 13. 数据库边界

允许新增：

```text
market_announcements
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
```

---

# 14. 不调用 LLM

严格：

```text
LLM calls = 0
```

不得：
- 公告摘要；
- 利好/利空判断；
- 重要性评分；
- 股价影响预测；
- 买卖建议。

---

# 15. 不接 Scheduler

本工单：

```text
Scheduler modified? NO
```

Market Announcement Scheduler 放后续。

先验证官方源稳定。

---

# 16. 自动测试

至少新增：

```text
SZSE response normalize
stable external_id
official-domain URL enforcement
max 10 fetch limit
published_at parsing
missing date -> null
same announcement dedup
single-symbol failure isolation
unsupported SH/BJ explicit behavior
GET /api/v1/market includes latest announcements
announcement order DESC
no announcements -> []
existing market snapshot/technical unchanged
existing intelligence tables unchanged
```

自动测试使用 fixture / fake HTTP。

不得依赖实时网络。

---

# 17. 安全与来源校验

Provider 正式写库前，公告 URL 必须属于允许域：

```text
szse.cn
*.szse.cn
```

如果返回第三方 URL：

```text
拒绝写入
记录 warning/failure
```

不要跟随到非官方镜像。

---

# 18. 明确禁止

禁止：

```text
第三方财经新闻
通用新闻搜索

PDF 正文抓取
OCR
LLM 摘要
公告分类
利好利空
AI Daily Review

Market Scheduler 修改
技术指标修改
交易逻辑

SH/BJ 扩展
更多股票
```

---

# 19. Stop Rule

满足：

```text
SZSE Provider 可用
+
可立克最近官方公告进入 SQLite
+
第二轮去重
+
Market API 返回最近公告
+
Market 页面可打开官方原文
+
LLM 0 调用
+
Scheduler 不变
+
既有数据不变
+
测试通过
```

立即停止。

如普通 HTTP 无法稳定获取官方列表：

```text
BLOCKED
```

不要换第三方数据源。

---

# 20. 验收报告

保存：

```text
docs/DSIH-013-report.md
```

## A. Provider

```text
provider:
official domain:
request type:
token required?:
real network result:
```

## B. Real Collection

```text
symbol:
received:
inserted:
skipped:
failed:
```

至少列出 3 条（若实际有）：

```text
published_at
title
url
external_id
```

## C. Duplicate Guard

```text
second run:
duplicate rows? NO
```

## D. API

```text
GET /api/v1/market:
announcement count:
ordering:
official URLs only:
```

## E. Frontend

```text
latest announcements visible:
official link works:
no fabricated summary:
```

## F. Database

```text
sources changed? NO
items changed? NO
analysis changed? NO
feedback changed? NO
intelligence watchlist changed? NO
market_watchlist changed? NO
market_snapshots changed? NO
market_announcements before/after:
```

## G. Tests

```text
Backend:
TypeScript:
Frontend build:
```

## H. Scope Audit

```text
LLM called? NO
Scheduler modified? NO
Technical indicators modified? NO
Third-party finance source added? NO
PDF/OCR added? NO
Trading logic added? NO
```

## I. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 21. 后续边界

本工单通过后，下一步再决定：

```text
DSIH-013-R1｜Announcement Text Intake v0.1
```

只对“新公告”读取官方 PDF 文本，并做干净文本入库。

之后才考虑：

```text
Market AI Daily Review
```

---

# 22. 核心原则

Market Announcements v0.1 只回答：

> **“我关注的公司最近披露了什么官方公告？”**

不回答：

> **“这是利好还是利空？”**

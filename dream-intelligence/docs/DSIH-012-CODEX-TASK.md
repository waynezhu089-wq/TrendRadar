# DSIH-012｜Market Watch v0.1 — A股日线数据基础

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase E / Market Watch  
优先级：P0

前置已验收：
- DSIH-011-R1：Watchlist → Candidate Boost 已 PASS
- 自动采集 / 自动筛选 / 有界 LLM 分析 / Today 已闭环
- Feedback / Watchlist 已可真实使用

本工单开始进入 Market Watch，但只做：

> **自选股 + 真实日线快照 + 最小 Market 页面**

不做 AI 复盘，不做买卖建议，不做价格预测。

---

# 1. 本工单唯一目标

建立第一版：

```text
Market Watchlist
→ Market Provider
→ Daily Snapshot
→ SQLite
→ /api/v1/market
→ Market 页面
```

第一版只支持：

```text
中国 A 股
```

---

# 2. 数据模型

先审计现有数据库是否已有：

```text
market_snapshots
```

若已有，优先复用。

若没有，按当前 `initialize_database() / create_all` 机制新增。

## market_watchlist

最小字段：

```text
id
symbol
name
market
enabled
created_at
```

约束：

```text
UNIQUE(symbol, market)
enabled = boolean
```

## market_snapshots

最小字段：

```text
id
symbol
market
date
open
high
low
close
volume
amount
turnover
source
captured_at
```

约束：

```text
UNIQUE(symbol, market, date)
```

不得保存：

```text
AI recommendation
target price
buy/sell signal
position
cost basis
```

---

# 3. Symbol 规范

A 股内部统一：

```text
symbol = 6 位代码
market = SH | SZ | BJ
```

例如：

```text
002782 | SZ
600000 | SH
```

API 可以接受：

```text
002782
002782.SZ
```

但写库前统一规范化。

本工单不支持港股、美股、基金、期货、加密货币。

---

# 4. Market Provider

实现最小接口，例如：

```text
MarketProvider
  fetch_daily(symbol, market)
```

第一版只接一个真实、无需用户付费 Token 的 A 股公开数据 Provider。

优先选择：
- 当前 Python 环境中最轻量、可稳定返回 A 股日线数据的成熟方案；
- 若使用第三方库，保持 Provider 隔离，未来可替换。

禁止把外部 Provider 逻辑散落到 API / 页面。

如果真实 Provider 当前不可访问：

```text
BLOCKED
```

记录明确原因，不擅自改成假数据。

---

# 5. 首轮只拉“最近交易日”

本工单不做全历史回填。

对每只 enabled 股票：

```text
获取最近可用交易日的 1 条日线快照
```

写入：

```text
market_snapshots
```

第二次执行同一交易日：

```text
SKIP / UPSERT 同一唯一键
不得重复新增
```

优先采用：

```text
insert-if-new
```

不要覆盖已保存的历史日线，除非 Provider 明确返回同日修正且现有设计已有安全 upsert；1.0 默认不复杂化。

---

# 6. Market Watchlist API

实现最小：

```http
GET    /api/v1/market/watchlist
POST   /api/v1/market/watchlist
DELETE /api/v1/market/watchlist/{id}
```

POST 示例：

```json
{
  "symbol": "002782",
  "market": "SZ",
  "name": "可立克"
}
```

要求：

```text
重复 symbol+market → 409
非法代码 / market → 422
删除不存在 → 404
```

不要实现批量导入。

---

# 7. Snapshot 采集入口

提供显式命令：

```bash
python -m app.commands.collect_market --once
```

输出：

```text
symbol
market
date
inserted
skipped
failed
source
```

本工单不注册进 Scheduler。

先手动验收。

---

# 8. Market API

实现：

```http
GET /api/v1/market
```

最小返回：

```json
{
  "items": [
    {
      "symbol": "002782",
      "market": "SZ",
      "name": "可立克",
      "date": "YYYY-MM-DD",
      "open": 0,
      "high": 0,
      "low": 0,
      "close": 0,
      "volume": 0,
      "amount": 0,
      "turnover": 0
    }
  ]
}
```

没有快照的 Watchlist 项也应可返回：

```text
latest_snapshot = null
```

或等价结构。

不要因为没行情就删掉 Watchlist 项。

---

# 9. Frontend

新增最小：

```text
/market
```

如果当前 App 已有 Today / Watchlist 导航，就按现有轻量方式增加：

```text
Today | Watchlist | Market
```

页面至少显示：

```text
代码
名称
市场
最近交易日
收盘价
成交量
成交额
换手率
```

若某字段 Provider 不提供：

```text
显示 —
```

不得伪造 0。

---

# 10. 不做技术指标

本工单禁止：

```text
MA5/MA10/MA20
MACD
RSI
KDJ
支撑位
压力位
趋势评级
```

这些放到后续：

```text
DSIH-012-R1｜Market Technical State v0.1
```

---

# 11. 不调用 LLM

本工单：

```text
LLM calls = 0
```

不得：
- AI 解释涨跌；
- 新闻归因；
- 每日复盘；
- 推荐买卖。

---

# 12. 正式验收

只创建 1 个真实 A 股 Watchlist 项进行闭环验收：

```text
002782 | SZ | 可立克
```

验收：

```text
POST market watchlist
→ collect_market --once
→ market_snapshots 新增 1 条最近交易日
→ GET /api/v1/market
→ 页面可见
→ 第二次 collect_market --once 不重复新增
```

最终正式库保留这 1 条 Market Watchlist。

---

# 13. 数据库边界

允许新增：

```text
market_watchlist
market_snapshots
```

禁止修改：

```text
sources
items
analysis
feedback
watchlist
```

现有 Intelligence Watchlist 与 Market Watchlist 严格分开。

---

# 14. 测试

至少新增：

```text
symbol normalization
valid SH/SZ/BJ market
invalid symbol rejected
create/list/delete market watchlist
duplicate watchlist rejected
provider normalize test
latest daily snapshot persistence
same date dedup
provider failure isolation
GET /api/v1/market with snapshot
GET /api/v1/market without snapshot
existing intelligence tables unchanged
frontend typecheck/build
```

自动测试使用 Fake Provider / temp DB。

不依赖真实网络。

---

# 15. 明确禁止

禁止：

```text
AI stock analysis
买入/卖出建议
目标价
价格预测
自动交易

技术指标
新闻归因
公告抓取
Market Scheduler

修改 Intelligence Watchlist
修改 Candidate Selector
修改 Analyzer
修改 Priority
修改 Today Rules

多市场扩展
付费数据源
复杂缓存
```

---

# 16. Stop Rule

满足：

```text
Market Watchlist 可用
+
真实 A 股最近交易日快照写入 SQLite
+
第二轮同日不重复
+
Market API 200
+
Market 页面显示真实快照
+
LLM 0 调用
+
既有 Intelligence 数据不变
+
全部测试通过
```

立即停止。

---

# 17. 验收报告

保存：

```text
docs/DSIH-012-report.md
```

## A. Provider

```text
provider:
library/API:
token required?:
real network result:
```

## B. Schema

```text
market_watchlist:
market_snapshots:
unique constraints:
```

## C. Real Acceptance

```text
symbol:
market:
name:
date:
open:
high:
low:
close:
volume:
amount:
turnover:
source:
```

## D. Duplicate Guard

```text
second run:
duplicate row created? NO
```

## E. API

```text
watchlist POST:
watchlist GET:
market GET:
```

## F. Frontend

```text
page visible:
real snapshot visible:
missing value behavior:
```

## G. Database

```text
sources changed? NO
items changed? NO
analysis changed? NO
feedback changed? NO
intelligence watchlist changed? NO
market_watchlist before/after:
market_snapshots before/after:
```

## H. Tests

```text
Backend:
TypeScript:
Frontend build:
```

## I. Scope Audit

```text
LLM called? NO
Analyzer modified? NO
Priority modified? NO
Today modified? NO
Scheduler modified? NO
Technical indicators added? NO
Trading logic added? NO
```

## J. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 18. 后续边界

本工单通过后，下一张才考虑：

```text
DSIH-012-R1｜Market Technical State v0.1
```

只做简单、可解释的技术状态，不做预测。

---

# 19. 核心原则

Market Watch v0.1 只回答：

> **“我关注的股票，最近一个交易日发生了什么？”**

不回答：

> **“我该不该买？”**

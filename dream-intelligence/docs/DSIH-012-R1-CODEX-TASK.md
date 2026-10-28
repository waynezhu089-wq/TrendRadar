# DSIH-012-R1｜Market Technical State v0.1 — 可解释技术状态

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase E / Market Watch  
优先级：P0

前置已验收：
- DSIH-012：Market Watch v0.1 PASS
- 腾讯财经真实 A 股日线已接入
- `002782 | SZ | 可立克` 已完成真实最新交易日快照闭环
- 当前 `market_snapshots` 仅持久化最近 1 个交易日

本工单只做：

> **有限历史日线 + 简单、可解释、非预测性的技术状态。**

不做买卖建议，不做价格预测，不调用 LLM。

---

# 1. 本工单唯一目标

将当前 Market Watch 从：

```text
最近 1 个交易日
```

扩展为：

```text
最近最多 30 个交易日日线
        ↓
简单技术状态计算
        ↓
GET /api/v1/market
        ↓
Market 页面
```

第一版只服务现有：

```text
002782 | SZ | 可立克
```

---

# 2. 为什么先用 30 个交易日

DSIH-012 已确认 Tencent Provider 一次真实请求能返回约 30 条日线。

因此本轮优先复用现有 Provider 能力：

```text
不换数据源
不新增 Token
不引入第二 Provider
```

30 个交易日足够计算第一版：

```text
日涨跌幅
MA5
MA10
MA20
20 日最高 / 最低
20 日区间位置
5 日平均成交量
量比（当前成交量 / 前 5 日平均成交量）
```

不追求更长历史。

---

# 3. 历史数据写入

保留现有：

```text
market_snapshots
```

不新增历史表。

现有唯一键继续：

```text
UNIQUE(symbol, market, date)
```

新增显式命令，例如：

```bash
python -m app.commands.collect_market --backfill 30
```

行为：

```text
对 enabled Market Watchlist
获取最近最多 30 个交易日
逐日 insert-if-new
已存在日期 → SKIP
```

---

# 4. 保持 --once 旧语义

现有：

```bash
python -m app.commands.collect_market --once
```

必须继续只处理：

```text
最近一个可用交易日
```

不得因为本工单偷偷变成 30 日回填。

也就是说：

```text
--once        = 日常增量
--backfill 30 = 显式历史初始化
```

---

# 5. Provider 边界

继续使用：

```text
TencentDailyProvider
```

若当前 provider 内部已经拿到多条日线：

优先把“返回多条历史”的能力从现有实现中最小抽取出来，例如：

```text
fetch_recent_daily(symbol, market, limit=30)
```

不要复制第二套 HTTP / normalize 代码。

禁止新增 AKShare 作为运行时 Provider。

AKShare 只能继续作为字段映射参考，不作为第二真实数据源。

---

# 6. 技术指标计算位置

新增轻量纯函数 / service，例如：

```text
compute_technical_state(snapshots)
```

直接从数据库已有 `market_snapshots` 计算。

第一版：

```text
不新增 technical_state 表
不持久化派生指标
```

原因：

```text
指标可以随最新 snapshot 即时重算
避免派生数据过期
```

---

# 7. 技术状态字段

仅计算以下字段。

## 7.1 Daily Change

需要至少 2 个交易日：

```text
change_pct =
(latest_close / previous_close - 1) * 100
```

若数据不足：

```text
null
```

---

## 7.2 Moving Average

```text
ma5
ma10
ma20
```

规则：

```text
有完整 N 个有效 close 才计算
否则 null
```

不要用不足 N 天的数据冒充 MA。

---

## 7.3 Price vs MA

返回描述性状态：

```text
close_vs_ma5_pct
close_vs_ma10_pct
close_vs_ma20_pct
```

公式：

```text
(close / maN - 1) * 100
```

没有对应 MA：

```text
null
```

---

## 7.4 20-Day Range

需要至少 20 个交易日：

```text
high_20d
low_20d
range_position_20d
```

其中：

```text
range_position_20d =
(close - low_20d) / (high_20d - low_20d) * 100
```

若：

```text
high_20d == low_20d
```

则：

```text
range_position_20d = null
```

---

## 7.5 Volume

计算：

```text
avg_volume_5d
volume_ratio_5d
```

为避免把当日同时放入基准：

```text
avg_volume_5d = 最新交易日前 5 个完整交易日的平均 volume
volume_ratio_5d = 当日 volume / avg_volume_5d
```

因此 volume ratio 至少需要：

```text
6 个交易日
```

否则 null。

---

# 8. 不生成“多空判断”

禁止生成：

```text
强势
弱势
看多
看空
突破
买点
卖点
建议持有
建议减仓
趋势评分
综合评分
```

Market Technical State 只陈述事实，例如：

```text
收盘价高于 MA20 2.4%
当前位于 20 日价格区间的 68%
当日成交量是前 5 日均量的 1.3 倍
```

---

# 9. API

扩展现有：

```http
GET /api/v1/market
```

每个 Market item 增加：

```json
{
  "technical": {
    "change_pct": 0.0,
    "ma5": 0.0,
    "ma10": 0.0,
    "ma20": 0.0,
    "close_vs_ma5_pct": 0.0,
    "close_vs_ma10_pct": 0.0,
    "close_vs_ma20_pct": 0.0,
    "high_20d": 0.0,
    "low_20d": 0.0,
    "range_position_20d": 0.0,
    "avg_volume_5d": 0.0,
    "volume_ratio_5d": 0.0,
    "sample_days": 30
  }
}
```

字段不足时必须：

```text
null
```

不得用 0 代替缺失值。

---

# 10. Frontend

在现有 `/market` 页面增加一个轻量“技术状态”区域。

至少显示：

```text
当日涨跌
MA5
MA10
MA20
距 MA20
20 日最高
20 日最低
20 日区间位置
5 日均量
量比
```

缺失：

```text
—
```

不要新增图表。

不要新增 K 线。

不要重做 Market 页面。

---

# 11. 正式验收

对正式：

```text
002782 | SZ | 可立克
```

执行：

```bash
collect_market --backfill 30
```

要求：

```text
market_snapshots 从 1 条扩展到最近最多 30 个不同交易日
```

然后再次执行：

```bash
collect_market --backfill 30
```

必须：

```text
不产生同日期重复行
```

---

# 12. 数学验收

从正式数据库读取可立克日线。

Codex 必须用独立简单计算再次核对至少：

```text
change_pct
ma5
ma10
ma20
high_20d
low_20d
range_position_20d
avg_volume_5d
volume_ratio_5d
```

并确认与 API 返回一致。

不能只测试“字段存在”。

---

# 13. 数据精度

建议：

```text
价格 / MA：保留合理 decimal 精度
百分比：API 可保留 2~4 位小数
volume / amount：保持数值意义，不转成人类格式后再入库
```

数据库继续保存原始规范化数值。

显示层可以格式化。

---

# 14. 数据库边界

允许新增：

```text
market_snapshots 历史行
```

禁止修改：

```text
sources
items
analysis
feedback
intelligence watchlist
market_watchlist
```

现有最新交易日 snapshot 也不得被无理由改写。

---

# 15. 不接 Scheduler

本工单：

```text
Scheduler modified? NO
```

现有 Market 仍通过手动：

```text
collect_market --once
```

日常增量。

Market Scheduler 放后续单独决定。

---

# 16. 不调用 LLM

严格：

```text
LLM calls = 0
```

不得生成：

```text
AI 分析
涨跌原因
投资结论
买卖建议
```

---

# 17. 测试

至少新增：

```text
backfill inserts multiple trading days
second backfill deduplicates
--once still latest-only
snapshots sorted by date
change_pct exact calculation
ma5 / ma10 / ma20
insufficient MA returns null
20d high / low
20d range position
flat 20d range returns null position
5-day average volume excludes current day
volume ratio calculation
insufficient volume history returns null
market API technical state
missing values serialize as null
existing Intelligence tables unchanged
```

自动测试使用固定 fixture。

不得依赖实时网络。

---

# 18. 明确禁止

禁止：

```text
RSI
MACD
KDJ
BOLL
ATR

支撑位
压力位
突破检测

买卖信号
预测
目标价
仓位建议
自动交易

新闻 / 公告
LLM
Market Scheduler

新 Provider
更多股票
多市场
图表/K线
```

---

# 19. Stop Rule

满足：

```text
可立克最近最多 30 个交易日入库
+
二次 backfill 无重复
+
简单技术状态计算正确
+
Market API 200
+
Market 页面显示技术状态
+
LLM 0 调用
+
Scheduler 不变
+
既有 Intelligence 数据不变
+
全部测试通过
```

立即停止。

---

# 20. 验收报告

保存：

```text
docs/DSIH-012-R1-report.md
```

## A. History Backfill

```text
symbol:
requested:
provider rows:
inserted:
skipped:
failed:
date range:
final snapshot count:
```

## B. Duplicate Guard

```text
second backfill:
duplicate dates? NO
```

## C. Technical State

记录真实值：

```text
latest date:
close:
previous close:
change_pct:
ma5:
ma10:
ma20:
close_vs_ma5_pct:
close_vs_ma10_pct:
close_vs_ma20_pct:
high_20d:
low_20d:
range_position_20d:
avg_volume_5d:
volume_ratio_5d:
sample_days:
```

## D. Independent Math Check

```text
API vs independent calculation:
change_pct:
ma5:
ma10:
ma20:
range:
volume ratio:
```

全部标：

```text
MATCH / MISMATCH
```

## E. API

```text
GET /api/v1/market:
technical object:
null handling:
```

## F. Frontend

```text
technical section visible:
real values visible:
missing values:
```

## G. Database

```text
sources changed? NO
items changed? NO
analysis changed? NO
feedback changed? NO
intelligence watchlist changed? NO
market_watchlist changed? NO
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
Scheduler modified? NO
Provider changed? NO / minimal history method only
Priority modified? NO
Today modified? NO
Trading signal added? NO
Prediction added? NO
```

## J. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 21. 后续边界

本工单通过后，不要立刻堆更多指标。

下一步优先考虑：

```text
DSIH-012-R2｜Market Scheduler v0.1
```

让收盘后自动更新最新日线。

之后才讨论：

```text
公告 / 新闻
AI Daily Review
```

---

# 22. 核心原则

Market Technical State v0.1 只回答：

> **“价格现在处于什么可测量的位置？”**

不回答：

> **“接下来会涨还是会跌？”**

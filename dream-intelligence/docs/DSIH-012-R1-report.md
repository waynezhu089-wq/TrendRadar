# DSIH-012-R1 验收报告

## A. History Backfill

| Field | Actual result |
| --- | --- |
| symbol | 002782 / SZ / 可立克 |
| requested | 最近最多 30 个交易日 |
| provider rows | 30 |
| first run inserted | 29 |
| first run skipped | 1（原有 2026-09-28 快照） |
| first run failed | 0 |
| date range | 2026-08-17 ～ 2026-09-28 |
| final snapshot count | 30 个不同交易日 |

同一个 Tencent Finance Provider 新增 `fetch_recent_daily(..., limit=30)`，`fetch_daily()` 继续只取其中最新一天。`--once` 与 `--backfill 30` 分别调用这两个入口；没有增加数据源或定时任务。

## B. Duplicate Guard

- second backfill: inserted **0**, skipped **30**, failed **0**
- duplicate dates? **NO**；30 行对应 30 个不同日期。
- 原有 2026-09-28 快照逐列内容哈希与回填前一致。

## C. Technical State

指标从 SQLite 中最新 30 日快照即时计算，不另存表。价格、均价、百分比及量比在 API 中最多保留 4 位小数；缺少完整样本或分母为零时返回 `null`。

| Field | Real value |
| --- | ---: |
| latest date | 2026-09-28 |
| close | 14.14 |
| previous close | 14.96 |
| change_pct | -5.4813% |
| ma5 | 15.0900 |
| ma10 | 15.0360 |
| ma20 | 15.2135 |
| close_vs_ma5_pct | -6.2956% |
| close_vs_ma10_pct | -5.9590% |
| close_vs_ma20_pct | -7.0562% |
| high_20d | 16.09 |
| low_20d | 13.95 |
| range_position_20d | 8.8785% |
| avg_volume_5d | 7,640,320 股（前 5 日，不含当日） |
| volume_ratio_5d | 1.2587 倍 |
| sample_days | 30 |

这些值仅描述已发生的日线数据，不构成预测或交易信号。

## D. Independent Math Check

从正式 SQLite 直接读取日线，使用独立脚本按工单公式重算，没有调用生产技术状态函数。和 `GET /api/v1/market` 的结果逐项比较：

| Check | Result |
| --- | --- |
| change_pct | MATCH |
| ma5 / ma10 / ma20 | MATCH / MATCH / MATCH |
| close vs MA5 / MA10 / MA20 | MATCH / MATCH / MATCH |
| high_20d / low_20d / range_position_20d | MATCH / MATCH / MATCH |
| avg_volume_5d / volume_ratio_5d | MATCH / MATCH |
| sample_days | MATCH |

完整数值与边界核验见 [独立计算证据](evidence/dsih-012-r1-math.json)。

## E. API

- `GET /api/v1/market`: **200**，返回可立克最新快照及 `technical` 对象。
- `technical` 含工单指定的 12 个计算字段和 `sample_days`。
- 无快照、样本不足、缺失数值及分母为零的情况按字段返回 JSON `null`；固定样本测试已验证。

## F. Frontend

- technical section visible: **YES**，仍在既有 `/market` 页面。
- real values visible: **YES**，包括 MA5/10/20、20 日区间、前 5 日均量及量比。见[完整页面截图](evidence/dsih-012-r1-market.png)。
- missing values: 显示 `—`。
- 没有新增图表、K 线或页面。

## G. Database

[回填前基线](evidence/dsih-012-r1-before.json)保存了逐表行数和全部有序行的 SHA-256；回填后逐表复核：

| Table | Before | After | Content |
| --- | ---: | ---: | --- |
| sources | 9 | 9 | unchanged |
| items | 164 | 164 | unchanged |
| analysis | 16 | 16 | unchanged |
| feedback | 1 | 1 | unchanged |
| intelligence watchlist | 2 | 2 | unchanged |
| market_watchlist | 1 | 1 | unchanged |
| market_snapshots | 1 | 30 | 只增加 29 个历史交易日；原有最新快照 unchanged |

## H. Tests

- Backend: **88 passed**；覆盖历史回填、二次去重、`--once` 命令分流、Provider 日期排序、固定样本精确计算、样本不足及缺失值、API、原有情报表隔离。见[测试输出](evidence/dsih-012-r1-tests.txt)。
- TypeScript: **PASS**（`tsc --noEmit`）。
- Frontend build: **PASS**（`vite build`）。
- Warning: Starlette 测试客户端发出 `httpx` 弃用提示，不影响测试结果。

## I. Scope Audit

- LLM called? **NO**
- Scheduler modified? **NO**
- Provider changed? **仅新增最小历史方法，仍为 Tencent Finance**
- Priority modified? **NO**
- Today modified? **NO**
- Trading signal added? **NO**
- Prediction added? **NO**

## J. Final

**PASS WITH WARNINGS**

验收条件已满足；唯一警告来自测试客户端依赖的弃用提示。

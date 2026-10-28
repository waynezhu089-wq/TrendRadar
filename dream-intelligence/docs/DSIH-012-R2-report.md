# DSIH-012-R2 验收报告

## A. Scheduler Registration

| Field | Result |
| --- | --- |
| job count | 5 |
| Market job | `market` / Market Collector |
| cron | Monday–Friday 16:10 |
| timezone | Asia/Shanghai（Cron trigger 显式指定） |
| max_instances | 1 |
| coalesce | true |
| existing jobs changed? | NO |

原有 NewsNow 60 分钟、GitHub 120 分钟、RSS 240 分钟、Auto Analysis 240 分钟及相对 RSS 的 12 分钟 offset 均保持原样。确定性时间测试中，2026-09-28 20:00 上海时间之后的下一次 Market 触发为 2026-09-29 16:10 上海时间。

## B. Real Once

通过 `python -m app.commands.run_scheduler --once-market` 显式执行真实 Market Job，无需等待收盘时刻。

| Field | Actual result |
| --- | --- |
| watchlist_count | 1 |
| received | 1 |
| inserted | 0 |
| skipped | 1 |
| failed | 0 |
| status | OK |
| symbol | 002782 / SZ |
| latest date | 2026-09-28 |

已保存的最新交易日与 Provider 返回日期相同，因此此次正常跳过，没有强行制造新行。

## C. Duplicate Guard

- same-date duplicate row? **NO**
- `market_snapshots` 仍为 30 行、30 个不同交易日；已有快照内容哈希与执行前一致。

## D. Database

[运行前基线](evidence/dsih-012-r2-before.json)记录每张表的行数及全部有序行 SHA-256。真实 Job 执行后：

| Table | Before | After | Content |
| --- | ---: | ---: | --- |
| sources | 9 | 9 | unchanged |
| items | 164 | 164 | unchanged |
| analysis | 16 | 16 | unchanged |
| feedback | 1 | 1 | unchanged |
| intelligence watchlist | 2 | 2 | unchanged |
| market_watchlist | 1 | 1 | unchanged |
| market_snapshots | 30 | 30 | unchanged |

## E. Market API

- `GET /api/v1/market`: **HTTP 200**，返回一个可立克项目。
- latest snapshot: 2026-09-28，收盘价 14.14。
- technical object: 正常返回，`sample_days=30`，`ma20=15.2135`。
- 既有 `/market` 页面现场检查正常显示最新快照和技术状态；本工单没有修改 UI。

## F. Failure Isolation

- single symbol failure: Fake Provider 测试中一只股票失败，另一只仍插入成功；第二次同日运行转为 SKIP。
- other scheduler jobs unaffected: Market 部分失败及整体异常时，已有 Collector Job 均可独立执行。
- 日志只记录股票代码、市场、日期和结果，不输出异常正文或 Secret。

## G. LLM Audit

- LLM called? **NO**
- Analyzer invoked? **NO**
- `--once-market` 只执行 Market Job；自动测试断言分析路径未调用。

## H. Tests

- Backend: **92 passed**，包含第 5 个 Job 注册、上海时区 Cron、原有 4 个 Job 配置不变、Job 复用采集 service、同日去重、失败隔离、最新快照即时影响技术状态。
- TypeScript: **PASS**（`tsc --noEmit`）。
- Frontend build: **PASS**（`vite build`）。
- Warning: Starlette 测试客户端产生 `httpx` 弃用提示，不影响结果。

## I. Scope Audit

- existing scheduler jobs modified? **NO**
- Provider modified? **NO**
- Technical indicators modified? **NO**
- Today modified? **NO**
- Trading logic added? **NO**

## J. Final

**PASS WITH WARNINGS**

Market 第 5 个 Scheduler Job 已按指定市场时区注册，真实手动 Job 路径成功且同日去重。唯一警告是测试客户端依赖的弃用提示。

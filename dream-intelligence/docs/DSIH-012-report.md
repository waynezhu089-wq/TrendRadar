# DSIH-012 验收报告

## A. Provider

- provider: Tencent Finance daily K-line, isolated in `app.market.provider.TencentDailyProvider`
- library/API: `httpx` / `https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get`
- token required?: NO
- real network result: HTTP 200; `sz002782` returned 30 daily rows, latest date 2026-09-28. The provider stores only the latest available trading day. Field positions and units follow the [AKShare Tencent daily-line implementation](https://github.com/akfamily/akshare/blob/main/akshare/stock_feature/stock_hist_tx.py): volume converted from lots to shares and amount from 10,000 CNY to CNY. Turnover is stored as percentage points.

## B. Schema

- market_watchlist: `id, symbol, name, market, enabled, created_at`
- market_snapshots: `id, symbol, market, date, open, high, low, close, volume, amount, turnover, source, captured_at`
- unique constraints: `(symbol, market)` on market_watchlist; `(symbol, market, date)` on market_snapshots
- Both tables were created by the existing `initialize_database() / create_all` mechanism. The original Intelligence watchlist is separate.

## C. Real Acceptance

| Field | Actual value |
| --- | --- |
| symbol | 002782 |
| market | SZ |
| name | 可立克 |
| date | 2026-09-28 |
| open | 14.96 |
| high | 14.96 |
| low | 13.95 |
| close | 14.14 |
| volume | 9,616,700 shares |
| amount | 136,900,600 CNY |
| turnover | 1.96% |
| source | Tencent Finance |

First `python -m app.commands.collect_market --once`: inserted 1, skipped 0, failed 0.

## D. Duplicate Guard

- second run: inserted 0, skipped 1, failed 0
- duplicate row created? **NO**; `market_snapshots` remains at 1 row.

## E. API

- watchlist POST: **201** for `002782 | SZ | 可立克`
- watchlist GET: **200**, one normalized entry
- market GET: **200**, one item with the real 2026-09-28 snapshot
- health GET: **200**
- today GET: **200**

## F. Frontend

- page visible: **YES**, `/market`
- real snapshot visible: **YES**, [browser evidence](evidence/dsih-012-market.png)
- missing value behavior: a missing snapshot or field displays `—`; no fabricated zero.

## G. Database

The five existing tables were compared before and after by row count and SHA-256 over every ordered row. The baseline is [saved here](evidence/dsih-012-before.json).

| Table | Before | After | Content |
| --- | ---: | ---: | --- |
| sources | 9 | 9 | unchanged |
| items | 164 | 164 | unchanged |
| analysis | 16 | 16 | unchanged |
| feedback | 1 | 1 | unchanged |
| intelligence watchlist | 2 | 2 | unchanged |
| market_watchlist | 0 | 1 | 002782/SZ only |
| market_snapshots | 0 | 1 | 2026-09-28 only |

## H. Tests

- Backend: **82 passed**, including symbol normalization, SH/SZ/BJ validity, invalid codes, CRUD and duplicate rejection, provider normalization, latest snapshot persistence, same-day deduplication, provider failure isolation, Market API with and without snapshot, and original Intelligence table isolation. [Test output](evidence/dsih-012-tests.txt).
- TypeScript: **PASS** (`tsc --noEmit`).
- Frontend build: **PASS** (`vite build`).
- Warning: Starlette's test client emits an `httpx` deprecation warning; it does not affect the test result.

## I. Scope Audit

- LLM called? **NO**
- Analyzer modified? **NO**
- Priority modified? **NO**
- Today modified? **NO**
- Scheduler modified? **NO**
- Technical indicators added? **NO**
- Trading logic added? **NO**

## J. Final

**PASS WITH WARNINGS**

The required real-data loop is complete and the second run did not duplicate the daily snapshot. The only warning is the pre-existing test-client dependency deprecation notice.

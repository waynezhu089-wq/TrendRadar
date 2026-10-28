# DSIH-011-R1 验收报告

## A. Policy

```text
match fields: source.name、title、content、url
match method: 合并空白并转小写后，对 Watchlist normalized_value 做简单子串匹配
watchlist affects eligibility?: YES，NewsNow 命中 Gate Term 或 Watchlist 即可进入候选池
watchlist affects ordering?: YES，命中优先，再按原 Tier 和 Tier 内规则排序
watchlist affects Priority?: NO
```

候选报告新增 `watchlist_matches`、`watchlist_hit`、`watchlist_match_count`；命中数量只用于解释，不参与加权。若同时命中 Watchlist 和 NewsNow Gate，`selection_reason` 同时记录两种原因。

## B. Frozen Rules

```text
lookback: 7 天
max total: 6
GitHub quota: 3
RSS quota: 3
NewsNow quota: 2
gate terms changed? NO
```

既有 `ANALYSIS_GATE_TERMS` 内容及 Tier 内排序保持不变，冻结断言与无 Watchlist 兼容测试通过。

## C. Production Dry Run

```text
candidate count: 0
watchlist hit count: 0
LLM calls: 0
DB writes: 0
```

正式库目前的 `project | ComfyUI` 与 `project | browser-use` 没有命中尚未分析的 Raw Item；因此本次无候选逐条列示。`analyze_queue --dry-run` 的实际输出见[日志](evidence/dsih-011-r1-dry-run.log)。未调用 DeepSeek，也未制造正式 Raw Item。

## D. Isolated Boost Test

隔离内存库的 [Selector 输出](evidence/dsih-011-r1-isolated.json)：

| 顺序 | 类型 | 标题 | Watchlist 命中 | Gate 命中 |
|---:|---|---|---|---|
| 1 | GitHub | ComfyUI release | ComfyUI | — |
| 2 | NewsNow | Orion release | Orion | — |
| 3 | NewsNow | Orion update | Orion | — |
| 4 | RSS | Routine report | — | — |

GitHub Watchlist 命中成功；两个 NewsNow 的 Orion 命中在没有通用 Gate 命中的情况下获得资格，并排在更新的非命中 RSS 前。第三条 Orion NewsNow 被每轮最多 2 条的配额阻止。另有自动测试验证总数最多 6、7 天窗口、来源/标题/正文/URL 匹配、大小写和空白归一化、多重命中仅记录不加权、无 Watchlist 时旧选择结果及原因保持一致。

工单中“NewsNow 标题含 ComfyUI 但不命中 Gate”的示例与冻结规则冲突：`ComfyUI` 本身就在 Gate Terms 中，`browser-use` 也包含 Gate 词 `browser`。为验证真正的绕过路径，隔离测试使用仅存在于测试库的 `Orion`；未改变正式 Watchlist 或 Gate Terms。

## E. Database

| Table | Before | After | 内容变化 |
|---|---:|---:|---|
| sources | 9 | 9 | NO |
| items | 164 | 164 | NO |
| analysis | 16 | 16 | NO |
| feedback | 1 | 1 | NO |
| watchlist | 2 | 2 | NO |

五张表按 `ORDER BY id` 对全部行做 SHA-256 摘要，[运行前](evidence/dsih-011-r1-before.json)与[运行后](evidence/dsih-011-r1-after.json)完全一致。正式 Watchlist 仍为 `project | ComfyUI`、`project | browser-use`。

## F. Tests

```text
Backend: 78 tests PASS，0 failed
TypeScript: PASS（tsc --noEmit）
Frontend build: PASS（Vite）
```

Dry-run 的隔离测试确认 0 Provider 调用、五张表 0 写入；Watchlist CRUD 前后 Today 响应一致。测试日志见 [dsih-011-r1-tests.log](evidence/dsih-011-r1-tests.log)。既有 Starlette/httpx 依赖弃用提示仍存在。

## G. Scope Audit

```text
Scheduler modified? NO
Analyzer modified? NO
Priority modified? NO
Today modified? NO
Watchlist CRUD modified? NO
Frontend modified? NO
New infrastructure added? NO
```

代码只修改 `backend/app/intelligence/candidates.py` 与选择策略相关测试 `backend/tests/test_analysis_queue.py`、`backend/tests/test_watchlist.py`；另存本报告与验收证据。

## H. Final

**PASS WITH WARNINGS**

Watchlist 命中可提升候选排序，并让无通用 Gate 命中的 NewsNow Raw Item 获得分析资格；配额、总数、窗口及无 Watchlist 回退均通过测试。正式 dry-run 无候选、无 LLM、无数据库写入。警告为工单示例与现有 Gate Terms 的冲突，以及既有测试依赖弃用提示。

# DSIH-009-R1 验收报告

## A. Scheduler Jobs

| Job | 周期 | 首次运行关系 | max_instances | coalesce |
|---|---:|---|---:|---|
| NewsNow | 60 分钟 | 启动后 60 分钟 | 1 | true |
| GitHub | 120 分钟 | 启动后 120 分钟 | 1 | true |
| RSS | 240 分钟 | 启动后 240 分钟 | 1 | true |
| Auto Analysis | 240 分钟 | RSS 首次运行后 12 分钟 | 1 | true |

已真实启动并停止 Scheduler，注册的四个 Job、下次运行时间、12 分钟错峰和重叠保护见 [注册证据](evidence/dsih-009-r1-registration.json)。无需等待四小时周期。

## B. Collector Once

执行 `run_scheduler --once`，仅运行三个 Collector。该子进程中移除了三个 `DSIH_LLM_*` 环境变量，命令仍完成采集，未调用 LLM。

| Collector | received | inserted | skipped | failed | status |
|---|---:|---:|---:|---:|---|
| NewsNow | 80 | 26 | 54 | 0 | OK |
| GitHub | 3 | 0 | 3 | 0 | OK |
| RSS | 6 | 0 | 6 | 1 | WARNING |

RSS 有一个来源失败，因此 `--once` 退出码为 1；其他来源继续执行，已有成功数据保留。调度汇总未提供失败来源的身份，本报告不推断。详见 [采集日志](evidence/dsih-009-r1-collectors.log)。

## C. Analysis Once

`analyze_queue --dry-run` 预览 3 条 RSS 候选，随后执行一次 `run_scheduler --once-analysis`，复用定时任务函数。selected 3、analyzed 3、skipped 0、failed 0、normal LLM calls 3、repair calls 0、provider abort **NO**、aborted remaining 0、status OK。

| item_id | source | title | result | priority | action |
|---:|---|---|---|---:|---|
| 86 | OpenAI News | Two years of OpenAI Academy | OK | 17 | IGNORE |
| 90 | Google DeepMind Blog | Gemini 3.8 text-to-speech says hello | OK | 39 | WATCH |
| 87 | OpenAI News | OpenAI extends cyber access to Ukraine for civilian defense | OK | 30 | IGNORE |

详见 [候选预览](evidence/dsih-009-r1-dry-run.log)和[分析日志](evidence/dsih-009-r1-analysis.log)。

## D. Cost Guard

selected ≤ 6：**YES（3）**。NewsNow ≤ 2：**YES（0）**。7 天窗口、各来源配额、关键词和 Tier 排序未改动；新增冻结常量测试。每条最多两次调用、每轮最多 12 次调用的既有边界仍由分析队列执行。

## E. Database

| Table | Before | After | 旧记录变化 |
|---|---:|---:|---:|
| sources | 9 | 9 | 0 |
| items | 138 | 164 | 0 |
| analysis | 13 | 16 | 0 |

26 条新增 Raw Item 来自 Collector；3 条新增 Analysis 来自本次分析。原有 Source、Item、Analysis 逐字段比较均未改写，也没有删除。详见[运行前快照](evidence/dsih-009-r1-before.json)与[运行后快照](evidence/dsih-009-r1-after.json)。

## F. Today

`GET /api/v1/today`：HTTP **200**；raw_items 164、analyzed 16、Must Read 2、Relevant 4、Other 10。新分析的 item 86、90、87 均按现有阈值自然进入 Other；Today 代码及规则未修改。

## G. Failure Isolation

Fake LLM 测试中，首条候选发生 `LLM_REQUEST_ERROR` 后立即停止本轮：3 条候选只调用 Provider 1 次，`aborted_remaining=2`，Job 报告 `PROVIDER_UNAVAILABLE`。Schema/JSON 单条失败仍允许后续候选继续；Collector Job 不受 Analysis Job 失败影响。Provider 故障未在真实服务上人为触发。

## H. Regression

后端：**64 tests PASS，0 failed**（[测试日志](evidence/dsih-009-r1-tests.log)）。TypeScript：**PASS**。前端生产构建：**PASS**。测试输出仍有 Starlette/httpx 依赖弃用警告。

## I. Scope Audit

Selector、Gate Terms、Quota、Analyzer、Prompt/Profile、Priority、Today、Connector 均未修改；未新增基础设施、来源或队列表。主要改动：`backend/app/commands/run_scheduler.py`、`backend/app/commands/analyze_queue.py`、`backend/tests/test_scheduler.py`、`backend/tests/test_analysis_queue.py`，以及本报告与验收证据。

## J. Final

**PASS WITH WARNINGS**

第四个 Job 已按 240 分钟周期注册，并与 RSS 错开 12 分钟；单实例与合并执行保护已验证。Collector-only 入口未触发 LLM；显式分析入口成功处理 3 条真实候选并写入 Analysis。Today 200，全部 64 个后端测试、TypeScript 与前端构建通过。警告仅为本次 RSS 采集的一个来源失败，以及既有测试依赖弃用提示。

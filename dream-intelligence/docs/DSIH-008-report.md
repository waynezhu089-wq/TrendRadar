# DSIH-008 验收报告

## A. Scheduler

```text
Implementation: APScheduler 3.11.3，独立 BlockingScheduler 进程
Process entry: 在 backend 目录运行 python -m app.commands.run_scheduler
Manual acceptance: python -m app.commands.run_scheduler --once
Timezone: UTC（计划与每次 Job 的时间戳）
Persistent job store? NO，使用进程内默认存储
```

定时进程实际启动并在约 10 秒观察期内没有立即采集；它按固定间隔运行。`--once` 复用相同三个 Job 函数。采集 Job 调用已有 Connector 与 `save_collection`，没有复制 HTTP、normalize、去重或入库逻辑。

## B. Registered Jobs

```text
NewsNow interval: 60 分钟
GitHub interval: 120 分钟
RSS interval: 240 分钟
Overlap protection: 每个 Job max_instances=1，coalesce=True
```

自动测试核对了三项注册、间隔、非立即触发、重叠保护及失败后的后续 Job 执行。

## C. Once Run

| Job | received | inserted | skipped | failed | status |
|---|---:|---:|---:|---:|---|
| NewsNow | 80 | 46 | 34 | 0 | OK |
| GitHub | 3 | 0 | 3 | 0 | OK |
| RSS | 6 | 0 | 6 | 1 | WARNING |

`--once` 顺序执行了三个 Job。NewsNow 新增的 46 条 Raw 分别来自 Weibo 28、Zhihu 6、Bilibili Hot Search 12。RSS 有一个来源失败，但两个成功来源的 6 条均被正确跳过；汇总日志未记录失败来源的名称，因此不推测具体是哪一个。由于 warning，命令退出码为 1。时间戳与汇总结果见 `evidence/dsih-008-once.log`。

## D. Failure Isolation

```text
Test: 第一个 Job 抛异常，后两个 fake Job 继续执行；异常文本中的测试 secret 不进入日志。
Result: PASS。真实 --once 中 RSS 单源失败独立记录，前两个 Job 已完成。
```

空结果测试确认 `received=0`、`inserted=0` 如实输出。普通定时 Job 运行只输出 Job 名、UTC 起止时间、received、inserted、skipped、failed、status；不输出 Token 或 API Key。

## E. Database

```text
sources before/after: 9 → 9
items before/after: 92 → 138
analysis before/after: 9 → 9
existing Raw mutated? NO，原有 92 条逐字段相同
existing Analysis mutated? NO，原有 9 条逐字段相同
```

Source 也逐字段相同；46 条新增记录均为 NewsNow Raw Item。前后快照及核验摘要：`evidence/dsih-008-before.json`、`evidence/dsih-008-after.json`。

## F. Today

```text
HTTP: 200
Card counts: 9（Must Read 2，Relevant 3，Other 4）
New unanalyzed Raw leaked into Today? NO
```

Today 的 `raw_items` 更新为 138，`analyzed` 仍为 9。

## G. LLM Audit

```text
LLM called? NO
Analyzer invoked? NO
```

Scheduler 的三个生产 Job 只进入现有采集路径。自动测试对三个 Job 分别验证其委托给已有 Connector/保存函数，且不实例化 Analyzer。

## H. Tests

```text
Backend: PASS，50 tests / 0 failed
TypeScript: PASS
Frontend build: PASS
```

测试日志：`evidence/dsih-008-tests.log`。既有 Starlette/httpx 弃用提示仍存在。

## I. Scope Audit

```text
Analyzer modified? NO
Priority modified? NO
Today modified? NO
Connector logic duplicated? NO
New Connector added? NO
Feishu added? NO
Queue infrastructure added? NO
```

仅新增 `backend/app/commands/run_scheduler.py`、`backend/tests/test_scheduler.py`，并在 `backend/pyproject.toml` 增加 APScheduler 3.x 依赖；没有持久化任务表或自动分析队列。

## J. Warnings

- 真实 RSS Job 有一个外部来源失败。现有 Job 汇总日志仅保留失败数，不能据此确定具体来源；未扩大重试或排查范围。
- 在本次工具提供的 Windows 终端中，发送 Ctrl+C 字符和向独立进程组发送 `CTRL_C_EVENT` 均未得到进程内的正常退出输出；测试进程已清理，没有遗留 Scheduler。自动测试覆盖了 Python 收到 `KeyboardInterrupt` 后等待 Job 完成并调用 `shutdown(wait=True)` 的路径。实际终端信号传递仍需人工交互验证。
- 测试依赖存在既有 Starlette/httpx 弃用提示。

## K. Final

**PASS WITH WARNINGS**

三个固定采集 Job 已正确注册，独立进程可启动，`--once` 完成真实采集且失败隔离有效。46 条新 Raw 进入数据库，Analysis 保持 9，Today 返回 200，全部测试通过。RSS 单源失败和本机终端信号传递验证限制保留为警告。

APScheduler 的间隔触发、`max_instances`、`coalesce` 和关闭行为依据[官方 3.x 文档](https://apscheduler.readthedocs.io/en/3.x/userguide.html)。

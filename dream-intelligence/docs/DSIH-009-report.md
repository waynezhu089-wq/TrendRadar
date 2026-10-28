# DSIH-009 验收报告

## A. Policy

```text
Lookback: effective_time = published_at；NULL 时 captured_at；最近 7 天（含边界）
Max total: 6
GitHub quota: 3
RSS quota: 3
NewsNow quota: 2
Gate terms: AI, 人工智能, 大模型, LLM, 模型, 视频生成, 图生视频, ComfyUI, MiniMax, Seedance, Agent, 智能体, MCP, workflow, 工作流, browser, 浏览器自动化, 自动化, 开源, GitHub
```

Tier 顺序为 GitHub → RSS → NewsNow。GitHub/RSS 按 effective_time 降序；NewsNow 按关键词命中数降序，再按 effective_time 降序。所有并列情况由 item_id 保证稳定顺序。此层级仅控制模型调用机会，不改变 Priority 公式。

## B. Dry Run

正式数据库只读预览，0 次模型调用、0 次数据库写入；前后 Source、Item、Analysis 逐字段一致。

| item_id | source | source_type | title | effective_time (UTC) | tier | gate_matches | selection_reason |
|---:|---|---|---|---|---:|---|---|
| 92 | Hugging Face Blog | rss | Accelerating vision-language models with LFM2.5-VL-DSpark | 2026-09-24T14:08:57+00:00 | 2 | — | RSS_RECENT |
| 93 | Hugging Face Blog | rss | How to Use NVIDIA Warp and MjWarp to Accelerate Robotics Simulation and Learning Workflows | 2026-09-23T18:41:40+00:00 | 2 | — | RSS_RECENT |
| 89 | Google DeepMind Blog | rss | Advancing Private AI Compute with secure, server-side memory | 2026-09-23T16:00:57+00:00 | 2 | — | RSS_RECENT |
| 130 | Bilibili Hot Search | newsnow | MiniMax M3.1 Flash上线 | 2026-09-28T11:52:54.342323+00:00 | 3 | MiniMax | NEWSNOW_GATE_MATCH: MiniMax |

```text
already_analyzed: 9
too_old: 0
newsnow_no_gate_match: 122
selected: 4
```

GitHub 的三条现有 Raw 已有 Analysis，本轮无 GitHub 候选。RSS 占 3 个名额；NewsNow 只有 1 条命中门槛。

## C. Real Once

只对上述 4 个 ID 执行一次 `--once`。

| item_id | result | category | priority | dreamstream_relevance | recommended_action | provider_calls | repair_used |
|---:|---|---|---:|---:|---|---:|---|
| 92 | OK | AI | 42 | 40 | WATCH | 1 | FALSE |
| 93 | OK | AI | 29 | 15 | IGNORE | 1 | FALSE |
| 89 | OK | AI | 30 | 15 | IGNORE | 1 | FALSE |
| 130 | OK | AI | 34 | 42 | WATCH | 1 | FALSE |

总计：selected 4，analyzed 4，skipped 0，failed 0，repair_count 0。

再次执行 **dry-run**（没有第二轮模型调用）：四个成功 ID 均不再出现；新预览显示的是另三条尚未分析的 RSS Item（86、90、87），未执行分析。

## D. Database

```text
sources before/after: 9 → 9
items before/after: 138 → 138
analysis before/after: 9 → 13
Raw mutation: NO，138 条逐字段一致
Old Analysis mutation: NO，原有 9 条逐字段一致
Source mutation: NO
```

新增 4 条 Analysis，均为 `dsih-analyzer-v0.1.1`；未建 Queue 表。

## E. Today

```text
HTTP: 200
Must Read: 2
Relevant: 4
Other: 7
new item buckets: 92=RELEVANT, 93=OTHER, 89=OTHER, 130=OTHER
```

Today 阈值与排序未修改。

## F. Cost Guard

```text
selected <= 6? YES (4)
NewsNow <= 2? YES (1)
normal LLM calls: 4
repair calls: 0
total provider calls: 4
maximum allowed per run: 6 items / 12 calls
```

命令中还按每条最多 2 次、每轮最多 12 次封顶；自动测试用 Fake LLM 验证了单条失败后的继续执行和一次 repair 边界。

## G. Tests

```text
Backend: PASS，57 tests / 0 failed
TypeScript: PASS
Frontend build: PASS
```

新增测试覆盖未分析过滤、7 天窗口、NULL 时间回退、tier 顺序、关键词大小写、NewsNow 2 条配额、总数 6、稳定排序、dry-run 无写入/无模型调用、失败隔离和已分析候选跳过。既有 Starlette/httpx 弃用警告仍在。

## H. Scope Audit

```text
Scheduler modified? NO
Connector modified? NO
Priority modified? NO
Today rules modified? NO
New DB table added? NO
Queue framework added? NO
```

只新增 `backend/app/intelligence/candidates.py`、`backend/app/commands/analyze_queue.py` 和 `backend/tests/test_analysis_queue.py`。未将 Analyzer 注册到 Scheduler。

## I. Quality Notes

- 选中的 NewsNow“MiniMax M3.1 Flash上线”命中明确门槛词，但只有标题与 B 站搜索链接；现有 Analyzer 给 credibility 20、Priority 34，说明这次模型没有把标题当作已核实的版本能力。没有选到明显无关的 NewsNow。
- RSS 题为 NVIDIA Warp/MjWarp 机器人仿真的文章，模型给 Dream Stream relevance 15、Priority 29；它进入队列是因为 RSS Tier 免关键词门槛，说明该 tier 会消耗一些低相关条目的模型成本。按工单没有现场调整规则。
- 本次对未入选 NewsNow 的品牌词做了有限抽查，未观察到明显高相关但因门槛词遗漏的样本；这不是对全部 122 条排除项的逐条人工审核。
- Hugging Face 的视觉语言模型条目只有标题，模型说明了证据限制，Priority 42；DeepMind 的 Private AI Compute 摘要与 Feed 自带一句简介一致。

## J. Final

**PASS WITH WARNINGS**

Selector 的顺序、门槛与成本上限可重复验证；dry-run 合理且无写入。一次真实分析成功 4/4，Provider 调用 4 次，Today HTTP 200，所有回归通过。警告保留 RSS Tier 中低相关条目仍会获得分析机会，以及既有测试依赖弃用提示。

证据：`evidence/dsih-009-before.json`、`evidence/dsih-009-dry-run.log`、`evidence/dsih-009-once.log`、`evidence/dsih-009-after-dry-run.log`、`evidence/dsih-009-after.json`、`evidence/dsih-009-tests.log`。

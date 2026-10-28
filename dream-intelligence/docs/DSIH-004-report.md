# DSIH-004｜轻量 Intelligence Analyzer v0.1

执行日期：2026-09-28。

## A. Architecture

- LLM client: app/llm/base.py 的 LLMClient Protocol；openai_compatible.py 使用标准库 HTTP，POST /chat/completions，要求 JSON 输出，无新依赖。
- Analyzer: app/intelligence/analyzer.py；选择无 analysis 的非 Mock item，逐条验证、独立提交，不改 Raw Item。已有分析返回 SKIP，不调用 Provider。
- Priority engine: app/intelligence/priority.py，纯函数；无平台热度。
- Profile: config/intelligence_profile.md，短文本项目关注方向。
- Schema: app/schemas/analysis.py，6 个分数严格整数 0–100，分类与动作枚举验证。非法输出拒绝写入，不自动重试；模型 priority 被忽略。
- CLI: python -m app.commands.analyze_pending --limit 5；默认 5，上限 20。
- Secret 仅来自环境变量，settings repr 隐藏 Key/URL；不输出 Prompt、完整响应或敏感异常。HTTP 重定向不转发 Authorization。
- Fake 只存在于 backend/tests/test_intelligence.py；正式命令无假 Provider 兜底。

## B. Provider

- Real provider configured: NO。只检查环境变量是否存在，未检索其它密钥。
- Model: 未配置。
- Real validation: NOT RUN。
- Warning: **REAL_LLM_NOT_VALIDATED**。
- 已执行真实 CLI --limit 5，明确输出未配置提示，退出码 2，无 API 请求、无数据库写入。

## C. Analysis

正式数据库：

- Pending available: 80。
- Pending selected: 0（配置检查先于选择与写入）。
- Analyzed: 0。
- Skipped: 0。
- Failed: 0 个 item；命令因未配置 Provider 退出，不误记为模型分析失败。

隔离 Fake 完整闭环测试：

- Pending selected: 3。
- Analyzed: 3。
- 同一 3 个 ID 再次执行：Skipped 3，无新增 Provider 调用。
- 再次选择 pending：空列表，无额外调用。
- 失败隔离用例：无效 JSON、Provider 异常、有效输出依次返回 FAIL / FAIL / OK，成功结果仍入库。

## D. Priority

- Version: v0.1-no-hotness。
- Formula: relevance=(personal_relevance+dreamstream_relevance)/2；priority=0.40×relevance+0.20×importance+0.15×actionability+0.10×novelty+0.15×credibility。
- 使用整数权重运算实现四舍五入 half-up，输出 0–100 整数。
- Sample: personal=75、dreamstream=90、importance=80、actionability=80、novelty=70、credibility=85 → 80.75 → 81。
- Tests: 全 0 → 0，全 100 → 100，仅 novelty=5 → 0.5 → 1。
- 模型提供 priority=100 的测试响应实际写入 priority=81。

## E. Database

- 正式 SQLite: data/dsih.db。
- items before/after: 81 / 81。
- analysis before/after: 1 / 1（只有原 Mock）。
- Raw item mutation: NO；所有 items 字段按 ID 序列化的 SHA256 前后一致。
- Fake 测试数据库：仅内存；Mock + 3 个测试 Raw Item，成功后 analysis 从 1 增至 4；原始 items 全字段完全一致。
- 没有 Schema 变更，没有 Fake Analysis 写入正式数据库。
- analyzer_version: dsih-analyzer-v0.1，tags 沿用现有 JSON 列。

## F. Tests

- Executed: python -m unittest discover -s backend/tests -v。
- Passed: 21。
- Failed: 0。
- 11 项 Analyzer/Schema/Provider 新测试，原 10 项回归测试全部通过。
- 覆盖公式及半数进位、分数严格验证、有效/非法 JSON、枚举、模型 priority 忽略、Fake 完整闭环、已分析跳过、单条失败隔离、Raw 不变、limit 边界、无配置退出、HTTP 请求协议和错误脱敏。
- 无真实 API 依赖，无测试 fixture API Key。
- 保留原有 Starlette TestClient/httpx 弃用提示，无测试失败。
- 日志：evidence/dsih-004-tests.log、dsih-004-cli.log。

## G. Regression

- Health API: HTTP 200，status=ok。
- Today API: HTTP 200，仍返回原 Mock 卡片。
- Frontend build/typecheck: PASS，npm run build 包含 tsc --noEmit 和 Vite build。
- NewsNow tests: 全部通过，未重新采集。
- Today API、NewsNowConnector 及 frontend/src 文件 SHA256 均保持一致。
- 证据：evidence/dsih-004-before.json、dsih-004-after.json。

## H. Scope Audit

- Today modified? NO
- Frontend modified? NO
- RSS added? NO
- GitHub Connector added? NO
- Scheduler added? NO
- Feishu added? NO
- MCP added? NO
- Embedding/RAG added? NO
- TrendRadar modified? NO

未引入 LiteLLM、Agent、多代理、自动全文抓取或用户画像系统。
未创建提交、未推送。

## I. Deviations

None。无 Provider 时的 NOT RUN 属于工单允许路径。JSON 修复重试是可选项，本版选择直接拒绝，无自动 retry。

已有接口限制（未修改）：Today 的响应 schema 要求 published_at 非空，而真实 NewsNow Raw Item 可为空。真实 Analysis 将来接入 Today 时需单独处理；本次无真实 Provider 写入，当前 Today 回归正常。这不属于本次已验证的展示能力。

重复 CLI 语义：每次处理下一批 pending，已分析记录从选择中排除；并非重复运行就必然整批 SKIP。针对相同 ID 的 SKIP 已单独测试。并发 CLI 的 token 去重不在 v0.1 范围，运行应串行。

## J. Final

**PASS WITH WARNINGS**

Analyzer 分层、结构化验证与代码 Priority 已完成。
Fake LLM 在隔离 SQLite 中完成闭环，21 项测试和前端构建通过。
正式 items/analysis 均未变化，Today 和前端未修改。
REAL_LLM_NOT_VALIDATED：未配置真实 Provider，未验证真实模型输出或写入。
已达到工单允许的 Stop Rule，停止开发。

# DSIH-006-R2 验收报告

## A. Changes

```text
Analyzer version: dsih-analyzer-v0.1.1
Prompt change: summary 仅陈述 Raw Item 事实；why_it_matters 用有证据边界的条件措辞描述项目关联
Error diagnostics: JSON_PARSE_ERROR / SCHEMA_VALIDATION_ERROR / LLM_REQUEST_ERROR，含简短安全摘要
Repair retry: 仅 JSON 或 Schema 校验失败时，同一 Provider/Model 最多修复一次；原响应只在内存中使用
```

改动仅在 `backend/app/intelligence/analyzer.py`、`backend/app/intelligence/prompts.py` 和 `backend/tests/test_intelligence.py`。不保存完整模型响应或密钥。Priority 公式仍为 `v0.1-no-hotness`。

## B. Tests

```text
Total: 39
Passed: 39
Failed: 0
Repair tests: valid JSON 不重试；JSON/Schema 失败各修复一次成功；修复失败最多一次；单条失败隔离；Raw 不变；错误不含测试密钥；Provider HTTP 状态安全摘要
```

真实 DeepSeek 未用于自动测试。TypeScript 检查与 Vite 构建均通过。测试日志：`evidence/dsih-006-r2-tests.log`。既有 Starlette/httpx 弃用警告仍存在。

## C. ComfyUI Evidence Preview

```text
Old why_it_matters: “ComfyUI 是 DSIH/Dream Stream 的核心工作流引擎；该版本提升模型兼容性、显存与运行稳定性，并更新模板，可能直接影响 AI 视频/图像管线。”
New preview why_it_matters: “这是 ComfyUI 官方版本发布，项目与 DSIH/Dream Stream 关注的 ComfyUI、AI 视频/图像工作流、Wan、MiniMax、Qwen 等方向高度相关。若后续升级采用该版本，可能改善显存占用、模型支持与运行稳定性；但该条目本身只说明上游发布了哪些改动，不代表 DSIH/Dream Stream 已集成或依赖这些更新。”
Writes to production DB? NO
Evidence-bound wording? YES
```

使用 item 82 的真实 Raw Item，在隔离的内存 SQLite 中运行 v0.1.1；模型调用 1 次、Priority 81。正式库中的旧 Analysis 保持原样。

## D. Crawl4AI

```text
Item: 84, unclecode/crawl4ai — Release v0.9.4
First attempt: JSON 与 Schema 校验通过
Repair invoked: NO
Final result: OK，GITHUB，analyzer_version=dsih-analyzer-v0.1.1
Validation error type: none
Priority: 44
Dream Stream relevance: 50
Recommended action: WATCH
```

真实模型调用 1 次。Analysis 仅据 Release 正文概括版本和安装方式，并明确正文没有功能细节；没有追加抓取外部 changelog。

## E. Database

```text
sources before/after: 7 → 7
items before/after: 84 → 84
analysis before/after: 6 → 7
Raw item mutation: NO，84 条逐字段摘要一致
Existing analysis mutation: NO，原有 6 条逐字段摘要一致
```

## F. Duplicate Guard

```text
Second run: item 84 SKIP（already analyzed）
LLM called again? NO，计数 0
```

## G. Today

```text
HTTP: 200
Must Read: 3
Relevant: 1
Other: 3
Crawl4AI bucket: RELEVANT
```

Today 显示 Raw 84、Analyzed 7。未调整分桶规则。

## H. Scope Audit

```text
Priority modified? NO
Today rules modified? NO
Profile topic scope modified? NO
Connector modified? NO
ComfyUI stored Analysis overwritten? NO
New framework added? NO
React UI modified? NO
Database Schema modified? NO
```

详细前后快照、隔离预览、真实分析和 Today 响应：`evidence/dsih-006-r2.json`。其中没有 API Key，也没有完整模型原始响应。

## I. Final

**PASS WITH WARNINGS**

v0.1.1 的错误分类、有限修复与证据边界测试通过。ComfyUI 预览不再把高相关性表述为已接入的内部事实。Crawl4AI 成功写入第 7 条 Analysis，第二轮 SKIP，并自然进入 Today Relevant。唯一现存警告为测试依赖的 Starlette/httpx 弃用提示。

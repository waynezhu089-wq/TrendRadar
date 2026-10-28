# DSIH-006-R2｜Analyzer v0.1.1 最小可信度与结构化输出修复

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：DSIH-006-R1 完成修复  
优先级：P0  
目标：只修复本轮真实 GitHub 分析暴露出的两个问题，不新增功能。

已知基线：

```text
sources = 7
items = 84
analysis = 6
```

已成功：
- ComfyUI → Priority 85 → Must Read
- browser-use → Priority 71 → Must Read
- Raw Item 未修改
- Today HTTP 200
- 33 tests PASS

未完成：
- Crawl4AI 首次模型返回未通过 JSON / Schema 校验，未写入 Analysis
- 当前 Analyzer 丢弃了具体解析/校验错误，无法定位失败原因
- 当前 Analyzer 没有实现此前设计中的“最多一次有限 JSON 修复重试”
- ComfyUI `why_it_matters` 出现一处过强的内部项目事实表述：
  “ComfyUI 是 DSIH/Dream Stream 的核心工作流引擎”
  当前证据只支持“与 Dream Stream 高相关 / 可能直接影响视频工作流”，不支持把它描述为既成内部架构事实

---

# 1. 本工单唯一目标

完成一个极小的：

```text
dsih-analyzer-v0.1.1
```

只增加：

1. 结构化输出失败时的可诊断错误；
2. 最多 1 次有限 JSON / Schema 修复重试；
3. `why_it_matters` 的证据边界约束，避免把“项目相关性判断”写成“已接入/核心引擎/既成事实”。

然后只重试 Crawl4AI item。

不得扩展其它能力。

---

# 2. 保持不变

禁止修改：

```text
Priority Formula
Today Rules
Intelligence Profile 的关注主题
Category 列表
recommended_action 枚举
NewsNow Connector
GitHub Connector
React UI
数据库 Schema
```

不得引入：

```text
LiteLLM
LangChain
RAG
Agent
MCP
Embedding
```

---

# 3. 结构化错误诊断

当前失败结果只剩：

```text
invalid JSON or analysis schema
```

v0.1.1 必须区分至少：

```text
JSON_PARSE_ERROR
SCHEMA_VALIDATION_ERROR
LLM_REQUEST_ERROR
```

并保留简洁、可审计的错误摘要。

要求：

- 不输出 API Key
- 不默认打印完整原始模型响应
- 不将完整原始响应写入正式数据库
- Schema error 应至少记录失败字段 / validation message
- JSON parse error 应记录解析错误类型/位置（若可得）
- 单条失败继续隔离，不影响其它 item

如果已有内部 Result/Error 类型，做最小扩展；不要建立复杂错误框架。

---

# 4. 最多一次修复重试

仅当首轮出现：

```text
JSON_PARSE_ERROR
或
SCHEMA_VALIDATION_ERROR
```

才允许进行 **1 次**修复调用。

修复调用必须：

- 使用同一 Provider / Model
- 输入首轮原始响应（仅内存）
- 输入简洁验证错误
- 明确要求：
  - 只返回合法 JSON
  - 严格符合现有 Analysis Schema
  - 不增加首轮中不存在的新事实
  - 不改变原始 Item 的事实语义
- 不允许第二次修复重试

流程：

```text
首轮成功
→ 正常写入

首轮结构失败
→ 修复 1 次
   → 成功：写入
   → 仍失败：FAIL，停止该 item
```

不得无限重试。

---

# 5. 证据边界 Prompt 最小修正

只在现有 Analyzer Prompt 中增加极短的事实边界要求。

要求模型区分：

```text
A. Raw Item 明确事实
B. Dream Stream / DSIH 相关性判断
```

规则：

- 不得把“高相关”“可能有价值”“可供集成参考”写成既成内部事实
- 除非 Raw Item 或项目 Profile 明确说明，否则不得说：
  - “已经接入”
  - “是核心引擎”
  - “正在生产使用”
  - “将直接改变现有生产系统”
- 推荐使用：
  - “与 Dream Stream 的……高度相关”
  - “可能影响……”
  - “可作为……的参考”
  - “若采用，可……”
- `summary` 只概括 Raw Item，不加入内部项目推断
- `why_it_matters` 才允许做项目相关性判断，但必须使用证据边界语言

不要重写整套 Prompt。

---

# 6. Analyzer 版本

成功修改后：

```text
analyzer_version = dsih-analyzer-v0.1.1
```

Priority 版本保持：

```text
v0.1-no-hotness
```

---

# 7. 自动测试

必须新增最小测试：

1. valid JSON → 不重试
2. invalid JSON → 修复一次成功
3. Schema invalid → 修复一次成功
4. 修复后仍失败 → 最终 FAIL
5. 修复最多一次
6. 单条失败隔离
7. raw item 不被修改
8. API Key / secret 不进入错误日志
9. 既有所有测试继续 PASS

可以使用 Fake LLM 完成。

不要用真实 DeepSeek 跑自动测试。

---

# 8. ComfyUI 旧 Analysis 的处理

**本工单不要修改、删除或覆盖 item 82 已存 Analysis。**

原因：
- 它是此前真实运行的审计证据；
- 当前尚未建立 Analysis 历史 / 受控重算策略；
- 为修一句文字去改历史派生数据会扩大范围。

只做一个**隔离验证**：

使用 item 82 的现有 Raw Item，
调用 v0.1.1 Analyzer 得到一个“不写正式 DB”的 preview 结果。

检查其 `why_it_matters` 是否仍把 ComfyUI 描述成既成的 DSIH/Dream Stream “核心引擎/已接入”事实。

记录 preview，不写数据库。

---

# 9. Crawl4AI 真实重试

只重试：

```text
item_id = 84
unclecode/crawl4ai — Release v0.9.4
```

允许：

```text
首轮 1 次
+
必要时 repair 1 次
```

总真实模型调用最多 2 次。

如果成功：

```text
analysis 6 → 7
```

写入：

```text
analyzer_version = dsih-analyzer-v0.1.1
```

然后再次执行同 item：

```text
SKIP
LLM called again? NO
```

如果仍失败：

```text
BLOCKED
```

并报告明确的 JSON / Schema 错误类型，不再继续调用。

---

# 10. Today 验证

如果 Crawl4AI 成功：

调用：

```text
GET /api/v1/today
```

记录：

```text
HTTP
Must Read
Relevant
Other
item 84 bucket
```

不得调整 Today 阈值。

---

# 11. 回归

必须：

```text
Backend tests PASS
Today API 200
TypeScript PASS
Frontend build PASS
```

---

# 12. 数据库预期

开始：

```text
sources = 7
items = 84
analysis = 6
```

若 Crawl4AI 成功：

```text
sources = 7
items = 84
analysis = 7
```

Raw Items 必须全部保持不变。

ComfyUI / browser-use 已存 Analysis 不变。

---

# 13. 明确禁止

禁止：

```text
新增 Connector
RSS
Market Watch
Watchlist
Feedback
Scheduler
Feishu
MCP

Priority 调参
Today 阈值调参
Profile 重构
大规模 Prompt 重写

重新分析其它 NewsNow Item
批量重算已有 Analysis
Analysis 历史系统
```

---

# 14. Stop Rule

### PASS 条件

```text
v0.1.1 自动测试通过
+
ComfyUI preview 不再出现既成内部架构事实化表述
+
Crawl4AI 成功生成 Analysis
+
analysis = 7
+
Crawl4AI 第二轮 SKIP
+
Today 200
```

### BLOCKED 条件

Crawl4AI 在一次有限 repair 后仍不通过：

```text
停止
保留明确错误证据
不再调用模型
```

---

# 15. 验收报告

保存：

```text
docs/DSIH-006-R2-report.md
```

## A. Changes
```text
Analyzer version:
Prompt change:
Error diagnostics:
Repair retry:
```

## B. Tests
```text
Total:
Passed:
Failed:
Repair tests:
```

## C. ComfyUI Evidence Preview
```text
Old why_it_matters:
New preview why_it_matters:
Writes to production DB? NO
Evidence-bound wording? YES/NO
```

## D. Crawl4AI
```text
First attempt:
Repair invoked:
Final result:
Validation error type:
Priority:
Dream Stream relevance:
Recommended action:
```

## E. Database
```text
sources before/after:
items before/after:
analysis before/after:
Raw item mutation:
Existing analysis mutation:
```

## F. Duplicate Guard
```text
Second run:
LLM called again? NO
```

## G. Today
```text
HTTP:
Must Read:
Relevant:
Other:
Crawl4AI bucket:
```

## H. Scope Audit
```text
Priority modified? NO
Today rules modified? NO
Profile topic scope modified? NO
Connector modified? NO
ComfyUI stored Analysis overwritten? NO
New framework added? NO
```

## I. Final
只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 16. 核心原则

这次不是“让模型更聪明”。

只做两件事：

```text
结构化输出失败时可恢复、可诊断
+
项目相关性判断不冒充内部既成事实
```

保持 1.0 轻量。

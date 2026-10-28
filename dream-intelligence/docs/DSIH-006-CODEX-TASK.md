# DSIH-006｜GitHub Radar Connector v0.1

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase B / GitHub Radar  
优先级：P0

当前状态：
- NewsNow Connector 已可稳定采集中文热点
- Analyzer v0.1 已冻结
- Today Intelligence v0.1 已完成
- 当前 Today 的 1 个 Must Read 仍主要来自 Mock，高相关真实来源尚不足

本工单目标：

> 让 DSIH 第一次从 GitHub 获取与 Dream Stream 高相关的真实结构化信息。

不扩功能，不做 GitHub 深度代码审计。

---

# 1. 本工单唯一目标

新增：

```text
GitHubConnector
```

完成：

```text
GitHub API
   ↓
GitHubConnector
   ↓
normalize
   ↓
DSIH sources / items
   ↓
SQLite
```

只接 3 个仓库：

```text
Comfy-Org/ComfyUI
browser-use/browser-use
unclecode/crawl4ai
```

完成真实采集和去重后立即停止。

---

# 2. 采集范围

v0.1 只采集：

```text
Latest Releases
```

如果某仓库没有 Release，可退化为：

```text
最近 commit / default branch HEAD
```

但每仓库只选一种最简单、稳定的公开结构化信息。

禁止本工单加入：

```text
Issues
Pull Requests
Stars growth
Fork growth
Contributors
README semantic analysis
Code search
Repository cloning
Automatic code audit
```

---

# 3. API 与认证

优先使用 GitHub REST API。

支持：

```text
GITHUB_TOKEN
```

但 Token 必须是可选的。

没有 Token 时：

```text
允许匿名公共 API
```

只要当前 3 个仓库和本次单次采集能完成即可。

不得：

```text
要求用户提供 Token 才能运行
把 Token 写入源码
输出 Token
提交 Secret
```

如遇 rate limit：

记录并停止，不做代理/绕过。

---

# 4. Connector 接口

复用现有 Connector 约定：

```text
collect()
normalize()
health()
```

不要搭新插件系统。

---

# 5. Source 设计

每个 GitHub 仓库对应一个 `source`：

```text
ComfyUI
browser-use
Crawl4AI
```

建议：

```text
type = github
category = GITHUB
```

Connector 是 GitHub。

Source 是具体仓库。

不要只创建一个：

```text
GitHub
```

来源必须保持可追踪。

---

# 6. Item Normalize

最低字段：

```text
source_id
external_id
title
url
content
author
published_at
captured_at
```

建议映射：

## Release

```text
title = repository + release/tag name
url = release html_url
content = release body（可截断到合理长度）
author = release author
published_at = published_at
external_id = repo + release id/tag
```

如果 fallback 为 commit：

```text
title = commit message 第一行
url = commit html_url
content = commit message
author = commit author
published_at = commit timestamp
external_id = commit SHA
```

保留原始事实，不生成 AI 摘要。

---

# 7. 去重

使用稳定：

```text
external_id
```

连续执行两次必须满足：

```text
第一次插入
第二次已有记录 SKIP
```

允许上游真实出现新 Release/Commit 导致少量新增。

不要做复杂语义去重。

---

# 8. 手动采集命令

提供最小命令，例如：

```bash
python -m app.commands.collect_github
```

输出至少：

```text
ComfyUI
received:
inserted:
skipped:
failed:

browser-use
...

Crawl4AI
...
```

不要加入 Scheduler。

---

# 9. 不调用 Analyzer

本工单：

```text
只采集 Raw Item
```

不得调用 DeepSeek。

不得写入新的 analysis。

原因：

先验证 GitHub Connector 自身。

下一工单再用现有 Analyzer 对少量 GitHub Raw Item 做 Intelligence 验证。

---

# 10. Today

本工单禁止修改：

```text
/api/v1/today
React Today
Intelligence Card
Today Rules
```

GitHub Raw Item 暂时不进入 Today，直到经过 Analysis。

---

# 11. 测试

最低新增：

```text
GitHub release normalize test
Commit fallback normalize test（如实现 fallback）
stable external_id test
duplicate insertion test
single repo failure isolation test
optional token behavior test
```

现有全部测试必须继续通过。

---

# 12. 真实验收

实际运行一次采集：

```text
Comfy-Org/ComfyUI
browser-use/browser-use
unclecode/crawl4ai
```

记录：

```text
received
inserted
skipped
failed
```

再运行第二次：

验证去重。

数据库预期：

```text
sources:
原有 4 + 3 GitHub sources

items:
原有 81 + 新 GitHub raw items

analysis:
仍保持 4
```

如上游当前结构导致某仓库没有 Release，按本工单允许的 fallback 最小处理。

---

# 13. 错误隔离

一个仓库失败：

```text
其他仓库继续
```

不要整体中断。

例如：

```text
ComfyUI OK
browser-use FAIL
Crawl4AI OK
```

仍保存成功源。

---

# 14. 明确禁止

禁止：

```text
LLM 调用
Analyzer 修改
Priority 修改
Today 修改

RSS
Market Watch
Watchlist
Feedback

Scheduler
Feishu
MCP

GitHub Repo Clone
Code Audit
Issue/PR analysis
Star trend analytics
GitHub Trending crawler

Embedding
RAG
Agent
Deep Research
```

---

# 15. Stop Rule

满足：

```text
3 个 GitHub Source 建立
+
真实 GitHub Raw Item 进入 SQLite
+
第二轮去重通过
+
analysis 未增加
+
全部测试通过
```

立即停止。

---

# 16. 验收报告

保存：

```text
docs/DSIH-006-report.md
```

结构：

## A. Connector
```text
API:
Auth mode:
Repositories:
```

## B. Collection Run 1
```text
ComfyUI:
browser-use:
Crawl4AI:
Total received:
Inserted:
Skipped:
Failed:
```

## C. Collection Run 2
同上。

## D. Database
```text
sources before/after:
items before/after:
analysis before/after:
```

## E. Dedup
```text
Stable external_id:
Second run duplicates:
```

## F. Failure Isolation
```text
Result:
```

## G. Tests
```text
Backend:
TypeScript:
Frontend build:
```

## H. Scope Audit
```text
LLM called? NO
Analyzer modified? NO
Priority modified? NO
Today modified? NO
NewsNow modified? NO
RSS added? NO
Scheduler added? NO
Feishu added? NO
MCP added? NO
GitHub deep audit added? NO
```

## I. Deviations
没有则：

```text
None
```

## J. Final
只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 17. 核心原则

本工单不是“做 GitHub 情报分析”。

只做：

```text
GitHub
→ Raw Item
```

让 DSIH 先拥有第二类真实 Connector，再让现有 Analyzer 去判断哪些 GitHub 变化值得看。

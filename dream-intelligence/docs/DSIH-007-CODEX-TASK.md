# DSIH-007｜RSS 官方 AI 来源 Connector v0.1

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase B / RSS  
优先级：P0

当前正式基线：

```text
sources = 6
items = 83
analysis = 6
```

已完成：
- NewsNow 中文热点 Connector
- GitHub Release Connector
- Analyzer v0.1.1
- Today Intelligence v0.1
- 生产 Mock 已退场，Today 当前只显示真实 Intelligence

本工单目标：

> 为 DSIH 接入第三类真实来源：官方 AI RSS / Atom。

只做 RSS → Raw Item，不调用 LLM。

---

# 1. 本工单唯一目标

新增通用：

```text
RSSConnector
```

接入 3 个官方结构化来源：

```text
OpenAI News
https://openai.com/news/rss.xml

Google DeepMind Blog
https://deepmind.google/blog/rss.xml

Hugging Face Blog
https://huggingface.co/blog/feed.xml
```

完成：

```text
Official RSS / Atom
      ↓
RSSConnector
      ↓
normalize
      ↓
sources / items
      ↓
SQLite
```

---

# 2. 来源边界

本工单只使用上述 3 个官方 Feed。

禁止擅自替换为：

```text
第三方 RSS 镜像
RSSHub
Google News 搜索 Feed
网页爬虫生成 RSS
```

如果某个官方 Feed 当前不可访问或格式异常：

```text
单源 FAIL
其余继续
```

在报告中记录，不自行换源。

---

# 3. Connector 接口

复用现有统一约定：

```text
collect()
normalize()
health()
```

不要建立新的插件框架。

建议使用成熟轻量 RSS/Atom 解析库；若项目已有可复用依赖优先复用。

不要手写完整 RSS/XML 解析器。

---

# 4. Source 设计

每个 Feed 创建一个独立 Source：

```text
OpenAI News
Google DeepMind Blog
Hugging Face Blog
```

建议：

```text
type = rss
category = AI
```

Source URL 保存实际 Feed URL。

不要只建立一个笼统的：

```text
RSS
```

---

# 5. 初次采集数量

为防止第一次接入把历史文章全部灌入数据库：

```text
每个 Source 最多取最新 3 条
```

本工单最大新增约：

```text
3 sources
9 raw items
```

如果 Feed 自身少于 3 条，则按实际数量。

不要做历史回填。

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
raw_json
```

映射原则：

### title
使用 Feed entry 原标题。

### url
使用 entry 的 canonical/link。

### content
优先顺序：

```text
content
→ summary / description
→ ""
```

如果内容包含 HTML：

```text
转为干净纯文本
```

只处理 Feed 自带内容。

**不得在本工单继续抓取文章正文页面。**

建议限制合理长度，例如最多 5,000 字符，避免异常 Feed 体积污染数据库。

### author
Feed 有则保存；无则 NULL。

### published_at
Feed 有合法时间则保存；没有则 NULL。

不得用 `captured_at` 伪造 `published_at`。

---

# 7. Stable external_id

优先：

```text
entry.id / guid
```

如果不存在：

```text
normalized canonical URL
```

再没有才：

```text
source + title + published_at 的稳定 hash
```

要求同一 entry 多次采集生成相同 external_id。

---

# 8. Raw JSON

保存必要的原始 entry 数据，保持可审计。

不要存整个 Feed XML 文档。

不得改写标题或内容为 AI 生成文本。

---

# 9. 去重

第一次：

```text
最多新增 9 条
```

立即第二次运行：

```text
相同 entry → SKIP
```

理想：

```text
inserted = 0
skipped = 首轮已写入数量
```

如果两次运行之间 Feed 确实发布了新内容，可以出现真实新增；必须在报告中解释具体条目。

不做语义去重。

---

# 10. 手动采集命令

提供最小命令，例如：

```bash
python -m app.commands.collect_rss
```

输出至少：

```text
OpenAI News
received:
inserted:
skipped:
failed:

Google DeepMind Blog
...

Hugging Face Blog
...
```

不要加 Scheduler。

---

# 11. 网络与错误策略

普通 HTTP 客户端即可。

可设置合理：

```text
User-Agent
timeout
```

允许少量普通网络重试，例如连接失败 / 5xx 的简单重试，但不要建设通用网络框架。

禁止：

```text
Cloudflare 绕过
Browser automation
Proxy rotation
Cookie harvesting
Captcha
```

单 Feed 失败不得中断其它 Feed。

---

# 12. 不调用 Analyzer

本工单：

```text
RSS → Raw Item
```

不得调用 DeepSeek。

不得新增 Analysis。

因此正式数据库应保持：

```text
analysis = 6
```

---

# 13. Today

本工单禁止修改：

```text
/api/v1/today
Today Rules
React Today
Intelligence Card
```

RSS Raw Item 在没有 Analysis 前：

```text
不进入 Today
```

---

# 14. 测试

最低新增：

```text
RSS parse / normalize test
Atom 兼容测试（如 3 个 Feed 中实际需要）
HTML summary → plain text test
stable external_id test
missing published_at → NULL test
duplicate insertion test
single feed failure isolation test
max 3 items per source test
```

使用 fixture / fake HTTP，不依赖外网跑自动测试。

现有所有测试继续 PASS。

---

# 15. 正式数据库验收

开始：

```text
sources = 6
items = 83
analysis = 6
```

如果 3 个官方 Feed 均成功：

```text
sources = 9
items <= 92
analysis = 6
```

最终以实际 Feed 返回为准。

要求：
- 真实旧数据不修改
- 已有 Analysis 不修改
- RSS 只新增 Raw Item

---

# 16. 真实验收两轮

## Run 1

实际联网采集：

```text
OpenAI News
Google DeepMind Blog
Hugging Face Blog
```

记录每源：

```text
received
inserted
skipped
failed
```

## Run 2

立即再次运行。

验证 stable ID / dedup。

---

# 17. 禁止事项

禁止：

```text
LLM 调用
Analyzer 修改
Priority 修改
Today 修改
NewsNow 修改
GitHub Connector 修改

全文网页抓取
Crawl4AI 网页抓取
Browser Scout
Deep Research

Scheduler
Feishu
Watchlist
Feedback
Market Watch
MCP
RAG
Embedding
Agent
```

---

# 18. Stop Rule

满足：

```text
RSSConnector 完成
+
官方 Feed Raw Item 进入 SQLite
+
第二轮去重通过
+
analysis 保持 6
+
测试通过
```

立即停止。

若某单 Feed 因外部网络 / 格式问题失败：

```text
允许 PASS WITH WARNINGS
```

前提是 Connector 本身和其它来源已证明正常，且未擅自换成第三方来源。

---

# 19. 验收报告

保存：

```text
docs/DSIH-007-report.md
```

## A. Sources

```text
OpenAI News:
Google DeepMind:
Hugging Face:
```

记录 Feed URL、HTTP/解析状态。

## B. Run 1

逐源：

```text
received:
inserted:
skipped:
failed:
```

## C. Run 2

同上。

## D. Sample Rows

每个成功 Feed 至少列 1 条：

```text
source
external_id
title
url
published_at
content preview
```

## E. Database

```text
sources before/after:
items before/after:
analysis before/after:
existing real rows mutated? NO
```

## F. Dedup

```text
Stable external_id:
Second run duplicate behavior:
```

## G. Failure Isolation

```text
Result:
```

## H. Tests

```text
Backend:
TypeScript:
Frontend build:
```

## I. Scope Audit

```text
LLM called? NO
Analyzer modified? NO
Priority modified? NO
Today modified? NO
NewsNow modified? NO
GitHub Connector modified? NO
Full-page crawling added? NO
Scheduler added? NO
Feishu added? NO
```

## J. Deviations

没有则：

```text
None
```

## K. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 20. 核心原则

本工单不是“建立 AI 新闻系统”。

只做：

```text
3 个官方高质量 RSS / Atom
→ 稳定 Raw Item
```

等 Connector 验证完成后，再单独决定哪些 RSS Item 值得进入 Analyzer。

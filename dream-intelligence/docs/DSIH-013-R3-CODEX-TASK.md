# DSIH-013-R3｜Announcement Scheduler v0.1 — 自动发现 + 轻量读取

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase E / Market Watch 自动化  
优先级：P0

前置已验收：
- DSIH-013：深交所官方公告元数据采集 PASS
- DSIH-013-R1：易读 PDF 正文轻量提取 PASS
- DSIH-013-R2：未读 / 已读状态 PASS
- 当前可立克 10 条公告已入库，公告 1 最终为已读，其余 9 条未读

本工单只做：

> **自动发现新公告，并对新公告做轻量正文读取；难处理的直接跳过。**

不做推送、不调用 LLM、不判断利好利空。

---

# 1. 本工单唯一目标

在现有 Scheduler 中新增第 6 个 Job：

```text
Market Announcements
```

每次执行：

```text
读取 enabled Market Watchlist
→ 拉取最近官方公告
→ 只写入新公告
→ 对“尚未处理正文”的最新公告做轻量 PDF 文本提取
→ 易读：READABLE
→ 难读：SKIPPED_COMPLEX
→ 新公告天然保持未读
```

---

# 2. 调度时间

使用：

```text
timezone = Asia/Shanghai
```

第一版低频执行：

```text
周一至周五
18:30
22:30
```

可使用一个 Cron Job：

```text
hour = "18,22"
minute = 30
day_of_week = "mon-fri"
```

理由：
- 收盘后公告集中披露；
- 22:30 再补一次晚间公告；
- 避免高频抓取。

不要增加交易日历。

---

# 3. 现有 Scheduler Job 全部冻结

当前已有：

```text
NewsNow
GitHub
RSS
Auto Analysis
Market Collector
```

它们的：
- interval / cron
- timezone
- offset
- max_instances
- coalesce

全部不改。

新增公告 Job 后：

```text
job count = 6
```

---

# 4. Job 必须复用现有能力

新增最小调度函数，例如：

```text
collect_market_announcements_job()
```

但它只能编排现有 service：

```text
SZSEAnnouncementProvider
announcement persistence
PDF light extractor
```

不得在 Scheduler 里复制：
- SZSE HTTP 请求；
- external_id 生成；
- PDF 下载逻辑；
- pypdf 提取；
- read/unread 逻辑。

---

# 5. 公告采集边界

对每只 enabled Market Watchlist：

```text
最近最多 10 条官方公告
```

只支持当前已实现的：

```text
SZ
```

若未来 Watchlist 中出现：

```text
SH / BJ
```

当前 Job：

```text
记录 UNSUPPORTED
继续其他股票
```

不要把整个 Job 置为失败。

---

# 6. 正文轻量读取

采集完成后，对：

```text
没有 market_announcement_documents 记录的公告
```

按：

```text
published_at DESC
```

最多处理：

```text
每只股票每轮 3 条
```

使用现有 R1 规则：

```text
普通 PDF 文本层 → READABLE
扫描 / 空白 / 加密 / 明显复杂 → SKIPPED_COMPLEX
网络/临时解析问题 → FAILED
```

禁止：

```text
OCR
视觉模型
浏览器自动化
复杂 PDF 修复
```

---

# 7. FAILED 重试边界

`FAILED` 表示普通可重试失败。

v0.1 每次 Scheduler Job：

```text
允许重新尝试 FAILED
```

但每份公告每轮最多：

```text
1 次
```

不要在同一 Job 内循环重试。

`READABLE` / `SKIPPED_COMPLEX`：

```text
永久 SKIP
```

除非未来人工重置；本工单不做重置功能。

---

# 8. 未读状态

新公告写入后：

```text
不创建 market_announcement_reads
```

因此自然为：

```text
is_read = false
```

正文读取成功或失败：

```text
都不得自动标记已读
```

用户仍需自己点击：

```text
标记已读
```

---

# 9. Job 日志

每轮至少记录：

```text
job=market_announcements
started_at
finished_at
watchlist_count

ann_received
ann_inserted
ann_skipped
ann_failed

docs_selected
docs_readable
docs_skipped_complex
docs_failed

status
```

每只股票可附：

```text
symbol
market
new_announcements
```

不得输出：
- 完整 PDF 正文；
- Secret；
- 大块原始响应。

---

# 10. 失败隔离

要求：

```text
一只股票公告失败
≠ 其它股票停止

一份 PDF FAILED
≠ 其它公告正文停止

公告 Job 失败
≠ 其它 5 个 Scheduler Job 停止
```

保持现有 Scheduler Job 隔离。

---

# 11. 手动验收入口

新增显式：

```bash
python -m app.commands.run_scheduler --once-announcements
```

只执行：

```text
Market Announcements Job
```

不得运行：
- Market 日线；
- Auto Analysis；
- NewsNow/GitHub/RSS。

若为了 CLI 需要明显重构，则 STOP / BLOCKED；不要扩大。

---

# 12. 真实验收

不等待 18:30 / 22:30。

执行：

```text
run_scheduler --once-announcements
```

允许当前结果为：

```text
ann_inserted = 0
```

因为最近 10 条可立克公告已经存在。

验收重点：

```text
Job 路径真实运行
同公告去重
正文状态不重复处理
未读状态不改变
```

如果当前还有未处理的 7 条公告：

```text
本轮最多处理最新 3 条
```

这属于正常真实验收。

---

# 13. 页面 / API 回归

执行后：

```text
GET /api/v1/market → 200
```

确认：
- `unread_announcement_count` 正常；
- `is_read` 正常；
- `read_status` 正常；
- 官方链接保留；
- Market 行情 / technical 不受影响。

不得修改 UI。

---

# 14. 不调用 LLM

严格：

```text
LLM calls = 0
```

不得：
- 摘要；
- 公告分类；
- 利好/利空；
- 重要性评分；
- 股价影响；
- 投资建议。

---

# 15. 数据库边界

允许：

```text
market_announcements 新增真实公告
market_announcement_documents 新增/更新正文处理状态
```

禁止修改：

```text
sources
items
analysis
feedback
intelligence watchlist
market_watchlist
market_snapshots
已有 market_announcements 内容
已有 READABLE / SKIPPED_COMPLEX document
market_announcement_reads
```

新公告不得自动创建已读行。

---

# 16. 自动测试

至少新增：

```text
scheduler registers announcement as 6th job
cron = Mon-Fri 18:30 and 22:30
timezone = Asia/Shanghai
max_instances=1
coalesce=true
existing 5 jobs unchanged
job reuses existing announcement collector
max 3 unprocessed docs per stock per run
READABLE/SKIPPED_COMPLEX not reprocessed
FAILED can retry on later run
one PDF failure does not stop later PDFs
new announcement remains unread
--once-announcements runs only announcement job
LLM not called
other scheduler jobs unaffected
```

使用 Fake Provider / fixture PDF / temp DB。

不要真实等待 Cron。

---

# 17. Scope 禁止项

禁止：

```text
Feishu
系统通知
邮件通知
浏览器通知

OCR
LLM
摘要
利好/利空
公告重要性评分

交易逻辑
新 Market Provider
SH/BJ Provider
交易日历

修改已有 5 个 Scheduler Job
修改 Market Technical State
修改 Today
```

---

# 18. Stop Rule

满足：

```text
第 6 个 Job 注册成功
+
Mon-Fri 18:30 / 22:30 Asia/Shanghai 正确
+
现有 5 个 Job 不变
+
--once-announcements 真实跑通
+
公告去重有效
+
正文每轮最多 3 条
+
易读则读 / 难读则跳过
+
未读状态不自动改变
+
LLM 0 调用
+
Market API 200
+
全部测试通过
```

立即停止。

---

# 19. 验收报告

保存：

```text
docs/DSIH-013-R3-report.md
```

## A. Scheduler Registration

```text
job count:
announcement job:
cron:
timezone:
max_instances:
coalesce:
existing 5 jobs changed? NO
```

## B. Real Once

```text
watchlist_count:
ann_received:
ann_inserted:
ann_skipped:
ann_failed:

docs_selected:
docs_readable:
docs_skipped_complex:
docs_failed:
```

逐条列本轮实际处理的公告。

## C. Read State

```text
unread before:
unread after:
auto-marked read? NO
existing read row changed? NO
```

## D. Database

```text
market_announcements before/after:
market_announcement_documents before/after:
market_announcement_reads before/after:
existing business tables changed? NO
```

## E. API

```text
GET /api/v1/market:
unread count:
read_status:
is_read:
official links:
```

## F. Failure Isolation

```text
single announcement failure:
single PDF failure:
other scheduler jobs unaffected:
```

## G. LLM Audit

```text
LLM called? NO
Analyzer invoked? NO
```

## H. Tests

```text
Backend:
TypeScript:
Frontend build:
```

## I. Scope Audit

```text
existing scheduler jobs modified? NO
announcement collector logic duplicated? NO
PDF extractor logic duplicated? NO
OCR added? NO
Trading logic added? NO
```

## J. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 20. 后续边界

本工单通过后：

> Market Watch 的“自动行情 + 自动公告发现 + 轻量正文 + 未读提醒”基础层可视为完成。

下一阶段再决定是否进入：

```text
Phase F｜Feishu
```

优先做：
- Daily Brief；
- Market 新公告未读提醒；
- 高优先级 Intelligence 摘要。

不提前在本工单实现。

---

# 21. 核心原则

这一阶段只负责：

> **“新公告自动进来；容易读的自动读；难的保留官方链接；看没看过由用户自己确认。”**

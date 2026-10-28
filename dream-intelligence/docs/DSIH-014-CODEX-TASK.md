# DSIH-014｜Feishu Daily Brief v0.1 — 手动真实推送闭环

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase F / Feishu  
优先级：P0

前置已验收：
- 自动采集 / 自动分析 / Today 已闭环
- Market 行情 / 技术状态 / 官方公告 / 公告未读状态已闭环
- DSIH-013-R3：公告自动发现 + 轻量读取 PASS

本工单第一次接入手机端。

目标：

> **把 DSIH 已有的高价值信息，压缩成一条飞书 Daily Brief，手动真实发送成功。**

本工单不接 Scheduler，不做双向交互。

---

# 1. 本工单唯一目标

实现：

```text
Today Intelligence
+
Market Watch
+
未读官方公告
      ↓
Daily Brief Builder
      ↓
Feishu Custom Bot Webhook
      ↓
手机飞书
```

先手动：

```bash
--dry-run
--once
```

验证真实消息。

---

# 2. 飞书接入方式

第一版只支持：

```text
飞书群自定义机器人 Webhook
```

配置：

```text
DSIH_FEISHU_WEBHOOK_URL
```

必须：
- 只从环境变量读取；
- 不写入源码；
- 不写进报告；
- 不输出完整 Webhook URL；
- 不提交 Git。

如果环境变量不存在：

```text
dry-run 仍必须可用
真实发送验收 = BLOCKED
```

不要擅自要求用户提供到聊天中。

---

# 3. 不做飞书应用 / OAuth

本工单禁止：

```text
飞书企业自建应用
OAuth
tenant_access_token
用户 open_id
消息回调
卡片按钮回调
双向交互
```

第一版只做单向 Custom Bot Webhook。

---

# 4. 消息格式

优先使用：

```text
interactive message card
```

如果当前官方 webhook 格式验证明显增加复杂度，可退回：

```text
post / rich text
```

但不要退回纯文本大段堆砌。

目标是手机可快速扫读。

---

# 5. Daily Brief 内容

第一版只发一条消息。

建议结构：

```text
Dream Intelligence｜Daily Brief
生成时间：...

🔥 Must Read（N）
1. 标题
   一句话摘要
   [查看原文]

2. ...

👀 Relevant（N）
1. ...
2. ...

📈 Market
可立克 002782.SZ
最近交易日：...
收盘：...
当日涨跌：...
距 MA20：...
20日区间位置：...

📢 未读公告（N）
1. 日期｜公告标题
   [查看官方公告]
2. ...
3. ...
```

---

# 6. 内容上限

为了减少通知焦虑：

```text
Must Read 最多 3 条
Relevant 最多 3 条
未读公告最多 3 条
```

若更多：

```text
显示“另有 X 条”
```

不要一次发几十条。

---

# 7. Intelligence 链接

对 Must Read / Relevant：

优先使用 Raw Item 的：

```text
url
```

飞书手机端可直接打开外部原文。

不要发送：

```text
http://127.0.0.1:5173
localhost
```

因为手机无法访问本机 localhost。

若某 Intelligence 没有有效外部 URL：

```text
不显示链接按钮
```

不要伪造链接。

---

# 8. Market 内容

第一版只展示 Market Watchlist 中现有股票。

当前：

```text
002782 | SZ | 可立克
```

只使用已有 Market API / service 数据：

```text
latest date
close
change_pct
close_vs_ma20_pct
range_position_20d
```

缺失字段：

```text
—
```

不要增加新的技术指标。

---

# 9. 公告内容

只使用：

```text
is_read = false
```

的官方公告。

按：

```text
published_at DESC
```

最多 3 条。

每条链接：

```text
官方深交所 URL
```

正文是否 READABLE 不影响提醒：

```text
READABLE → 仍提供官方链接
SKIPPED_COMPLEX → 仍提供官方链接
```

不要把完整公告正文塞进飞书。

---

# 10. 不调用 LLM

Daily Brief 只拼装：

```text
现有 Analysis.summary
现有 Market 数据
现有公告标题
```

严格：

```text
LLM calls = 0
```

不要为飞书再次摘要。

---

# 11. Builder

实现一个纯/轻量 Builder，例如：

```text
build_daily_brief(...)
```

输出结构与发送层解耦。

要求：
- 可单测；
- 不直接发 HTTP；
- 不读 Secret；
- 不写数据库。

---

# 12. Feishu Sender

实现最小：

```text
FeishuWebhookSender
  send(payload)
```

职责只包括：
- POST webhook；
- 超时；
- 解析飞书成功/错误返回；
- 不记录 Secret。

不要把业务查询写进 Sender。

---

# 13. CLI

新增：

```bash
python -m app.commands.send_feishu_brief --dry-run
```

行为：

```text
构建真实 Daily Brief
0 HTTP webhook calls
0 DB writes
输出安全 preview
```

Preview 可以显示：
- 标题；
- 计数；
- 各 section 标题；
- 链接域名/目标标题。

不要输出 Webhook URL。

新增：

```bash
python -m app.commands.send_feishu_brief --once
```

行为：

```text
构建同一 payload
→ 发送一次
→ 成功即停止
```

不自动重复发送。

---

# 14. 发送失败策略

本工单不做重试队列。

一次真实发送：

```text
成功 → PASS
失败 → 记录错误码 / 简洁信息 → BLOCKED
```

不要：
- 无限 retry；
- 切换 webhook；
- 自动创建机器人。

---

# 15. 无内容情况

即使：

```text
Must Read = 0
Relevant = 0
未读公告 = 0
```

`--dry-run` 应正常生成。

真实 `--once` 默认：

```text
不发送空 Daily Brief
```

返回：

```text
NO_CONTENT
```

但当前正式库已有内容，因此真实验收应有消息。

---

# 16. 数据库边界

本工单：

```text
0 DB writes
```

禁止修改：

```text
sources
items
analysis
feedback
watchlist
market_watchlist
market_snapshots
market_announcements
market_announcement_documents
market_announcement_reads
```

发送飞书不能自动把公告标记已读。

---

# 17. Scheduler

本工单：

```text
Scheduler modified? NO
```

先真人看一次消息效果。

通过后下一张才做：

```text
DSIH-014-R1｜Feishu Daily Brief Scheduler
```

---

# 18. 自动测试

至少新增：

```text
builder limits Must Read to 3
builder limits Relevant to 3
builder limits unread announcements to 3
“另有 X 条” calculation
external item URL included
localhost URL never included
missing URL handled
market missing values handled
read announcements excluded
announcement official link preserved
builder causes zero DB writes
sender success response
sender failure response
webhook secret not logged
dry-run makes zero HTTP webhook calls
--once makes at most one webhook call
empty content does not send
LLM never invoked
```

使用 Fake Sender / mock HTTP。

---

# 19. 真实验收

## Step A — Dry Run

执行：

```bash
send_feishu_brief --dry-run
```

报告：
- Must Read 数量；
- Relevant 数量；
- Market 数量；
- 未读公告数量；
- 最终卡片 section；
- 截断结果。

确认：
- 无 localhost 链接；
- 无 Secret；
- 无完整公告正文。

## Step B — Webhook 检查

读取环境变量：

```text
DSIH_FEISHU_WEBHOOK_URL
```

如果不存在：

```text
FINAL = BLOCKED
reason = FEISHU_WEBHOOK_NOT_CONFIGURED
```

但已完成的代码和测试保留。

## Step C — Real Send

若 webhook 已配置：

```bash
send_feishu_brief --once
```

最多发送一次。

人工确认：
- 飞书收到消息；
- 手机上结构清晰；
- Intelligence 外部链接可点击；
- 深交所公告链接可点击。

---

# 20. 明确禁止

禁止：

```text
Scheduler 推送
即时告警
Critical Alert
Watchlist Alert

飞书按钮交互
反馈回传
已读回传

OAuth
飞书应用
多群组管理

LLM
公告再次摘要
市场 AI 解读

邮件
微信
Telegram
```

---

# 21. Stop Rule

### PASS

满足：

```text
Daily Brief Builder 完成
+
dry-run 正确
+
真实 Webhook 发送成功
+
手机可读
+
外部链接可点击
+
0 DB writes
+
0 LLM
+
测试通过
```

立即停止。

### BLOCKED

若唯一阻塞是：

```text
DSIH_FEISHU_WEBHOOK_URL 未配置
```

则：
- 不绕过；
- 不伪造成功；
- 报告已完成的工程部分；
- 等用户本地配置后续续单。

---

# 22. 验收报告

保存：

```text
docs/DSIH-014-report.md
```

## A. Message Builder

```text
Must Read total/shown:
Relevant total/shown:
Market count:
Unread announcements total/shown:
localhost links present? NO
```

## B. Dry Run

```text
status:
HTTP calls:
DB writes:
LLM calls:
```

## C. Feishu Config

```text
webhook configured?:
webhook logged? NO
```

## D. Real Send

```text
attempted?:
result:
Feishu response code/status:
message received by user?:
```

不要记录完整 webhook。

## E. Link Check

```text
Intelligence external links:
Announcement official links:
localhost links:
```

## F. Database

```text
all existing tables changed? NO
```

## G. Tests

```text
Backend:
TypeScript:
Frontend build:
```

## H. Scope Audit

```text
Scheduler modified? NO
LLM called? NO
Read state changed? NO
Feishu interactive callback added? NO
New notification channel added? NO
```

## I. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 23. 后续边界

本工单通过后，下一步：

```text
DSIH-014-R1｜Feishu Daily Brief Scheduler
```

再决定每天几点推送。

之后才考虑：

```text
Critical Alert
Watchlist Alert
```

---

# 24. 核心原则

Feishu v0.1 只负责：

> **“每天把最值得看的少量信息送到手机。”**

不负责：

> **“把所有信息都推给用户。”**

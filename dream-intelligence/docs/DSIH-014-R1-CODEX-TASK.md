# DSIH-014-R1｜Feishu Daily Brief Scheduler v0.1

## 0. 目标

前置：DSIH-014 已完成真实飞书单次发送并由手机端验收。

本工单只做：

> 把已经验收通过的 Daily Brief 接入现有 Scheduler，每天早上自动发送 1 次，并防止同一天重复发送。

不新增消息内容，不做 Critical Alert，不做双向交互，不调用 LLM。

---

## 1. 调度配置

不要把用户时区和具体时间写死进代码。

使用环境变量：

```text
DSIH_FEISHU_BRIEF_TIME
DSIH_FEISHU_BRIEF_TIMEZONE
```

格式：

```text
HH:MM
IANA timezone
```

例如：

```text
08:30
Asia/Tashkent
```

该示例只说明格式，不是固定生产值。

如果任一变量缺失或非法：
- 不注册 Daily Brief Job；
- 其它现有 Scheduler Job 正常运行；
- 输出安全状态 `FEISHU_BRIEF_SCHEDULE_NOT_CONFIGURED`；
- 不猜测用户时间。

Webhook 继续使用已有：

```text
DSIH_FEISHU_WEBHOOK_URL
```

缺失 Webhook 时同样不注册 Brief Job，不影响其它 Job。

---

## 2. Scheduler

现有 6 个 Job 全部冻结：

```text
NewsNow
GitHub
RSS
Auto Analysis
Market Collector
Market Announcements
```

它们的 interval / cron / timezone / offset / max_instances / coalesce 全部不改。

配置完整后新增第 7 个 Job：

```text
Feishu Daily Brief
```

Cron：

```text
每天
hour/minute = DSIH_FEISHU_BRIEF_TIME
timezone = DSIH_FEISHU_BRIEF_TIMEZONE
max_instances = 1
coalesce = true
```

---

## 3. 完全复用 DSIH-014

Scheduler Job 必须复用现有：

```text
Daily Brief Builder
FeishuWebhookSender
```

禁止复制第二套：
- 消息拼装；
- 截断规则；
- HTTP Sender。

内容保持：

```text
🔥 Must Read
👀 Relevant
📈 Market
📢 未读公告
```

仍按现有上限：

```text
Must Read ≤ 3
Relevant ≤ 3
未读公告 ≤ 3
```

---

## 4. 当日重复发送保护

新增最小表：

```text
notification_deliveries
```

建议字段：

```text
id
channel
notification_type
delivery_date
status
sent_at
created_at
```

唯一约束：

```text
UNIQUE(channel, notification_type, delivery_date)
```

当前固定：

```text
channel = feishu
notification_type = daily_brief
```

规则：
- `delivery_date` 必须按 `DSIH_FEISHU_BRIEF_TIMEZONE` 计算；
- 真实发送成功后才写 `SENT`；
- 同一 delivery_date 已有 `SENT` → Scheduler Job 直接 SKIP，HTTP=0；
- 发送失败不得写 `SENT`；
- dry-run 不写任何 delivery；
- 不做通用通知中心。

---

## 5. 手动 CLI

现有：

```bash
python -m app.commands.send_feishu_brief --dry-run
python -m app.commands.send_feishu_brief --once
```

语义保持不变。

新增验收入口：

```bash
python -m app.commands.run_scheduler --once-brief
```

只执行 Scheduler 版本的 Daily Brief Job，不运行其它 Job。

`--once-brief` 必须受到“当日已发送”保护。

---

## 6. 失败策略

发送失败：

```text
status=FAILED
本轮停止
不自动重试
```

不得切换通知通道。

下一次正常调度仍可尝试，因为当天没有 SENT 记录。

---

## 7. 空内容

若现有 Builder 返回无内容：

```text
NO_CONTENT
HTTP=0
DB writes=0
```

不得发送空卡片。

---

## 8. 数据库边界

允许新增：

```text
notification_deliveries
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

发送 Brief 不得自动：
- 标记公告已读；
- 改 Feedback；
- 改 Watchlist。

---

## 9. 自动测试

至少覆盖：

```text
valid HH:MM
invalid time safe reject
valid IANA timezone
invalid timezone safe reject
missing schedule => Brief Job not registered
missing webhook => Brief Job not registered
configured => scheduler job count = 7
existing 6 jobs unchanged
configured cron uses configured timezone
max_instances=1
coalesce=true
scheduled job reuses existing builder/sender
successful send writes one SENT delivery
same-day second run => SKIP + zero HTTP
different delivery_date => eligible
delivery_date uses Brief timezone
failed send does not create SENT
dry-run remains zero DB writes
manual send_feishu_brief --once semantics unchanged
--once-brief runs only Brief Job
LLM never invoked
```

使用 Fake Sender / temp DB；自动测试禁止真实发送飞书。

---

## 10. 真实验收

### A. Config Check

只输出：

```text
webhook: SET/MISSING
brief time: SET/MISSING
brief timezone: SET/MISSING
```

绝不输出 Webhook 内容。

若时间 / 时区未配置：

```text
BLOCKED
```

不要猜值。

### B. Scheduler Registration

配置完整后确认：

```text
job count = 7
Brief cron/timezone 正确
其它 6 Job 不变
```

无需等待真实早晨。

### C. First Real Run

执行：

```text
python -m app.commands.run_scheduler --once-brief
```

要求：
- 最多 1 次 Webhook；
- 飞书真实收到一条；
- 手机端排版 / 链接保持 DSIH-014 已验收效果。

### D. Same-Day Guard

立即再次执行：

```text
python -m app.commands.run_scheduler --once-brief
```

必须：

```text
SKIP_ALREADY_SENT_TODAY
HTTP calls = 0
```

---

## 11. 禁止事项

禁止：

```text
Critical Alert
Watchlist Alert
即时推送

飞书回调
按钮交互
OAuth
飞书应用

修改 Builder 内容
修改 Today / Market / 公告规则

LLM
邮件
微信
Telegram
```

---

## 12. Stop Rule

PASS 条件：

```text
第 7 个 Job 注册成功
+
使用用户配置的时间 / 时区
+
其它 6 个 Job 不变
+
第一次 Scheduler 真实发送成功
+
同日第二次自动 SKIP
+
0 LLM
+
公告已读状态不变
+
全部测试通过
```

立即停止。

如果唯一缺少的是 Daily Brief 的时间或时区配置：

```text
BLOCKED
```

保留已完成工程，不猜用户偏好。

---

## 13. 验收报告

保存：

```text
docs/DSIH-014-R1-report.md
```

至少包含：

### A. Config
```text
webhook configured?:
brief time configured?:
brief timezone configured?:
secret logged? NO
```

### B. Scheduler
```text
job count:
brief cron:
brief timezone:
max_instances:
coalesce:
existing 6 jobs changed? NO
```

### C. Real Send
```text
delivery_date:
first run:
HTTP calls:
provider status:
message received?:
```

### D. Duplicate Guard
```text
second same-day run:
HTTP calls:
delivery rows:
```

### E. Database
```text
notification_deliveries before/after:
existing business tables changed? NO
read state changed? NO
```

### F. Tests
```text
Backend:
TypeScript:
Frontend build:
```

### G. Scope Audit
```text
Builder modified? NO
LLM called? NO
Critical Alert added? NO
Interactive callback added? NO
```

### H. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

## 14. 核心原则

> 每天早上自动送一条；不多发；同一天不重复发。

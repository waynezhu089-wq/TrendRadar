# DSIH-G01｜48 小时加速真实使用观察 — Activation

## 0. 工单定位

项目：Dream Stream Intelligence Hub（DSIH / Radar）  
阶段：Phase G｜真实使用  
类型：临时运行配置，不是新业务功能

当前状态：
- Windows Scheduler 已常驻并登录自启动
- 现有 7 个 Job 已验收
- Daily Brief 已可真实发送
- 当前目标不是继续开发，而是在 48 小时内增加真实运行样本

本工单只做：

> **将 DSIH 暂时切换到 48 小时加速观察频率，并准备自动恢复原频率。**

---

# 1. 先保存基线

在任何改动前记录：

```text
当前时间
Scheduler PID
7 个 Job 的完整 trigger / timezone / offset
数据库各表行数
notification_deliveries 行数
logs/scheduler.log 当前大小
```

保存到：

```text
docs/evidence/dsih-g01-before.json
```

---

# 2. 48 小时临时频率

仅临时调整采集 / 分析频率：

```text
NewsNow Collector     15 分钟
GitHub Collector      30 分钟
RSS Collector         60 分钟
Auto Analysis         120 分钟
```

Market 保持：

```text
工作日 16:10 Asia/Shanghai
```

Market Announcements 临时改为：

```text
工作日
08:30 / 10:30 / 12:30 / 14:30
16:30 / 18:30 / 20:30 / 22:30
Asia/Shanghai
```

Feishu Daily Brief 保持：

```text
每天 08:30 Asia/Shanghai
```

**Daily Brief 不加频率。**

---

# 3. 冻结所有业务规则

禁止修改：

```text
Candidate Selector
7-day lookback
MAX_TOTAL
Source quotas
NewsNow gate terms
Watchlist Boost
Analyzer
Prompt / Profile
Priority
Today Rules
Daily Brief Builder
Market Technical State
公告轻量读取规则
```

只改 Scheduler trigger。

---

# 4. LLM 成本保护

Auto Analysis 虽加快到 120 分钟，但继续使用现有：

```text
MAX_TOTAL <= 6
NewsNow <= 2
Provider failure abort
single-item repair <= 1
```

不得为了压测提高每轮分析上限。

---

# 5. 修改方式

优先在 Scheduler 的**集中配置位置**做最小临时调整。

不要：
- 复制 Job；
- 新建第二个 Scheduler；
- 同时跑两套频率；
- 修改业务 service。

如果当前代码无法安全集中修改 trigger：

```text
BLOCKED
```

先报告，不做分散式 hack。

---

# 6. 48 小时开始 / 结束

Activation 成功时记录：

```text
PHASE_G_START_AT
PHASE_G_END_AT = START + 48 hours
```

保存：

```text
docs/evidence/dsih-g01-window.json
```

使用带时区时间。

---

# 7. 自动恢复

创建：

```text
scripts/revert_phase_g_acceleration.ps1
```

职责仅：

```text
恢复原 7 个 Job 的正式频率
安全重启 DSIH Scheduler
确认只有 1 个长期 Scheduler PID
记录恢复结果
```

同时创建一次性 Windows Task：

```text
Dream Intelligence Phase G Revert
```

触发时间：

```text
PHASE_G_END_AT
```

执行上面的 revert script。

要求：
- 只运行一次；
- 成功恢复后可自动禁用或删除自身；
- 不打印 Secret；
- 不触发任何业务 Job。

---

# 8. Activation 后立即验证

安全重启 Scheduler 后确认：

```text
Scheduler running = YES
single instance = YES
job count = 7
```

逐项确认临时 trigger：

```text
NewsNow 15m
GitHub 30m
RSS 60m
Auto Analysis 120m
Market unchanged
Market Announcements accelerated
Daily Brief unchanged
```

---

# 9. 不做人为业务触发

本工单不要执行：

```text
--once
--once-analysis
--once-market
--once-announcements
--once-brief
```

Phase G 需要观察**自然调度**，不是人为制造样本。

---

# 10. 观察期不开发

48 小时内禁止继续开发：

```text
Critical Alert
更多 Source
更多股票
更多技术指标
新 Prompt
新 UI
新通知渠道
```

只允许修复：

```text
系统完全停止
数据库损坏风险
Secret 泄露
无限重复发送
明显失控的 LLM 调用
```

一般 Warning 只记录，不立即改。

---

# 11. 观察指标

后续审计至少统计：

```text
Scheduler 总运行时长
每个 Job 运行次数
每个 Job OK / WARNING / FAILED 次数

NewsNow:
received / inserted / skipped

GitHub:
received / inserted / skipped

RSS:
received / inserted / skipped / source failures

Auto Analysis:
selected
analyzed
failed
normal LLM calls
repair calls
provider aborts

Today:
Must Read 数量变化
Relevant 数量变化
Other 数量变化

Market:
snapshot 更新情况

Announcements:
received / new / document readable / skipped complex / failed
unread count

Feishu:
Daily Brief 实际发送次数
duplicate skip 次数
```

---

# 12. 日志安全

继续使用：

```text
logs/scheduler.log
```

检查：
- API Key 不出现；
- Feishu Webhook 不出现；
- 日志没有异常爆炸增长。

不要新增复杂 telemetry 系统。

---

# 13. 数据库安全

Activation 本身：

```text
0 业务 DB 写入
```

自然 Scheduler 在 48 小时内产生正常业务写入是预期行为。

不得：
- 清历史；
- 重置 Analysis；
- 人工制造 Item；
- 批量标记公告已读。

---

# 14. Stop Rule

Activation PASS 条件：

```text
原配置基线已保存
+
临时频率正确
+
Scheduler 单实例正常
+
Daily Brief 仍每天一次
+
48h 自动恢复任务已创建
+
恢复脚本可静态/安全验证
+
0 人为业务 Job 触发
```

满足后立即停止开发，进入等待观察。

---

# 15. Activation 报告

保存：

```text
docs/DSIH-G01-activation-report.md
```

至少包含：

## A. Window
```text
start:
end:
```

## B. Baseline
```text
7 formal schedules:
DB counts:
log size:
```

## C. Accelerated Schedules
```text
NewsNow:
GitHub:
RSS:
Auto Analysis:
Market:
Announcements:
Daily Brief:
```

## D. Runtime
```text
scheduler PID:
single instance:
job count:
```

## E. Revert
```text
revert script:
Windows one-time task:
trigger:
```

## F. Scope
```text
business rules modified? NO
manual jobs triggered? NO
```

## G. Final

只能：

```text
PASS
PASS WITH WARNINGS
BLOCKED
```

---

# 16. 48 小时结束后的下一步

48 小时自然运行完成后，不直接继续开发。

先生成：

```text
DSIH-G01-R1｜48h Observation Audit
```

根据真实日志和数据库决定：
- 哪些频率恢复后仍需调整；
- 哪些 Source 噪音大；
- LLM 成本是否合理；
- Daily Brief 是否真正有价值；
- 1.0 是否可以冻结。

---

# 17. 核心原则

> **先加速观察，不加速开发。**

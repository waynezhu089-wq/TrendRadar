# Tibo 中文动态与额度重置提醒验收 — 2026-10-23

## 用户授权与范围

用户确认账号为 `@thsottiaux`，关注的是 Codex **使用额度重置**，要求定期进入 DSIH、相关消息第一时间以中文发飞书。用户在 DSIH 专用 Chrome 登录 X 后关闭窗口，并明确确认手机收到中文提醒、原帖链接正常。

## 来源与真实读取

- 专用 X 会话以无界面 Chrome 读取成功，首次取得目标作者最近5条帖子；不读取日常浏览器登录数据或导出 Cookie。
- 直接读取并核对截图中的原帖：https://x.com/thsottiaux/status/2113492187770175603 ，发布时间2026-10-23 12:46:19 Asia/Shanghai。
- 同时读到 https://x.com/thsottiaux/status/2113492502355562875 的 “Landing tomorrow before 10am PST together with a small ship.”。忠实译为“明天 PST 上午10点前上线，同时还有一个小更新”，不把 ship 译成船，不自行变更原文时区或推算确定到账时刻。
- [Codex Resets公开API](https://codex-resets.com/api/docs)的status和最近记录接口均HTTP200；无API Key，保留其来源回链。社区分类不冒充作者原文或个人额度核验；不采纳 active_watch 预测或 scheduled_for 推测时刻作为事实。
- 基线共入库10条唯一公开记录。历史基线未批量发送。原文和中文记录独立保存，不伪造 items/analysis、评分或 Intelligence。

## 中文与发送

- 应用真实模型完成中文翻译与分类；源数据只作资料，不执行其指令。英文/无中文的结果不发送。
- “that's a reset”按预告保守处理，不等于执行完毕。普通帖子入平台，额度相关预告/明确完成/社区报告分别标注。
- 用户截图中的当前原帖作为首次验收发送1条中文卡片。首次HTTP请求被飞书以19024（关键词缺失）明确拒绝；补回原有的 `Dream Intelligence` 通知身份后，同一记录第2次请求成功。成功送达1条，不是2条。
- 飞书发送器确认HTTP200和业务码0后记录SENT；唯一事件键为`tibo:2113492187770175603:scheduled`。
- 用户手机验收回复：“已收到中文提醒，链接正常”。因此该条发送与手机链接验收均PASS。
- 首条卡片公开内容留样：`docs/evidence/tibo-first-chinese-alert.json`，不含Webhook。
- 新消息按“帖子ID + 预告/完成阶段”防重。明确拒绝最多尝试3次；网络超时等不确定回执记UNKNOWN，不自动重复发送。

## 运行证据

- `data/tibo-monitor.json`启用固定账号、专用浏览器和每5分钟轮询；新增Job `tibo_monitor`，沿用现有Scheduler单实例。
- 现有任务重载后日志为 `SCHEDULER_STARTED`、`job_count=8`、`formal`。
- 2026-10-23 14:37:26 Asia/Shanghai的首轮自动Job日志：OK、sources_ok=2、inserted=0、baseline=false、errors=[]、sent=0、NO_NEW_ALERTS，证明自动读取与重复抑制生效。
- 状态检查：Windows主任务Running、Scheduler PID单实例；Watchdog仍保留。已有触发规则不变，间隔任务随重载重新计时。没有执行任何`--once*`业务Job。
- API `/api/v1/tibo-monitor`返回200、enabled=true、browser_enabled=true、poll_minutes=5；health、today、daily-brief均200。
- 页面入口：Research左侧“自动订阅 / Tibo · Codex动态”，或`/research?subscription=tibo`。页面按保存时间/原始时间展示中文和出处；浏览器页面视觉验收未单独执行。

## 测试与数据保护

- 后端207项PASS；前端24项PASS；TypeScript及Vite构建PASS。
- 覆盖基线不提醒、新消息中文发送、重复抑制、预告转完成、浏览器补充不重复、源故障隔离、英文结果拒绝、未知回执不重试、社区与原文区分、只读GET、原有调度规则保留。
- 新增三张表前已备份`data/dsih.db.pre-tibo-20261023T063041.bak`。新增记录不写入Daily Brief的按天发送表，也不修改旧资讯和分析。
- 本次只操作授权新增订阅及必要的API/Scheduler重载，没有修改机器人安全配置，没有保存或输出任何Webhook、API Key、密码或Cookie。

## 另发现的既有问题

2026-10-23 08:30的旧Daily Brief日志为FAILED、FEISHU_11232（飞书限流）。本次已告知用户，未补发旧简报或修改其业务逻辑。该故障与新提醒首次19024不是同一错误。

## 限制

电脑需运行、联网、X会话有效。检查周期5分钟，来源和翻译另有延迟；每轮最多翻译2条，积压会顺延。读取限于最近可渲染的目标作者帖子；不承诺全历史、视频内容或个人额度到账。社区完成记录与作者直接明确确认分别标注。

DeepSeek MCP：本次未使用。中文翻译使用应用现有模型API；Codex检查了两条关键译文、分类及真实回执。

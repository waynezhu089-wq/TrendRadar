# DSIH-014 验收报告

## A. Message Builder

- Must Read total/shown: **2 / 2**。
- Relevant total/shown: **4 / 3**，卡片显示“另有 1 条”。
- Market count: **1**（可立克 002782.SZ；只用现有 Market 数据）。
- Unread announcements total/shown: **9 / 3**，卡片显示“另有 6 条”。
- 卡片 section：🔥 Must Read、👀 Relevant、📈 Market、📢 未读公告。
- 格式：单条 Feishu `interactive` 卡片，现有 Analysis 摘要、市场指标和未读公告标题按区块展示；构建器不读 Secret、不发 HTTP、不写数据库。
- Localhost links present? **NO**。实际卡片大小约 **4,165 UTF-8 bytes**，不含完整公告正文。
- [飞书自定义机器人格式参考](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)。

## B. Dry Run

- Status: **DRY_RUN**，使用正式库数据构建成功。
- HTTP webhook calls: **0**。
- DB writes: **0**。
- LLM calls: **0**。
- 预览只输出标题、总数/展示数、section、链接目标标题和域名；不输出 Webhook URL。
- [安全预览](evidence/dsih-014-dry-run.json) · [卡片与数据库核对](evidence/dsih-014-audit.json)。

## C. Feishu Config

- `DSIH_FEISHU_WEBHOOK_URL` configured in the CLI process? **YES**（续单复核）。
- 仅检查了非敏感目标属性：`https`、`open.feishu.cn`、官方自定义机器人路径；无用户信息、查询参数或 fragment。完整 Webhook 与 token 未输出、未写入报告。
- 待发送卡片为约 4,165 UTF-8 bytes：Must Read 2、Relevant 展示 3、Market 1、未读公告展示 3；不含 Webhook、localhost 链接或 PDF 全文。
- Webhook logged? **NO**。

## D. Real Send

- Attempted? **YES，且仅一次**。前两次自动审批在创建进程前拦截；用户针对明确的卡片内容和群聊目标重新批准后，原定 `--once` 命令才实际执行。未绕过审批。
- Result: **SENT**；Webhook HTTP calls **1**，没有自动重试。
- Feishu response code/status: **HTTP 200 / provider code 0**。
- Message received by user? **YES**。用户已在手机飞书确认收到这一条 Daily Brief，卡片易读，情报原文与深交所公告链接均可打开。
- [真实发送结果](evidence/dsih-014-real-send.json) · [此前环境变量缺失时的单次入口结果](evidence/dsih-014-once.json)。完整 Webhook 地址未输出或写入报告。

## E. Link Check

- Intelligence external links: 展示的 5 条含有效外部链接；目标域名包括 `github.com`、`huggingface.co`、`deepmind.google`。
- Announcement official links: 展示的 3 条均指向 `disc.static.szse.cn`；已读公告被排除，正文提取状态不影响官方链接。
- Localhost links: **0**；无 URL 的情报不会伪造链接。
- 用户已确认手机端实际可点击性。

## F. Database

- All existing tables changed? **NO**。`sources`、`items`、`analysis`、`feedback`、`watchlist`、`market_watchlist`、`market_snapshots`、`market_announcements`、`market_announcement_documents`、`market_announcement_reads` 的行数与全行 SHA-256 均和运行前一致。
- 未自动修改公告已读状态。
- [原工单运行前基线](evidence/dsih-014-before.json) · [原工单运行后核对](evidence/dsih-014-audit.json) · [续单发送前基线](evidence/dsih-014-send-before.json) · [续单发送后核对](evidence/dsih-014-send-audit.json)。

## G. Tests

- Backend: `python -m unittest discover -s tests`，**110/110 PASS**。新增 Builder 截断、溢出计数、外链/localhost 过滤、缺失值、已读公告排除、只读查询、Sender 成功/失败与 Secret 隐藏、dry-run 零 HTTP、单次发送上限和空内容不发送的测试。
- TypeScript: `tsc --noEmit` **PASS**。
- Frontend build: `vite build` **PASS**；本工单未改前端。
- [后端测试记录](evidence/dsih-014-tests.txt) · [前端构建记录](evidence/dsih-014-frontend-build.txt)。
- 现有 Starlette `TestClient` 对 `httpx` 的弃用提示仍出现，不影响测试结果。

## H. Scope Audit

- Scheduler modified? **NO**。
- LLM called? **NO**。
- Read state changed? **NO**。
- Feishu interactive callback added? **NO**；卡片只包含普通外部链接。
- New notification channel added? **NO**。
- OAuth、飞书应用、重试队列、推送定时化均未加入。

## I. Final

**PASS WITH WARNINGS** — Builder、dry-run、单次真实发送、服务端成功响应、手机端收件/排版/链接、零数据库写入和测试均已通过。唯一保留 warning 是现有 Starlette `TestClient` 的弃用提示；发送过程中没有重试或额外消息。

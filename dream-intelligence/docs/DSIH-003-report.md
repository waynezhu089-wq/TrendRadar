# DSIH-003｜NewsNow 首个真实 Connector

执行日期：2026-09-28。最终状态：**BLOCKED**。

## A. Connector

- Files created: backend/app/config.py、connectors/base.py、connectors/newsnow.py、commands/collect_newsnow.py，以及包初始化文件。
- API base: https://newsnow.busiyi.world/api/s；可通过 NEWSNOW_API_URL 切换自建端点。
- Platforms: 仅 weibo、zhihu、bilibili-hot-search。
- 接口：collect / normalize / health，无动态注册或插件系统。
- 实现使用 Python 标准库 HTTP 客户端；未复制或读取 TrendRadar 源码。
- 公共地址参考：[NewsNow 官方仓库](https://github.com/newsnext/newsnow)。响应结构另由一次成功的 PowerShell 请求核实；该样本未写入数据库，不计作 Connector 成功。

## B. Collection

| Source | Received | Inserted | Skipped | Result |
|---|---:|---:|---:|---|
| Weibo | 0 | 0 | 0 | FAILED — HTTP 403 |
| Zhihu | 0 | 0 | 0 | FAILED — HTTP 403 |
| Bilibili | 0 | 0 | 0 | FAILED — HTTP 403 |
| Total | 0 | 0 | 0 | Failed sources: 3 |

手动入口实际运行：python -m app.commands.collect_newsnow，退出码 1。
错误正文为 Cloudflare “Attention Required!” HTML。未尝试反爬或防护绕过。
完整日志：evidence/dsih-003-run1.log。

## C. Database

- SQLite: dream-intelligence/data/dsih.db。
- sources rows: 1。
- items rows: 1。
- analysis rows: 1。
- Real sources: 0（仅成功来源事务创建 Source，三源均失败）。
- Real items: 0。
- 原有 Mock Source、Mock Item、Mock Analysis 均保留，无真实新闻假 Analysis。
- author / published_at 调整为 nullable，避免为无作者/发布时间的热点伪造信息。
- 兼容调整前已备份：data/dsih.db.pre-dsih-003-20260928T085642613538.bak。
- 外键检查无异常；未新增数据库表。
- 数据库证据：evidence/dsih-003-database.json。

## D. Dedup Verification

- Live Run 1: 3 源全部 403，未写入。
- Live Run 2: 未执行；已确认防护阻塞，重复失败请求不能证明去重。
- Fixture Run 1: 3 条 inserted。
- Fixture Run 2: 0 条 inserted、3 条 skipped，sources/items 不增长。
- Duplicate behavior: 单元测试通过，真实连续两轮验收尚未完成。
- ID 规则：source + 去空白/fragment 后 URL 的 SHA256；缺 URL 时 source + title。保留 query 参数，不建立复杂 URL 规则。

## E. Failure Isolation

PASS（模拟测试）：微博超时，知乎和 Bilibili 各成功保存 1 条；结果为 FAILED / OK / OK。
真实运行也分别报告三源失败，未在第一个失败处崩溃。
每个成功来源独立事务；数据库异常时回滚当前来源，不回滚其它成功来源。

## F. Tests

- Executed: python -m unittest discover -s backend/tests -v。
- Passed: 9。
- Failed: 0。
- 包括 normalize、stable external_id、duplicate insertion、failure isolation、health failure、旧表兼容保留 Mock、初始化不 Seed，以及原 health/today 两个测试。
- 非阻塞提示：沿用的 Starlette TestClient/httpx 弃用警告。
- 测试日志：evidence/dsih-003-tests.log。

## G. Existing System

- Health API: HTTP 200，status=ok。
- Today API: HTTP 200，仅原有 Mock Intelligence。
- Frontend: 浏览器刷新后仍显示原有 Mock 卡片、Priority 91、Dream Stream Relevance 96。
- Regression: 原测试通过；today.py、Today.tsx、IntelligenceCard.tsx 的前后 SHA256 相同。
- 已重启后端加载新启动逻辑，并再次验证 health/today。
- 启动不再自动 Seed；保留 python -m app.db.seed。现有 Mock 未删除。

## H. Files Changed

- 新增：config.py、connectors/base.py、connectors/newsnow.py、commands/collect_newsnow.py、tests/test_newsnow.py。
- 修改：db/models.py、db/database.py、db/seed.py、main.py。
- 更新：README.md、.env.example、docs/ARCHITECTURE.md。
- 新增：本报告和 docs/evidence 下验收证据。
- 未修改 Today API 或任何前端代码；未修改依赖文件；无提交、无推送。

## I. Scope Audit

- LLM added? NO
- RSS added? NO
- GitHub connector added? NO
- Scheduler added? NO
- Feishu added? NO
- MCP added? NO
- TrendRadar modified? NO

未添加 Analysis/摘要/评分、页面、反爬或复杂去重。

## J. Final

**BLOCKED**

Connector、标准化、入库、基本去重及逐源隔离已实现，9 个测试通过。
公共 API 对 Connector 实际请求返回 Cloudflare 403，真实热点未进入 DSIH。
因此不能宣称达到三平台真实采集与连续两次去重验收。
恢复所需：提供允许该服务端客户端访问的 NewsNow 端点（通过 NEWSNOW_API_URL），或公共端点恢复可用。
届时继续真实 Run 1 / Run 2 和 SQL 验证；不需要进入 AI 或改动 Today。

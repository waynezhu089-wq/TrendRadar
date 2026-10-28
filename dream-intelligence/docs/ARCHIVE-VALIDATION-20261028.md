# 公开源码归档检查 — 2026-10-28

目标仓库：`waynezhu089-wq/TrendRadar`（公开）；分支：`codex/dsih-handoff-20261028`。归档以远程 master 基线 `792bcc3928b1617bba09df34989fd5675c159b86` 为父提交，仅增加 DSIH 子目录、最初工作区报告和根目录接力入口，不修改既有 TrendRadar 文件。

## 纳入与排除

- 原开发目录 349 个非忽略文件完整纳入；追加接力说明、环境版本记录、文件清单、字节保留规则、此次检查记录以及外部工具少量改动补丁/许可。
- 纳入 backend、frontend、工单、config、scripts、测试、验收 JSON/文本/图片。应用逐文件路径、大小、SHA256 见 `ARCHIVE-MANIFEST-20261028.json`；清单不自我包含。
- 不纳入 data、SQLite/备份、登录会话、Cookies、下载素材、真实环境变量、logs、依赖、第三方整仓、缓存、临时文件和原机嵌套 `.git`。
- 对所有候选文件执行与本机进程/Windows 用户级已配置秘密值的字节比对，以及常见模型、Google、GitHub、飞书凭据和私钥格式检查。不输出真实凭据。
- 唯一格式匹配为 `backend/tests/test_feishu_brief.py` 的固定 `SECRET-DO-NOT-LOG` 单元测试假地址，经人工核对放行；无实际配置秘密值命中。这是一次文件发布检查，不是保证检测任何未知秘密形式的证明。
- `.env.example` 仅含空密钥和公开地址示例。身份使用 GitHub no-reply 邮箱，不复制本机认证设置。
- MediaCrawler 与原包比较，确认改动仅 `config/base_config.py` 的四项非秘密配置和 `media_platform/bilibili/core.py` 的三条限额；保存差异补丁与原许可，未复制第三方运行状态。

## 在独立归档副本执行的验证

- Backend：使用原机专用 Python 3.12.14 环境，对归档副本 backend 执行 `python -m unittest discover -s tests`：285 passed，0 failed。不是全新安装 Python 环境的验证。
- Frontend：对归档副本依照 package-lock 进行 `npm ci --offline --ignore-scripts`，缓存安装成功；完整语义测试 46 passed，0 failed；TypeScript 检查与 Vite build 成功。
- Starlette TestClient 弃用提示为已有依赖警告；没有为消除此提示更改依赖。
- 不运行真实采集、真实模型、飞书发送、`--once*` 命令或定时业务；不停止或重新注册原机服务。
- 当前快照是首次集中提交，不能还原此前未提交的每次开发历史。历史工单与验收材料按原样保留，不把原机记录冒充新机验证。

## 接力限制

新机可克隆源码开始开发，但需要重新配置密钥与可选外部工具、登录浏览器。没有迁移个人数据库，因此历史方案/收藏/通知防重不自动出现。通知任务应保持单主机运行，另行决定运行主机和私密数据迁移方式。

发布完成后以 GitHub 分支实际提交 SHA 和远端文件核对为准；此文件不包含自引用提交 SHA。参见 `HANDOFF-20261028.md`。

DeepSeek MCP：本次未使用委派。

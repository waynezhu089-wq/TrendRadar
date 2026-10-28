# Dream Intelligence 开发归档入口

本分支为 `codex/dsih-handoff-20261028`，在用户自己的 TrendRadar Fork 中归档 DSIH 独立开发成果。原有 TrendRadar 代码和历史保留，不混入 DSIH 实现。

- 应用代码、工单、测试和验收：[dream-intelligence/](dream-intelligence/)
- **接力开发先读：[跨主机接力说明](dream-intelligence/docs/HANDOFF-20261028.md)**
- 文件清单与 SHA256：[归档清单](dream-intelligence/docs/ARCHIVE-MANIFEST-20261028.json)
- 最初参考验证报告：[工作区报告](dsih-workspace-reports/)

```powershell
git clone --branch codex/dsih-handoff-20261028 https://github.com/waynezhu089-wq/TrendRadar.git dsih-work
cd dsih-work\dream-intelligence
```

这是公开的开发文件快照；本机数据库、密钥、Cookies、依赖环境、日志和下载资产不在仓库中。新机重新安装依赖和配置；不要在两台主机同时启动通知 Scheduler。

后续修改直接在这个 clone 中提交、推送。历史验收记录不会自动成为新主机的验收结果。

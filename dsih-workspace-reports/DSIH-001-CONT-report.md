# DSIH-001-CONT｜TrendRadar Lab 最小运行验证

执行日期：2026-09-28，Asia/Shanghai。承接 DSIH-001，不重新创建 Fork。

## A. Git

- Local path: C:\Users\zhuxu\Documents\ChatGPT\信息收集平台\TrendRadar
- Origin: https://github.com/waynezhu089-wq/TrendRadar.git
- Upstream: https://github.com/sansan0/TrendRadar.git
- Origin HEAD: 792bcc3928b1617bba09df34989fd5675c159b86
- Upstream HEAD: 792bcc3928b1617bba09df34989fd5675c159b86
- Local HEAD: 792bcc3928b1617bba09df34989fd5675c159b86
- Default/current branch: master
- Status: PASS；clone 用户 Fork 后添加并 fetch upstream，三个 SHA 均匹配用户指定基线。无 merge/rebase/push。
- Fork relationship: 本续单由用户确认真实 Fork，本次不重复创建。

## B. Environment

- OS: Windows NT 10.0.26200.0，PowerShell。
- Python: 3.12.14；使用现有 Codex bundled Python 创建项目 .venv。
- pyproject Python requirement: >=3.12。
- TrendRadar version: 6.10.0（pyproject.toml、version、运行输出一致）。
- License: GNU GPL Version 3，读取仓库 LICENSE。
- Entry Point: python -m trendradar；project script 为 trendradar.__main__:main。
- Install method: 官方 README 推荐 uv sync。本地工具目录 .lab-tools 安装 uv 0.12.19，然后 uv sync --locked --python <现有 Python 路径> --no-python-downloads。
- Install result: PASS；101 个包安装完成，退出码 0；未升级系统 Python，未更改锁文件。
- Runtime directory: C:\Users\zhuxu\Documents\ChatGPT\信息收集平台\TrendRadar-Lab；与仓库内预置历史数据库隔离。

## C. Smoke Test

- doctor: PASS WITH WARNINGS；8 PASS / 2 WARNING / 0 FAIL，退出码 0。
- schedule: PASS；--show-schedule 正常输出，退出码 0。
- warnings: AI 未启用、通知渠道未配置，均符合本工单要求。
- 首轮诊断导入 LiteLLM 时尝试获取远程模型价格表，受网络限制后回退本地；未执行 AI 推理。正式采集设置 LITELLM_LOCAL_MODEL_COST_MAP=True 使用其本地表。
- schedule 输出中的 AI/推送为调度层开关，不等于最终启用状态；已核对执行代码的总开关判断，临时配置关闭 AI analysis、translation 和 notification，filter.method=keyword。
- 实际运行的版本检查另提示：临时 YAML 无版本注释、未复制的三个 AI 配置文件不存在。未修改代码消除提示，未影响采集。
- 完整日志：TrendRadar-Lab/doctor.log、schedule.log；机器可读诊断：output/meta/doctor_report.json。

## D. Real Crawl

- Platforms requested: bilibili-hot-search、weibo、zhihu。
- Platforms succeeded: 三者全部成功。
- Platforms failed: none。
- Items collected: 80；Bilibili 30、微博 30、知乎 20。
- Run result: PASS；仅运行一次正常采集，退出码 0，无异常退出。
- Crawl time: 2026-09-28 16:23，Asia/Shanghai。
- NewsNow 返回状态：Bilibili/微博为缓存数据，知乎为最新数据；这是本次真实公共 API 返回，不宣称所有条目均为即时最新。
- AI Analysis / Translation / Filter: OFF（关键词筛选）。Notifications: OFF。
- RSS、远程存储、自动拉取: OFF；未测试范围外功能。
- 日志：TrendRadar-Lab/crawl.log；退出码：crawl-exit.txt。

## E. SQLite

- DB path: C:\Users\zhuxu\Documents\ChatGPT\信息收集平台\TrendRadar-Lab\output\news\2026-09-28.db
- 本次独立运行目录 DB 文件数量: 1（不包含 upstream 仓库自带历史示例 DB）。
- Tables: platforms, news_items, sqlite_sequence, title_changes, rank_history, crawl_records, crawl_source_status, period_executions, ai_filter_tags, ai_filter_results, ai_filter_analyzed_news。
- news_items: 80 行；crawl_records: 1 行、total_items=80；crawl_source_status 三个平台均 success。
- Sample row count: 3；以只读连接检查，未修改 Schema。
- 已验证 title、platform_id、url、rank、first_crawl_time、last_crawl_time，采集日期在数据库文件名及 crawl_records.created_at 中。

- bilibili-hot-search｜闲木鱼祖峰聊潜伏｜rank=1｜first/last=16-23/16-23
  - URL: https://search.bilibili.com/all?keyword=%E9%97%B2%E6%9C%A8%E9%B1%BC%E7%A5%96%E5%B3%B0%E8%81%8A%E6%BD%9C%E4%BC%8F
- weibo｜中国队亚运王者夺金｜rank=1｜first/last=16-23/16-23
  - URL: https://s.weibo.com/weibo?q=%23%E4%B8%AD%E5%9B%BD%E9%98%9F%E4%BA%9A%E8%BF%90%E7%8E%8B%E8%80%85%E5%A4%BA%E9%87%91%23
- zhihu｜如何看待常德一老人因误解养老金政策拾荒 21 年，最终领到 42 万养老金？暴露了背后哪些问题？｜rank=1｜first/last=16-23/16-23
  - URL: https://www.zhihu.com/question/2087842325703520513

结构与少量抽样证据：TrendRadar-Lab/sqlite-evidence.json。无大量数据导出。

## F. HTML

- Generated: yes，正常采集自然生成。
- Path: C:\Users\zhuxu\Documents\ChatGPT\信息收集平台\TrendRadar-Lab\output\html\2026-09-28\16-23.html
- Latest: TrendRadar-Lab/output/html/latest/current.html。
- Can open: yes；使用仅绑定 127.0.0.1 的临时静态服务，浏览器请求返回 HTTP 200，页面可读。
- Shows real data: yes；页面显示 09-28 16:23、平台 3/3、热榜命中 8/80、AI 未启用，并显示数据库抽样标题“中国队亚运王者夺金”和 rank=1。
- HTML 只展示官方关键词命中的 8 条，SQLite 存储全部 80 条。
- 未修改 HTML。验证结束已停止临时 HTTP 服务；HTML 文件仍可本地打开。

## G. Repository Changes

- Modified tracked files: none，git diff --stat 无输出。
- Added tracked files: none。
- Commits: none。
- Branches created: none，仍为 master。
- 本地新增：项目 .venv；Python 运行自动产生未追踪 __pycache__；配置 origin/upstream 的 .git 本地元数据。
- 仓库外新增：.lab-tools（uv 与缓存）、TrendRadar-Lab（临时配置、运行日志、SQLite、自然生成 HTML、抽样证据）、本报告。
- 未修改生产源码、官方默认配置、锁文件或已有 index.html，未执行 Git add/commit/push。

## H. Final

**PASS WITH WARNINGS**

真实 Fork 已克隆，origin/upstream 与指定提交基线一致。
官方依赖安装成功，doctor 与 schedule 均正常运行。
一次真实公共采集成功，三个源共 80 条数据进入 SQLite。
自动生成的 HTML 可打开，已确认显示本次采集数据。
警告包括预期的 AI/通知未配置提示、初次价格表网络回退及临时配置版本检查提示。
生产源码与受追踪文件无修改；未运行 AI、通知或其它禁止功能。
已达到 Stop Rule，停止后续实验。

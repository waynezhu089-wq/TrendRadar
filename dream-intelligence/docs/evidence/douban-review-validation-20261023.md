# 豆瓣书影评论接入验收 — 2026-10-23

## 实际验证

- 用户在 DSIH 专用普通 Chrome 完成登录并关闭窗口。
- 后续独立浏览器进程在豆瓣首页识别到已登录 DOM，确认会话保留；没有输出、导出或导入 Cookie。
- 图书和电影的短评列表、长评列表均返回 HTTP 200；各一篇长评原始正文页也返回 HTTP 200。
- 按作品名搜索《肖申克的救赎》《三体》，各取得 3 条短评和 1 篇长评节选，无采集错误。
- 通过正常研究采集流程，在独立 SQLite `data/douban-validation-20261023T053900.db` 取得并插入 8 条评论。两篇长评保存的证据长度分别为 1822、3292 字符（含说明），不是列表摘要。
- 真实模型按“比较评论观点和分歧，为视频选题寻找切入点”归纳，研究状态 COMPLETED；指出样本日期为 2005–2014 年，并明确不能推断总体口碑。
- 重放同一批采集证据和已保存分析，新增 0 条；该去重检查未额外请求豆瓣或模型，不应称为第二轮实时采集。
- 独立验收库：sources=2，items=8，analysis=0。验收样本没有写入用户日常数据库或新建用户方案。

## 功能边界

方案助手可选择豆瓣图书/电影首页，也可使用用户明确提供的作品条目网址，不得编造作品 ID。专用登录按钮只打开登录窗口；采集须点击“现在运行”。每个入口最多搜索前两个话题、读取两部作品，每部三条短评、一篇长评正文节选。长评最多保存 6000 字，模型每条只收到前 1200 字，单次综合分析最多 12 条。

原始评论保留原始发布时间和稳定 ID；不强制评论正文包含话题原词。正文可能为旧热门评论，搜索首项可能不是精确作品，页面与分析均提示核对。不支持小组、日记或全站舆情。登录失效、403/429 或验证页会停止继续请求；已取得的评论仍可保存，其他来源继续执行。

没有变更 Scheduler、Watchdog、飞书配置或业务 Job，也未手动发送通知。没有复制外部采集器源码。候选 douban-cli 只提供长评摘要，本次生产适配器使用现有 Playwright 读取原始页面，不依赖该 CLI。

## 检查结果

- 后端隔离回归：181 / 181，通过。现有 TestClient 弃用警告仍存在。
- 前端语义渲染回归：19 / 19，通过。
- TypeScript 检查与 Vite 构建：通过。
- 重载本地 API 前确认无正在运行的研究；仅重载已核实的 uvicorn 进程。
- 更新后 health、today、OpenAPI 均 HTTP 200；豆瓣登录接口及书影分类已注册；前端首页 HTTP 200。
- 登录与真实读入链路：已实测。页面按钮的端到端操作及用户视觉验收：未实测，不标记为用户验收通过。

## 主要文件

`backend/app/research/douban.py`、`backend/app/commands/douban_login.py`、`backend/app/research/collection.py`、`backend/app/research/plan_assistant.py`、`backend/app/api/v1/research.py`、`backend/app/schemas/research.py`、`backend/tests/test_douban.py`、`backend/tests/test_plan_assistant.py`、`frontend/src/api/research.ts`、`frontend/src/pages/Research.tsx`、`README.md`、`.gitignore`。

DeepSeek MCP：本次未使用；实际归纳使用应用自身已配置的模型 API。

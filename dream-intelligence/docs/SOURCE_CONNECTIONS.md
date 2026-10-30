# 可配置来源接口

入口：设置 → 来源接口（`/settings?tab=sources`）。本次提供统一配置、JSON API / RSS 两个通用适配器和 GitHub 项目搜索模板。Hugging Face、Instagram 尚未接入或验收。

## 使用 GitHub 模板

1. 点击“添加 GitHub 项目搜索”，核对配置并保存。这一步只写本机配置，不检索网站。
2. 到“议题与来源”手动建立资讯研究方案，勾选该接口。也可让方案助手根据已配置的接口生成草案。
3. 例如检索式填 `ComfyUI`，排序选择 `stars`，条数填 `6`。网站栏可留空。
4. 方案创建后仍需到 Research 显式点击“现在运行”。本次未新增或启用定时任务。

模板使用 `GET https://api.github.com/search/repositories`，动态映射 `q`、`sort`、`per_page`；固定参数为 `order=desc`、`page=1`。默认追加 `is:public`，只查询公开仓库。默认结果上限 12，方案可选 1–12 条。

“前六”指该检索式返回的前六个结果，不代表整个 ComfyUI 生态的权威榜单。GitHub 的匹配范围、fork 默认规则、限流及 `incomplete_results` 可能影响覆盖。界面展示实际检索式、请求排序、当次数量、排名、star 快照和观测时间。仓库 `created_at` 是建立时间，不能视为新版本发布时间；`updated_at` 单独作为来源元数据保留。

官方接口说明：[Search repositories](https://docs.github.com/en/rest/search/search#search-repositories)；[仓库搜索限定词](https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories)。

## 新增其他同类 API

选择“自定义 JSON API”，按其官方接口文档配置以下内容，无需修改助手提示词或采集路由：

| 配置 | 用途 |
|---|---|
| 网站首页、请求地址 | 来源展示及公开 HTTPS GET 地址；参数另配 |
| 检索词参数名、固定检索限定词 | 将方案检索式传给 API，可追加固定限定词 |
| 固定参数 | 非敏感字符串参数，例如 `page`、`order` |
| 结果数组路径 | 点分隔 JSON 路径，例如 `data.items`；顶层数组留空 |
| 返回字段映射 | `id`、`title` 必填；另支持 `url`、`content`、`published_at`、`stars`、`updated_at` |
| 网址前缀 | 返回值没有原文 URL 时，以前缀加公开记录 ID 构造链接 |
| 排序参数、允许值、默认值 | 来自实际 API 文档；不声称所有 API 都支持 star 排序 |
| 条数参数、上限 | 每接口每次 1 个请求，最多选入 12 条，不自动翻页 |
| 凭据环境变量名、是否必需 | 只保存变量名；运行时从后端进程环境读取 |

返回字段路径只读取字典，不执行表达式、Python、JavaScript、任意命令或动态模块。JSON API 目前只支持 Bearer 认证；多步 OAuth、签名、登录浏览器、非 GET 协议或复杂分页需要单独适配器，不能仅靠填写网址获得能力。这是后续 Hugging Face、Instagram 等来源接入时需要核对的接口契约。

公共 RSS 模板复用现有受限网页采集器，按方案话题或显式检索式字面匹配，每次最多读取三条，不处理登录态。

## 凭据和错误

GitHub 可匿名查询公开资料，选填 `GITHUB_TOKEN`。其他 JSON API 使用 `DSIH_SOURCE_*` 环境变量名，例如 `DSIH_SOURCE_EXAMPLE_TOKEN`。真实值只在本机设置；保存来源时不发送给模型、不写入配置表或日志。`GITHUB_TOKEN` 只能发往 `api.github.com`。不允许复用 `DSIH_LLM_API_KEY` 等其他用途的变量。

接口不接受 URL 用户名/密码、查询字符串里的密钥或任意自定义认证头。每次请求检查公开地址，禁止本机与内网目标，不跟随重定向，不转发系统代理凭据。响应上限 1 MB，超时 12 秒；来源返回 401/403/429 后本次不再请求同一主机，无自动重试。错误不回显提供方响应正文或凭据。

“已配置”“凭据变量已存在”只表示本机配置状态，不是接口连通性、权限、配额或真实采集的验收。来源停用、鉴权失败或映射失效时明确失败，不自动替换网站，也不伪装为成功的空结果。

## 数据和扩展位置

新增三个 SQLite 表：`source_connections` 保存非敏感定义；`research_plan_sources` 保存方案绑定和检索选项；`research_source_reports` 保存每次运行的不可变结果快照。启动仅添加缺失表，不生成示例关注方案或历史数据。

原有方案兼容，未绑定接口的 API 结构保持原状。已有接口可编辑、停用；方案可通过“调整来源接口”修改下次运行设置。历史快照保留，重新分析旧 run 使用旧快照，重复采集同一来源 ID 不重复创建原始条目。新资料属于 `custom_web`，不会自动进入全局 Intelligence 分析队列。

新配置格式在 `backend/app/schemas/source_connections.py`，模板、目录与通用适配器在 `backend/app/research/source_connections.py`。如果新增协议适配器，在这两个位置定义契约和能力，不在方案助手内增加每站分支；助手从服务端目录取得名称、能力和受支持选项，不接触凭据。

数据库、凭据、登录态、运行日志和原机历史仍通过私密渠道管理，不上传公开 GitHub。

## 验证

后端执行 `python -m unittest discover -s tests`，前端执行 `node --test scripts/test-*.mjs`（PowerShell 下列出脚本后传给 Node）及 `npm run build`。新增回归覆盖配置验证、凭据不回显、参数映射、匿名或缺失凭据、重定向、限流、重复记录、历史快照、助手目录校验、显式保存与运行的分离、原方案兼容。

本次开发验证使用隔离数据库与模拟接口；真实 GitHub 请求、模型调用、Scheduler、Watchdog 和飞书发送均不属于本次自动验证。

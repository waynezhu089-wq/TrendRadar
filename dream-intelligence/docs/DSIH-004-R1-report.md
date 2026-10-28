# DSIH-004-R1｜真实云模型验收报告



## A. Provider

Base URL: https://api.deepseek.com

Model: deepseek-flash

API key logged? NO

Connectivity: PASS，最小 JSON 请求成功。

真实分析调用 3 次，另有 1 次无真实 Item 的最小连通性调用；无修复重试。



## B. Selected Items

- item_id: 2；source: Weibo；title: 中国队亚运王者夺金

- item_id: 42；source: Zhihu；title: 我国南疆塔克拉玛干沙漠发现两处大型地下水水源，这意味着什么？将对当地生态和经济带来哪些影响？

- item_id: 79；source: Bilibili Hot Search；title: 星铁真珠角色PV



## C. Real Analysis

以下为模型输出原文及程序计算分数，仅供人工审核；不评价分析质量。



### Item 2

Title: 中国队亚运王者夺金

Source: Weibo

Category: OTHER



Summary: 仅有微博热搜标题，内容为空，指向中国队在亚运会王者荣耀项目夺金，无法核实具体细节。



Why it matters: 属于体育/电竞热点，与 DSIH / Dream Stream 关注的 AI 视频生成、ComfyUI、Agent/Skill/MCP 等方向无直接关系。



Importance: 5



Novelty: 10



Credibility: 15



Personal relevance: 0



Dream Stream relevance: 0



Actionability: 0



Priority: 4



Tags: 微博热搜, 亚运, 电竞, 王者荣耀, 仅有标题



Recommended action: IGNORE



JSON valid? YES

Scores in range? YES

Priority computed by code? YES

Raw item unchanged? YES



### Item 42

Title: 我国南疆塔克拉玛干沙漠发现两处大型地下水水源，这意味着什么？将对当地生态和经济带来哪些影响？

Source: Zhihu

Category: OTHER



Summary: 知乎上的一个提问，声称南疆塔克拉玛干沙漠发现两处大型地下水水源，并询问其对当地生态与经济的影响。目前仅有标题、无正文内容、无来源、无发布时间与作者信息。



Why it matters: 该话题属于地理/资源与区域发展议题，与 DSIH / Dream Stream 的 AI 视频生成、工作流与智能体方向没有直接关联；且仅凭一个提问标题无法核实所谓『大型地下水水源』的真实性与规模。



Importance: 12



Novelty: 20



Credibility: 25



Personal relevance: 5



Dream Stream relevance: 3



Actionability: 5



Priority: 11



Tags: 中国, 新疆, 水资源, 知乎提问, 未核实



Recommended action: IGNORE



JSON valid? YES

Scores in range? YES

Priority computed by code? YES

Raw item unchanged? YES



### Item 79

Title: 星铁真珠角色PV

Source: Bilibili Hot Search

Category: OTHER



Summary: 该条目仅为 B 站搜索页链接，关键词为“星铁真珠角色PV”，没有任何正文、作者或发布时间信息，无法确认具体视频内容。



Why it matters: 这是《崩坏：星穹铁道》角色 PV 的搜索入口，属于游戏/二次元宣传内容，与 AI 视频生成技术或 Dream Stream 工作流无直接关联。



Importance: 8



Novelty: 3



Credibility: 15



Personal relevance: 8



Dream Stream relevance: 5



Actionability: 3



Priority: 7



Tags: Bilibili, 游戏PV, 星穹铁道, 无正文



Recommended action: IGNORE



JSON valid? YES

Scores in range? YES

Priority computed by code? YES

Raw item unchanged? YES



三条 analyzer_version 均为 dsih-analyzer-v0.1；公式版本 v0.1-no-hotness。已从数据库重新读取并用纯函数重算核对 Priority。



## D. Database

items before: 81

items after: 81

analysis before: 1

analysis after: 4

Raw Item 全字段 SHA256 前后一致。正式数据库保留 3 条真实 Analysis，无假数据兜底。



## E. Duplicate Guard

Second run: 3 SKIP（already analyzed）

LLM called again? NO，计数为 0

Duplicate analysis written? NO

使用现有 Analyzer.analyze_one 对明确的三个 ID 验证，无 CLI 或架构修改。



## F. Regression

Tests: 21 passed / 0 failed（原有 TestClient/httpx 弃用提示仍存在）。

Health API: TestClient 对正式数据库验证 HTTP 200。

Today API: FAIL，HTTP 500。现有 IntelligenceCard.published_at 要求 datetime，而本次真实 NewsNow Item 的该字段为 NULL，触发 Pydantic ValidationError。此限制已在 DSIH-004 报告记录，本次真实分析使其实际触发。

宿主重启后 localhost:8000 无监听，改用 FastAPI TestClient 加载当前应用及正式 SQLite 完成 API 回归。

Frontend build/typecheck: PASS（tsc --noEmit + Vite build）。构建通过不代表 Today 页面运行可用。

不将测试 fixture 中 Today 通过误报为正式数据回归通过；本工单禁止修改 Today，未修复该兼容问题。



## G. Scope Audit

Today modified? NO

Frontend modified? NO

NewsNow modified? NO

TrendRadar modified? NO

New provider framework added? NO

LiteLLM added? NO

Agent/MCP/RAG added? NO

未修改生产代码；本次只生成报告/证据并写入授权的三条 Analysis。未提交 Git。



## H. Final

**PASS WITH WARNINGS**

云 API 连通、三条真实 Item 分析入库、程序 Priority、重复 SKIP 四项 Smoke Test 停止条件均满足。

重要警告：Today 在正式数据上返回 500，现有系统回归并非全部通过。需要后续独立工单处理 nullable published_at 的兼容；本次不修改 Today、不伪造时间、不删除真实分析来隐藏问题。

已停止模型调用及开发。
# DSIH-004-R3｜Intelligence Analyzer 正负样本校准

所有输入均为 SYNTHETIC CALIBRATION FIXTURE，不代表真实新闻。

## A. Isolation

Production DB touched? NO（无写入；仅只读完整性校验与 Today 查询）。

Temporary DB used: SQLite :memory:；三条夹具及 Analysis 仅在内存，结束后 engine.dispose，未留下临时 DB 文件。

Production code modified? NO；backend/app、frontend/src、config 文件 SHA256 一致。

正式 DB 整文件 SHA256 前后完全一致；sources=4、items=81、analysis=4。

## B. Provider

Base URL: https://api.deepseek.com

Model: deepseek-flash

API key logged? NO

当前 dsih-analyzer-v0.1、现有 Profile/Prompt、v0.1-no-hotness 公式及 OpenAICompatibleClient 原样使用。正常分析共 3 次，无连通性额外调用，无修复重试或 A/B 测试。

输入保留工单原 Title/Content，仅在 Content 前加 SYNTHETIC CALIBRATION FIXTURE 标签；source.type=calibration，作者/日期为空。

## C. Sample A

Title: AI video model adds multi-reference character consistency and controllable action guidance for production workflows

Category: AI_VIDEO

Summary: 一条标题式信息，声称某AI视频模型新增多参考图角色一致性、更强的动作引导以及可接入生产工作流的能力；正文为合成校准样本，无来源、无URL、无发布时间，也未指明具体模型或厂商。

Why it matters: 多参考图角色一致性与动作可控性正是Dream Stream视频工作室在角色资产复用和分镜生成上的核心痛点，若属实可简化跨镜头角色保持与动作编排流程。

Importance: 55

Novelty: 45

Credibility: 15

Personal relevance: 70

Dream Stream relevance: 78

Actionability: 20

Priority: 50

Tags: AI视频生成, 角色一致性, 动作控制, 工作流集成, 无来源

Recommended action: IGNORE

Priority computed by code? YES；从结构化结果重新计算并核对。

## D. Sample B

Title: Browser automation framework improves agent task reliability and adds workflow integration hooks

Category: OTHER

Summary: 该条目描述一个浏览器自动化框架可提升长时代理可靠性并增加工作流集成钩子，但明确标注为合成校准样本，无 URL、作者或日期，也不是视频生成能力。

Why it matters: 浏览器自动化与代理可靠性对 Dream Stream 的 Agent/Skill/MCP 和自动化模块有潜在价值，但当前无实证细节，无法判断是否值得集成。

Importance: 45

Novelty: 35

Credibility: 5

Personal relevance: 60

Dream Stream relevance: 55

Actionability: 15

Priority: 39

Tags: browser-automation, agent, workflow-integration, synthetic-fixture, infrastructure

Recommended action: IGNORE

Priority computed by code? YES；从结构化结果重新计算并核对。

## E. Sample C

Title: Local food festival draws large weekend crowds

Category: OTHER

Summary: 合成校准样本：某地方美食节周末吸引大量人流，包含餐饮、演出与家庭活动，与AI、视频生成、工作流自动化、Agent或Dream Stream均无直接关系。

Why it matters: 对本项目无实质影响，仅用于验证系统对无关内容的过滤能力。

Importance: 0

Novelty: 0

Credibility: 5

Personal relevance: 0

Dream Stream relevance: 0

Actionability: 0

Priority: 1

Tags: synthetic, local-event, non-ai

Recommended action: IGNORE

Priority computed by code? YES；从结构化结果重新计算并核对。

## F. Ordering Check

Priority A > B > C ? YES（50 > 39 > 1）。

Dream Stream relevance A > B > C ? YES（78 > 55 > 0）。

High sample incorrectly ignored? YES（按默认 READ/WATCH 预期，A 实际返回 IGNORE；是否适用工单的理由例外，留给人工审核）。

Low sample misclassified as AI_VIDEO? NO（C=OTHER）。

A 分类为 AI_VIDEO，B/C 为 OTHER。A、B 均返回 IGNORE，与各自预期 READ/WATCH 不一致。A 的摘要说明合成样本、无来源/URL/时间，B 的解释说明缺少实证细节；仅记录理由，不判定理由是否充分。

明确的合成标签进入了模型输入，模型在输出中引用这一标签并降低可信度/可行动性；本轮不能等同于有可核验来源的真实发布信息校准。未删除标签、未改 Prompt、未重跑。

## G. Hallucination Check

Invented company/version/date/release? NO。

Notes: 对三条输出逐项检查，未新增具体公司、版本、发布日期或将夹具宣称为已核实真实发布事件。模型对项目痛点/潜在价值的描述是其解释，不作为事实背书。

不据此宣布 Analyzer 质量优秀，也不作冻结版本决定。

## H. Regression

Backend tests: 22 passed / 0 failed。

Today API: 200，通过 FastAPI TestClient 查询正式数据库，返回 4 张现有 Intelligence。

原有 Starlette TestClient/httpx 弃用提示仍存在。

## I. Scope Audit

Prompt modified? NO

Profile modified? NO

Priority formula modified? NO

Production DB modified? NO

Today modified? NO

Frontend modified? NO

New framework added? NO

无生产代码修改、无 Git 提交；运行脚本通过标准输入执行，无需保留/删除脚本文件。新增文件仅报告及 docs/evidence 中校准结果与测试日志。

## J. Final

**PASS WITH WARNINGS**

三次真实 DeepSeek 校准、隔离性和两项严格相对排序验证完成，已停止。

警告：A、B 的推荐动作均为 IGNORE；是否接受其对合成、未核验信息的解释，由人工审核。未为满足预期而调整任何配置或公式。

完整证据：docs/evidence/dsih-004-r3-calibration.json；测试日志：docs/evidence/dsih-004-r3-tests.log。

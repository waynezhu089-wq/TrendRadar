# DSIH-007 验收报告

## A. Sources

| Source | 官方 Feed URL | Run 1 HTTP / 解析 | Run 2 HTTP / 解析 |
|---|---|---|---|
| OpenAI News | https://openai.com/news/rss.xml | 请求成功，RSS 解析成功 | 请求成功，RSS 解析成功 |
| Google DeepMind Blog | https://deepmind.google/blog/rss.xml | 请求成功，RSS 解析成功 | 请求返回内容，但解析不到有效 RSS/Atom 条目；单源 FAILED |
| Hugging Face Blog | https://huggingface.co/blog/feed.xml | 请求成功，Feed 解析成功 | 请求成功，Feed 解析成功 |

普通 HTTP 请求成功时未单独记录精确状态码；失败请求会记录 HTTP 错误码。第二轮 DeepMind 未产生 HTTP 异常，失败点是响应体缺少可解析的有效条目。未改用其它来源，也未额外重试。

## B. Run 1

| Source | received | inserted | skipped | failed |
|---|---:|---:|---:|---:|
| OpenAI News | 3 | 3 | 0 | 0 |
| Google DeepMind Blog | 3 | 3 | 0 | 0 |
| Hugging Face Blog | 3 | 3 | 0 | 0 |
| **Total** | **9** | **9** | **0** | **0** |

## C. Run 2

| Source | received | inserted | skipped | failed |
|---|---:|---:|---:|---:|
| OpenAI News | 3 | 0 | 3 | 0 |
| Google DeepMind Blog | 0 | 0 | 0 | 1 |
| Hugging Face Blog | 3 | 0 | 3 | 0 |
| **Total** | **6** | **0** | **6** | **1** |

第二轮 DeepMind 没有有效条目，因此无法用真实第二轮响应验证它的三个条目；其稳定 ID 和重复插入行为已由 fixture 测试覆盖。正式数据库未因此新增重复项。

## D. Sample Rows

| Source | external_id | title | url | published_at | content preview |
|---|---|---|---|---|---|
| OpenAI News | `rss:63b50ae0f1350d018e445b5f75909283d0ef9314d106069ebe0795d700bf260d` | Proaction boosts sales 60% and saves 75+ hours with Codex | https://openai.com/index/proaction | 2026-09-25 19:00:00 UTC | With Codex, GPT-Live-1, and GPT-6 Astra, Proaction builds, operates, and sells modern fleet management faster. |
| Google DeepMind Blog | `rss:3cb022555b599beef3e587822d90f3edacb148e60939ef86bca5d9bf232be96e` | Introducing Gemini 3.8 Live with Live Avatar | https://deepmind.google/blog/introducing-gemini-38-live-with-live-avatar/ | 2026-09-24 16:20:39 UTC | 空：Feed 该条没有可用正文/摘要 |
| Hugging Face Blog | `rss:a25f3647e9ccc0efbdba02dc7d64116013c4dea34082f4f3294f24d56be7b0c9` | Holo4: powering generalist computer-use agents | https://huggingface.co/blog/Hcompany/holo4 | 2026-09-28 09:44:05 UTC | 空：Feed 该条没有可用正文/摘要 |

每个新增 Item 都有 `raw_json`，仅保存该 entry 的必要解析字段；没有存整份 Feed，也没有抓取文章网页。内容上限 5,000 字符，每源最多 3 条。

## E. Database

```text
sources before/after: 6 → 9
items before/after: 83 → 92
analysis before/after: 6 → 6
existing real rows mutated? NO
```

`items.raw_json` 为本单新增的可空 JSON 列，旧 83 条 Item 的原字段逐字段一致，新列均为 NULL；原有 Source 和 Analysis 逐字段一致。迁移前备份由数据库初始化逻辑创建。Today HTTP 200，仍有 6 张已分析卡，RSS Raw Item 数为 9、Today RSS 卡数为 0。

## F. Dedup

```text
Stable external_id: 优先 Feed id/guid；否则规范化 URL；再否则 source + title + published_at 的 SHA256。均带 source 命名空间。
Second run duplicate behavior: OpenAI 3/3 SKIP；Hugging Face 3/3 SKIP；DeepMind 因第二轮响应无有效条目，未参与真实重复验证。
```

## G. Failure Isolation

```text
Result: DeepMind 第二轮解析失败未影响 OpenAI 或 Hugging Face 的采集与去重；单源错误独立记录。
```

## H. Tests

```text
Backend: PASS，45 tests，0 failed（fixture/fake HTTP，无外网）
TypeScript: PASS
Frontend build: PASS
```

覆盖 RSS、Atom、HTML 转纯文本、稳定 ID、缺失发布时间、最多三条、重复写入、单 Feed 失败隔离及旧库添加 `raw_json` 的兼容迁移。现有 Starlette/httpx 弃用提示仍存在。

## I. Scope Audit

```text
LLM called? NO
Analyzer modified? NO
Priority modified? NO
Today modified? NO
NewsNow modified? NO
GitHub Connector modified? NO
Full-page crawling added? NO
Scheduler added? NO
Feishu added? NO
```

新增 `backend/app/connectors/rss.py`、`backend/app/commands/collect_rss.py`、`backend/tests/test_rss.py`；为 Raw JSON 扩展了基础 Item 数据结构、数据库模型与一次可重复执行的轻量迁移；新增 `feedparser` 和 `beautifulsoup4` 依赖。命令：在 `backend` 目录运行 `python -m app.commands.collect_rss`。

## J. Deviations

第二轮 Google DeepMind 官方 Feed 响应没有有效条目，故该源本轮 FAILED；第一轮已成功存入三条真实 Raw Item。其余两源第二轮全部去重。保留官方 URL，未换镜像或抓网页。

## K. Final

**PASS WITH WARNINGS**

三个官方 Feed 第一轮各有三条真实 Raw Item 进入 SQLite，Analysis 保持 6；第二轮可用的六条全部跳过。测试与构建通过。唯一验收限制是 DeepMind 第二轮响应无法解析，真实第二轮去重证据只覆盖 OpenAI 与 Hugging Face。

证据：`evidence/dsih-007-before.json`、`evidence/dsih-007-after.json`、`evidence/dsih-007-run1.log`、`evidence/dsih-007-run2.log`、`evidence/dsih-007-tests.log`。

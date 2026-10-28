# DSIH-006-R3 验收报告

## A. Mock Audit

```text
source: id=1, name=Mock Source, type=mock, url=https://example.com/mock
item: id=1, title=MiniMax releases new video capability, external_id=day1-mock-minimax
analysis: id=1, item_id=1, analyzer_version=mock-v1
evidence: 三条记录的 ID、标识、名称和版本均与 Day 1 测试种子一致；正式库只有这一条 type=mock 的来源及其单条 Item/Analysis。未将真实 NewsNow/GitHub 行判定为 Mock。
```

## B. Database

```text
sources before/after: 7 → 6
items before/after: 84 → 83
analysis before/after: 7 → 6
real rows mutated? NO
```

先做 SQLite 备份，再在单个事务中依次删除已确认的 Analysis、Item、Source；外键检查通过。全部真实 Source、Item、Analysis 在前后逐字段相同。备份：`data/dsih.db.pre-dsih-006-r3-20260928T110115Z.bak`。审计与哈希见 `evidence/dsih-006-r3.json`。

## C. Today

```text
HTTP: 200
Must Read: 2（ComfyUI、browser-use）
Relevant: 1（Crawl4AI）
Other: 3（Zhihu、Bilibili Hot Search、Weibo）
Mock present? NO
```

Today 当前为 Raw 83、Analyzed 6。六张卡全部来自真实数据。

## D. Regression

```text
Backend: PASS，40 tests / 0 failed
TypeScript: PASS
Frontend build: PASS
```

新增一个回归测试，确认直接执行 `app.db.seed` 模块不再插入 Mock；现有 `seed(session)` 函数仅供测试显式调用。应用启动仍只做数据库初始化，不执行 seed。既有 Starlette/httpx 弃用警告仍出现，未在本单处理。测试日志：`evidence/dsih-006-r3-tests.log`。

## E. Scope Audit

```text
LLM called? NO
Analyzer modified? NO
Priority modified? NO
Today rules modified? NO
Connector modified? NO
Database schema modified? NO
```

仅修改 `backend/app/db/seed.py`、`backend/tests/test_newsnow.py`，并保存本报告及证据。未重新分析任何条目。

## F. Final

**PASS WITH WARNINGS**

Mock 身份已唯一确认并从正式数据库移除。Today 不再展示 Mock，全部真实数据保持不变。后端、Today、TypeScript 与前端构建通过；仅保留既有测试依赖弃用警告。

# DSIH-004-R2｜Today NULL 时间字段回归修复

## A. Root Cause

- Root cause: 真实 Item 的 published_at 为 NULL，但卡片 Pydantic Schema 仅接受 datetime，构造响应时抛出 ValidationError。
- Affected schema/file: backend/app/schemas/intelligence.py，IntelligenceCard.published_at。
- 修复前使用正式 SQLite 实际复现 HTTP 500。

## B. Fix

- Backend change: published_at 改为 datetime | None = None。
- Frontend change: frontend/src/api/intelligence.ts 中 published_at 改为 string | null。
- 现有 IntelligenceCard 不显示发布时间，无需改组件或新增时间展示。
- Today 查询及排序未改，未新增 fallback timestamp。
- DB migration: NO。
- 新增回归测试：backend/tests/test_api.py。

## C. API

- Today before: 500。
- Today after: 200。
- 使用 FastAPI TestClient 加载当前应用与正式 data/dsih.db 验证，无数据库依赖替换。
- 返回现有全部 4 张 Intelligence，顺序为 item_id 1、42、79、2。
- NULL published_at serialized: YES；42、79、2 的 published_at 均返回 JSON null，原 Mock 时间保留。
- 证据：docs/evidence/dsih-004-r2-before.json、dsih-004-r2-after.json。

## D. Database

- items before/after: 81 / 81。
- analysis before/after: 4 / 4。
- NULL published_at rows modified? NO；80 个 NULL Item ID 集合完全一致。
- 全部 items 字段按 ID 序列化 SHA256 前后一致。
- 未 UPDATE Raw Item，未新增 Analysis，未迁移数据库。

## E. Tests

- Backend: 22 passed / 0 failed。
- Regression test: test_today_accepts_null_published_at_without_mutating_item 通过；已有有效 Analysis 的 Item 设置 NULL 时间后返回 200、published_at:null，并核对 Raw 全字段未改。
- TypeScript: tsc --noEmit 通过。
- Frontend build: Vite build 通过。
- 原有 TestClient/httpx 弃用警告仍存在，不影响结果。
- 测试日志：docs/evidence/dsih-004-r2-tests.log。

## F. Scope Audit

- LLM called? NO
- Analyzer modified? NO
- Priority modified? NO
- NewsNow modified? NO
- TrendRadar modified? NO
- New feature added? NO

仅修改后端卡片 Schema、前端接口类型、回归测试，并新增验收报告/证据。未提交或推送。

## G. Final

**PASS WITH WARNINGS**

Today 在正式数据上恢复 HTTP 200，NULL 时间原样返回。
数据库 items=81、analysis=4 保持不变，Raw 字段及 80 条 NULL 时间未改写。
22 项后端测试、TypeScript 和前端构建通过。
唯一警告为既有测试依赖弃用提示；已达到 Stop Rule，停止。

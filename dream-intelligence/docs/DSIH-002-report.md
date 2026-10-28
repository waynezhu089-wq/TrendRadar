# DSIH-002 验收报告

日期：2026-09-28。状态：Day 1 Mock Bootstrap。

## A. Project

- Project path: C:\Users\zhuxu\Documents\ChatGPT\信息收集平台\dream-intelligence
- Git initialized: YES，独立 .git，与 TrendRadar 分开。
- Branch: codex/dsih-002。
- Commits: 0；未配置 GitHub remote，未推送。

## B. Backend

- Python: 3.12.14，项目 backend/.venv。
- FastAPI: 0.141.1；SQLAlchemy 2.0.54；Pydantic 2.13.5；Uvicorn 0.54.0。
- SQLite path: C:\Users\zhuxu\Documents\ChatGPT\信息收集平台\dream-intelligence\data\dsih.db。
- Tables: sources、items、analysis，仅三张。
- Health API: GET http://127.0.0.1:8000/api/v1/health → 200，{"status":"ok"}。
- Today API: GET http://127.0.0.1:8000/api/v1/today → 200，从 SQLAlchemy 查询 SQLite，返回一张 Mock 卡片。
- 四项统计均为 1，由查询结果计算；分数全部为 seed mock 值，无评分引擎。

## C. Database

- Source rows: 1，Mock Source，type=mock。
- Item rows: 1，MiniMax releases new video capability。
- Analysis rows: 1，mock-v1；priority=91，dreamstream_relevance=96。
- 启动自动 seed；测试证明重复 seed 不增加记录。
- 数据库被 .gitignore 排除。

## D. Frontend

- Node: 24.19.0；npm 11.17.0。
- React: 19.3.0。
- Vite: 7.3.6；TypeScript 5.9.3。
- URL: http://127.0.0.1:5173/。
- CORS 仅允许 localhost:5173 和 127.0.0.1:5173 的 GET。
- 页面明确显示 Day 1 Mock Bootstrap、MOCK DATA，并说明内容与分数为 mock。

## E. End-to-End

- SQLite → API: PASS。
- API → React: PASS。
- Card visible: PASS，浏览器实际显示 TODAY 和一张卡片。
- Refresh retains data: PASS。
- 证据步骤：直接查询 SQLite，确认三张表各 1 行；访问 health/today 获得 HTTP 200；只修改 DB 标题为 MiniMax Mock Verification，API 与浏览器均显示修改后的标题；恢复原标题，重新调用 API 并刷新浏览器，均恢复原标题。此验证未改前端代码。
- 浏览器截图已实际查看，卡片显示 Priority 91、Dream Stream Relevance 96、MiniMax · Video、Mock Source · mock-v1。

## F. Tests

- Tests executed: python -m unittest discover -s tests -v。
- Passed: 2。
- Failed: 0。
- health test：验证 HTTP 200 和 status=ok。
- today basic test：独立内存 SQLite，验证 seed 幂等、DB 改动被 API 读取、分数及统计结构。
- npm run build：PASS，包含 tsc --noEmit 和 Vite build。
- 实际启动 FastAPI、Vite，并完成浏览器验证。

## G. Files

- backend/pyproject.toml
- backend/app/main.py
- backend/app/api/v1/health.py、today.py
- backend/app/db/database.py、models.py、seed.py
- backend/app/schemas/intelligence.py
- backend/tests/test_api.py
- frontend/package.json、package-lock.json、tsconfig.json、index.html
- frontend/src/api/intelligence.ts
- frontend/src/components/IntelligenceCard.tsx
- frontend/src/pages/Today.tsx、App.tsx、main.tsx、style.css
- README.md、docs/ARCHITECTURE.md、.gitignore、.env.example
- docs/DSIH-002-report.md

## H. Deviations

功能范围：None。

环境说明：Vite 首次在沙箱内启动时，依赖预构建遇到目录读取拒绝；按权限流程在沙箱外重启同一命令后成功，仅监听 127.0.0.1，未修改代码绕过限制。

非阻塞警告：Starlette TestClient 提示 httpx 支持已弃用，两个测试仍通过；npm 提示 esbuild 安装脚本尚未批准，实际构建和 Vite 运行均成功，无需追加操作。

Day 1 的 Today 返回本地已分析记录，不实现日期筛选；该最小语义在 ARCHITECTURE.md 明确记录。

## I. Scope Audit

- Real internet connector added? NO
- LLM added? NO
- TrendRadar modified? NO
- Scheduler added? NO
- Market added? NO
- Feishu added? NO
- MCP added? NO

未加入 Watchlist、Feedback、登录、Docker、部署、Agent、Skill、搜索、分页、复杂筛选、Dark Mode 或动画。

## J. Final

**PASS WITH WARNINGS**

第一张 Mock Intelligence Card 已在浏览器显示。
数据链路 SQLite → FastAPI → HTTP → React 经实际修改数据库验证。
基础测试 2/2 通过，TypeScript 检查及构建通过。
仅存在上述工具链非阻塞提示，无功能验收失败。
达到 Stop Rule 后停止开发，本地前后端保留运行供验收。

# DSIH-006｜GitHub Radar Connector v0.1

## A. Connector

- API: GitHub REST https://api.github.com，/repos/{owner}/{repo}/releases/latest。
- Auth mode: anonymous；支持可选环境变量 GITHUB_TOKEN，未输出或保存真实 Token。
- Repositories: Comfy-Org/ComfyUI、browser-use/browser-use、unclecode/crawl4ai，仅此三者。
- Latest 指最新正式 Release；仅 latest 返回 404 时用 /commits?per_page=1 获取默认分支最新 Commit。当前实际三者均采到 Release，fallback 仅在测试中验证。
- 正文最多保留 20000 字符，不生成摘要。作者、发布时间保留 API 值，无值保持 NULL。
- health 仅检查 API 可访问性。403/429 保守停止后续请求，不重试、不切换认证或代理；其它单源失败继续。
- 参考：[GitHub Release API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)、[Commit API](https://docs.github.com/en/rest/commits/commits#list-commits)。

## B. Collection Run 1

| Source | Received | Inserted | Skipped | Failed |
|---|---:|---:|---:|---:|
| ComfyUI | 1 | 1 | 0 | 0 |
| browser-use | 1 | 1 | 0 | 0 |
| Crawl4AI | 1 | 1 | 0 | 0 |
| Total | 3 | 3 | 0 | 0 |

## C. Collection Run 2

| Source | Received | Inserted | Skipped | Failed |
|---|---:|---:|---:|---:|
| ComfyUI | 1 | 0 | 1 | 0 |
| browser-use | 1 | 0 | 1 | 0 |
| Crawl4AI | 1 | 0 | 1 | 0 |
| Total | 3 | 0 | 3 | 0 |

两轮均退出码 0，未遇限流。

## D. Database

- sources before/after: 4 / 7。
- items before/after: 81 / 84；第二轮保持 84。
- analysis before/after: 4 / 4。
- 三个 GitHub sources 的 type=github、category=GITHUB、enabled=true。
- GitHub Item 对应 Analysis 数量为 0。

- ComfyUI: Comfy-Org/ComfyUI — v0.37.0；external_id=github:comfy-org/comfyui:release:392485194；https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.37.0
- browser-use: browser-use/browser-use — 0.13.10；external_id=github:browser-use/browser-use:release:382459855；https://github.com/browser-use/browser-use/releases/tag/0.13.10
- Crawl4AI: unclecode/crawl4ai — Release v0.9.4；external_id=github:unclecode/crawl4ai:release:394626896；https://github.com/unclecode/crawl4ai/releases/tag/v0.9.4

## E. Dedup

- Stable external_id: github:repo:release:id（无 ID 时 tag），commit 则 repo + SHA。
- Second run duplicates: 0，全部 3 条已存在记录 SKIP。
- SQLite 唯一 external_id 约束及 ON CONFLICT DO NOTHING。

## F. Failure Isolation

PASS：模拟中间仓库失败，首尾仓库各保存 1 条；再次保存跳过 2 条。每仓库独立事务。
限流例外：测试确认首次 429 后不再请求其它仓库，仅记录停止原因。

## G. Tests

- Backend: 33 passed / 0 failed，原有 27 项全部通过。
- 新增 6 项覆盖 Release normalize、Commit fallback、稳定 ID、去重与错误隔离、可选 Token、限流停止。
- TypeScript: tsc --noEmit PASS。
- Frontend build: Vite build PASS。
- Today HTTP 200，仍返回原 4 张 Intelligence；raw_items 按数据库自动变为 84。
- 既有 TestClient/httpx 弃用提示仍存在。

## H. Scope Audit

- LLM called? NO
- Analyzer modified? NO
- Priority modified? NO
- Today modified? NO
- NewsNow modified? NO
- RSS added? NO
- Scheduler added? NO
- Feishu added? NO
- MCP added? NO
- GitHub deep audit added? NO

既有 backend/app、frontend/src、config 文件哈希未变。新增 github.py、collect_github.py、test_github.py 及报告证据；README 增加手动命令说明。无新依赖、无克隆、无提交或推送。

## I. Deviations

None。403 与 429 均保守停止，不尝试绕过；其它仓库级失败隔离。

## J. Final

**PASS WITH WARNINGS**

三个 GitHub Source 和三条真实 Release Raw Item 已入库，第二轮全部去重。
Analysis 保持 4，未调用 Analyzer；33 项测试及前端检查构建通过。
唯一警告为已有测试依赖弃用提示。已按 Stop Rule 停止。

证据：docs/evidence/dsih-006-run1.log、dsih-006-run2.log、dsih-006-tests.log、dsih-006-before.json、dsih-006-after.json。

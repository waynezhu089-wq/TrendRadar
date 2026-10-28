# Qwen image vision — 2026-10-23

## Outcome

- CODE / MODEL-FREE TESTS: PASS.
- REAL VISION ACCEPTANCE: BLOCKED at public preview retrieval, before any model call.
- Qwen requests: **0**; Qwen token usage: not applicable.
- Human visual/UX acceptance: NOT_TESTED.

## Authorized binding

User explicitly allowed DSIH to reference `VNEXT_QWEN_API_KEY`. The exact vision binding was read from vNext configuration without changing that project:

- Base URL: `https://llm-64taelt1l1s3o096.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
- Model: `qwen3.8-flash`
- Local `data/vision-provider.json` contains endpoint, model and environment-variable **name only**. It is ignored by Git. No key value was displayed or copied into a file.
- `GET /api/v1/image-vision/status`: configured=true. This verifies configuration availability, not provider connectivity.
- Existing `DSIH_LLM_*` text provider remains unchanged.

## Implemented flow

Explicit **看图筛选与归纳** → up to 12 saved public previews → actual Base64 image bytes + topics/purpose → Qwen JSON response → exact image/categorization citation validation → independent `research_image_visual_reports` record. Every preview is bounded to 2 MB, total 8 MB; redirects retain public-host checks. Images stay in memory, without modifying watermarks or downloading originals. No automatic model retries or metadata fallback labelled as vision.

Saved results group readable MATCH/PARTIAL images by visual category. Weak matches and unassessed candidates are collapsed. Each useful category initially shows at most two previews. Per-image visible-content details and original attribution remain available. Ordinary result/status GETs never call models; explicit unchanged-input analysis reuses the saved report. A failed provider response or invalid citation preserves previous results.

## Checks actually executed

- Backend full suite: **242 passed**, 0 failed; includes 11 new image-vision tests. A later targeted rerun of all 11 passed after adding the empty-run boundary assertion.
- Frontend full suite: **34 passed**, 0 failed; includes two new visual-report/explicit-request tests. A final image/research subset rerun: 14 passed.
- TypeScript and Vite build: PASS, including final UI state-isolation adjustment.
- Tests verify actual multimodal wire payload, explicit key reference, no implicit vNext key reuse, preview type/signature/size/private redirects, separate persistence, cache reuse, invalid/missing/duplicate citations, partial preview failure, unreadable results, missing configuration, no-image/running runs, safe API errors and read-only GET behavior.
- Existing Starlette test-client deprecation warning remains; no dependency upgrades were performed.
- Live health API: `{"status":"ok"}`.
- Live Research UI displays the new explicit button. Browser's stale zero-width tab was replaced; temporary viewport override was cleared. Real grouped visual results could not be validated because no model response was obtained.

## Real request and blocker

Target: existing example plan **5**, saved run **19**, six FilmGrab previews from Blade Runner 2049 / Chungking Express. No new collection was run.

Two entry requests completed (the browser request and the later direct API validation), both with `HTTP 502` at preview retrieval. The direct validation returned `VISION_PREVIEWS_UNAVAILABLE`. The processor fails before invoking the model when no preview can be read; visual report row count remains **0**, and model calls remain **0**. Access logs are completion records; an absent log line while a request is pending is not proof that the request never arrived.

Bounded diagnostics of existing public images:

- Public-address validation: PASS.
- FilmGrab thumbnail, default HTTPX: TLS `UNEXPECTED_EOF_WHILE_READING` / ConnectError.
- Same image, standard library: URLError with SSLEOFError (errno 8).
- Same image, direct HTTPX: ConnectTimeout.
- Same image via the currently configured HTTP proxy: ConnectError.
- Existing Openverse preview: ConnectError.
- Windows configured proxy `127.0.0.1:7897` is listening. No proxy credentials were present; no proxy settings were changed.

Evidence establishes a backend image-fetch network/TLS blocker. It does **not** establish that Qwen is unavailable, that the API key is invalid, or that the model lacks vision. After restoring backend HTTPS access to public previews, the same page/button can complete real vision acceptance. No certificate validation bypass, alternate-site expansion or repeated model attempts were used.

## Preservation

Pre-change backup: `data/dsih.pre-image-vision-20261023T080557.bak`.

Read-only row comparison confirmed all previous rows unchanged in research_plans (5), research_images (12), research_run_images (18), research_image_summaries (4), global analysis (310), notification_deliveries (17), post_notifications (1). Existing background collection may add raw items/runs independently; it was not stopped.

Only the verified Web API was reloaded. Final `scheduler_status.ps1` confirms the original single Scheduler PID **63332**, task **Running**. Final counts remain visual reports 0, global analysis 310, notification_deliveries 17, post_notifications 1. No Scheduler/Watchdog restart, one-shot collection job, Feishu delivery, vNext mutation, commit or branch creation was performed.

Actual entry/layout screenshot (not a successful visual-analysis result): `qwen-image-vision-entry-20261023.jpg`.

DeepSeek MCP delegation: not used. Real text-model calls: 0. Real Qwen calls: 0.

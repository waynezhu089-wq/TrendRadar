# Dream Intelligence

可配置来源接口：设置 → **来源接口**。通过 GitHub 项目搜索、JSON API 或公共 RSS 模板添加本机来源，关注方案和方案助手共享来源目录。支持检索词、排序、条数与字段映射，保存配置不会执行采集。详见 [来源接口配置与扩展说明](docs/SOURCE_CONNECTIONS.md)。

AI 制作商单：主导航「AI 商单」(`/commissions`)，手动读取 AigcSDM、漫剧工场、塔猴及猪八戒公开需求，按视频广告、漫剧动画、图片视觉分区，可筛选来源，单列大陆归属待核实与过期记录。猪八戒目前限于公开详情与相似需求，未实现全站搜索。参见 [范围与限制](docs/AI_COMMISSIONS.md) 和 [来源扩展验证](docs/evidence/ai-commission-sources-validation-20261024.md)。

An independent, lightweight future Intelligence Hub for Dream Stream.
Current status: local development with collection, purpose-based research, analyzed intelligence and a daily topic homepage. Raw items remain separate from Intelligence. Not Production.

## Backend (PowerShell, Python 3.12+)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Startup creates tables in `data/dsih.db` without seeding. To create the development Mock Card, explicitly run: `.\.venv\Scripts\python.exe -m app.db.seed`.
Health: http://127.0.0.1:8000/api/v1/health
Today: http://127.0.0.1:8000/api/v1/today

## Frontend (second terminal, Node 22.12+)

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173 for **Today**, the default daily topic homepage (`/today` remains an alias). Navigation is Today / Research / Market / Settings. Settings (`/settings`) contains topic plans, source websites, purpose and Watchlist configuration; the old `/watchlist` address opens the corresponding Settings tab.

Today uses a spacious two-column topic layout, switching to one column below 1000px. Each topic initially shows three headlines; detailed research is linked separately and additional analysis advice is collapsed. Topics and their headlines are ordered by original publication time, newest first, with unknown dates last. **Today** includes information collected or analyzed during the current calendar day in Asia/Shanghai; **近 7 天** includes today and the previous six days. Each item's `included_at` is the later of its capture and analysis times. Research uses its server-recorded summary analysis time (falling back to the historical run completion time). Older publication dates remain visible with a **较早发布 · 本期收录/分析** label; NULL publication dates remain NULL and are labelled unknown. Future publication dates, mock items and raw unanalyzed items are excluded. Empty configured topics remain visible.

`GET /api/v1/daily-brief?days=1|7` is read-only. Research material is included only when cited by a saved, successful per-run analysis; global analyzed content still uses the existing relevance threshold. Cross-date Research overviews are not reused as daily summaries. The explicit analysis button calls `POST /api/v1/daily-brief/analyze?days=1|7`, using the configured `DSIH_LLM_*` provider. It synthesizes the selected period's evidence, at most 12 items per topic and 12 topics, validating exact topic/item citations. Reports are cached in ignored `data/daily-reports/`, keyed by rule version, local date, period, purpose and evidence content. Refreshing a page never invokes the model; unchanged reports reuse the cache. The model receives the distinction between original publication time and our inclusion time, and must not recast old or undated items as newly published news.

When candidates are available, **分析并更新简报** adds `include_pending=true`. This explicitly runs the existing bounded candidate analyzer first: at most six unanalyzed items from the recent-seven-day queue, preserving existing source quotas, Watchlist matches and topic gates (including at most two NewsNow items). Successful validated item analyses are saved to global `analysis`; raw items remain unchanged, and MediaCrawler/custom-web items stay outside this global analyzer. Provider failure stops further calls and returns a visible notice; partial successes remain saved. The daily summary then uses the updated evidence. Failed summaries preserve successfully saved analyses. Repeated processing skips already analyzed items, but a further explicit click can process the next eligible batch. Merely refreshing never processes candidates. There are no crawls, scheduler changes or notification sends in this endpoint. The old `/api/v1/today` endpoint remains unchanged for existing consumers including Daily Brief notifications.

React fetches the local FastAPI service directly on port 8000. CORS allows only the local Vite origins on port 5173.

## Conversation-assisted plan creation

Open `http://127.0.0.1:5173/settings?assistant=1`, or click **让助手建立方案** from Research. Describe a direction and purpose in ordinary language. The assistant uses the existing configured model to propose a name, topics, sources and analysis purpose. It asks up to three short questions when information is insufficient, and supports further conversational refinements or manual edits. The draft preview shows source capabilities and limits. The existing selected-plan detail is hidden while the assistant is open to keep the workspace uncluttered.

`POST /api/v1/research-plan-assistant/draft` accepts at most 12 user/assistant messages, 12,000 characters total, and an optional current draft. It does not write to the database, browse sites, log in, run a collector or send notifications. Schema/source validation allows at most one formatting repair; a provider error is not retried. Model output cannot execute tools. Weibo hotlists and Bilibili keyword search are known sources; Zhihu is explicitly labelled limited and is suggested only when requested. Other public URLs must have been supplied by the user/current edited draft, never invented by the model, and are labelled as unverified static HTML/RSS attempts. No new website integration is installed by this assistant.

**创建这个方案** explicitly calls `POST /api/v1/research-plan-assistant/create` with reviewed fields and `confirmed: true`. It reuses the existing ResearchPlan schema, creates a plan without collecting anything, and reuses an exactly identical active plan on repeated confirmations in this single-process local API. Different names, topics or purposes can still create separate plans. Creation and model failures preserve the current draft on the page. The original user request is retained alongside a bounded recent conversation so short approvals keep their context. Optional unavailable websites are listed in `deferred_sources` and do not block a draft once supplementary sources have been accepted; an explicitly exclusive unsupported-source requirement still needs clarification. The assistant offers **先生成可用来源草案** when unavailable sources are blocking progress. Deferred sites are not included in the created plan's active websites.

Conversation and unfinished draft state are cached in the current browser tab's `sessionStorage`, so refreshing or collapsing the assistant can restore them. **重新开始** and successful creation clear this cache. A pending new reply never restores an earlier draft as ready to create. No conversation is persisted to the backend database; only explicitly confirmed plans become ResearchPlan records. After creation, open the selected plan's Research workspace to run it manually. No scheduler or notification behavior is changed.

## Purpose-based research plans

### Tibo Chinese updates and Codex reset alerts

Open `http://127.0.0.1:5173/research?subscription=tibo` (Research → 自动订阅 → Tibo · Codex 动态). The subscription reads recent public posts by `@thsottiaux` through a separately logged-in, headless Chrome profile, and supplements reset signals with the documented public Codex Resets API. Login is performed personally in an ordinary dedicated Chrome window; its Git-ignored profile is `data/x-browser-profile/`. Close that login window before collection. `python -m app.commands.x_login` can reopen it.

The local configuration `data/tibo-monitor.json` enables the subscription in the existing Scheduler. The default interval is **two hours**. Change it in **设置 → 自动订阅** (`http://127.0.0.1:5173/settings?tab=subscriptions`): 30 minutes, 1 / 2 / 4 / 12 / 24 hours. Saving only writes the non-secret preference; a lightweight Scheduler control job reads it every 30 seconds and reschedules Tibo without restarting the service or executing collection. The next check is one full interval after application (also after scheduler launch). The settings page distinguishes saved/pending/applied values and shows the next check in Beijing time; a stale Scheduler heartbeat is labelled as waiting for the service. GET and saving settings never call X, the translation model or Feishu. Browser access expiry/403/429 is recorded without challenge workarounds; a failed source does not discard another successful source. The PC must remain running and online with a valid X session. The configured interval is not an assurance of instantaneous source updates. Only the recent rendered timeline is read (up to twelve target-author posts); this is not an exhaustive archive or media/transcript downloader.

The initial poll establishes a baseline. Afterwards, new posts are translated into Chinese before any alert. At most two pending posts are translated per poll; ordinary updates remain in the platform. The classifier distinguishes quota reset announcements, explicit completion, unclear content and non-quota resets. “That's a reset” alone is treated as an announcement, not proof that accounts were reset. Community observations are labeled as community reports, and their observation timestamps are not presented as original post publication times. Predictions, probability estimates and inferred reset deadlines are not ingested as facts. English originals, source links and Chinese translations remain available.

Quota notifications use the configured `DSIH_FEISHU_WEBHOOK_URL`, never copied into database/logs or browser code. Each canonical post plus announcement/completion phase has one delivery key, separate from the daily brief guard. Known provider rejection permits at most three attempts across polls; a network timeout or uncertain acknowledgement is recorded UNKNOWN and not automatically resent. The original Dream Intelligence title remains in cards for the existing bot keyword policy. The original source and Chinese translation are attached; lengthy translations are excerpted in the card while the complete version remains in the platform.

Dedicated `monitored_posts`, `tibo_monitor_state` and `post_notifications` tables preserve the boundary between translated updates and Intelligence analysis. This does not insert fake global Analysis or change priority scores. GET/status and the page's **刷新列表** only read saved records. A real Chinese announcement card was delivered and accepted by the user on 2026-10-23; see `docs/evidence/tibo-monitor-validation-20261023.md`. The prior Daily Brief, Market, collection schedules and Watchdog rules are retained; interval tasks begin counting again when the resident scheduler reloads.

### YouTube video inspiration

Research plans now also support `collection_type: videos` with the fixed source `https://www.youtube.com/`. The public YouTube Data API searches up to eight topics, ten candidates per query, within the last 30 days. English phrases are separated from trailing Chinese glosses; requests alternate relevance/date order without extra pagination. Round-robin selection keeps at most twelve videos and two per stable channel ID (display-name fallback). Actual query traces and candidate/selected channel counts are stored in `video_search_reports` and visible in the page's collapsed search explanation. Historical runs without a report remain labelled unrecorded. IDs deduplicate videos globally; per-plan run links preserve metadata-based Chinese organization and plan-scoped favorites. Separate video tables keep references out of global `items`, Intelligence `analysis` and Today news. No video file download, full-video understanding or Feishu send is added. Source-diversity validation: `docs/evidence/youtube-diversity-validation-20261024.md`.

Set `DSIH_YOUTUBE_API_KEY` in the backend environment, with YouTube Data API v3 enabled. The key is sent only as a request header, never a URL parameter. Setup and user instructions: [docs/YOUTUBE_SETUP.md](docs/YOUTUBE_SETUP.md).

Plans are created in Settings or through the assistant. Their own schedule controls support 120/360/720/1440-minute intervals and default to disabled. The updated resident Scheduler checks due video plans every five minutes, at most three per tick, with a persistent 15-minute per-plan claim to prevent overlapping manual/scheduled runs. A separate heartbeat reports whether the worker has loaded the feature and key. Schedule GET/save never runs business jobs; old Scheduler instances must load the new code before automatic collection can work. Existing collection, Market, Tibo and Daily Brief triggers retain their settings.

Real manual collection was validated on 2026-10-24: run 21 received and inserted 12 unique public videos; all 12 have Chinese metadata organization. Browser favorites, loaded previews and one 8-second embedded playback were verified. The user chose a six-hour interval; plan 6 is now enabled, the existing Scheduler was normally reloaded and its heartbeat confirms key/worker readiness. First planned run: 2026-10-24 21:59 Asia/Shanghai; that future execution is not yet observed. Evidence: `docs/evidence/youtube-live-validation-20261024.md`; earlier implementation checks: `docs/evidence/youtube-validation-20261024.md`.

### Image reference collection

**看图筛选与归纳** is a separate, explicitly invoked Qwen vision step on saved image results. It sends the plan's topics/purpose and up to 12 public preview images as actual Base64 image inputs, never original files or browser credentials. Each preview is bounded to 2 MB, with an 8 MB total input budget. Failed previews remain unassessed. The result records visible subjects, scene, light, color, composition, purpose fit, uncertainty and category-level synthesis. It cannot infer motion from stills or establish usage rights. Watermarks are preserved.

Configure this separately from the existing text provider using `DSIH_VISION_BASE_URL`, `DSIH_VISION_MODEL` and `DSIH_VISION_API_KEY_ENV` (the **name** of an authorized environment variable holding the key). Alternatively use the ignored local `data/vision-provider.json` with `base_url`, `model`, `api_key_env`; never put the key value in that file. No implicit reuse of another project's credentials occurs. The local authorized binding uses `qwen3.8-flash`; text analysis retains `DSIH_LLM_*`.

`POST /api/v1/research-plans/{plan_id}/runs/{run_id}/vision` stores validated observations in the additive `research_image_visual_reports` table, apart from metadata recommendations and global Intelligence. Read-only status and result GETs never call models. Explicit reanalysis with unchanged purpose and preview hashes reuses the saved report. Failed provider calls or invalid citations preserve the previous report, without automatic retries. The page groups useful references with initially compact previews and collapses weak or unassessed candidates. New acceptance evidence: `docs/evidence/qwen-image-vision-validation-20261023.md`.

The plan assistant supports video-creation inspiration with `collection_type: images` alongside the default `research` mode. Say what video you are making and what references you need, then confirm the draft and click **现在运行** in Research. **设置 → 手动填写关注方案 → 视频灵感与图片参考** offers an explicit source selector: **FilmGrab** (`https://film-grab.com/`) for movie-frame reference, **Openverse** (`https://openverse.org/`) for open-license images, or both. Existing image plans keep their saved sources. **调整参考来源** updates only source selection, without collection/model calls; historical runs and the original purpose remain unchanged. Public previews may carry watermarks, which are retained. ArtStation returned HTTP 403 and Huaban returned an abnormal-access block during validation; neither is presented as an integrated source. Audio and book-file collection are not implemented.

An image run uses at most two model calls: source-specific query planning, then metadata-based suggestions. Each selected source gets at most two queries. Openverse uses short visual keywords (six results per query) and may try at most two shorter English phrases after successful empty responses, with four API requests maximum. FilmGrab searches movie titles, directors or cinematographers; it cannot semantically search arbitrary frame descriptions. Each FilmGrab query reads at most two real search-result galleries and samples three dispersed previews per film. Each run is bounded to two search pages and four galleries, with per-run gallery caching and at most three same-site redirect attempts per page. Across sources, at most twelve unique image records are retained; two-source plans reserve six places for each source. A timeout, rejection or rate limit stops requests to that source, preserving successful results from other sources. Actual search terms and usable candidate counts are recorded even when empty. Factual diagnostics are labelled as search records, not agent analysis. Historical empty runs cannot retrospectively reveal unrecorded queries.

The model ranks potential references using titles, tags, film/creator credits, dimensions and rights metadata. It may recommend zero images. It does **not** inspect image pixels, judge individual-frame composition or analyze video rhythm. FilmGrab recommendations identify films/frames worth examining, not visually verified matching shots. Previews use spacious two-column cards (one on narrow screens), with explicit source badges, credits, original links and purpose suggestions. FilmGrab rights notices are preserved, unknown rights are not converted into an open license, and there is no in-platform original download for FilmGrab references. FilmGrab identities are stable across cache-query changes; recollection refreshes supplied credits/rights while retaining favorites. **本方案收藏** retains favorites across older runs. **分析已有结果** uses saved metadata without another search.

Original image files are fetched only by an explicit download action, capped at 20MB, and restricted to JPEG/PNG/WebP/GIF signatures and content types. Public URL/DNS checks apply before every redirect. Files are stored in Git-ignored `data/research-assets/` with a SHA256 digest; repeat downloads reuse the local file. Original hosts can refuse requests, and an unverified/unsupported license or file format is reported to the user. Source/author/license metadata remains attached to the saved image record. GET/history/favorite actions do not call image search, model or download services.

Images have separate `research_images`, `research_run_images` and `research_image_summaries` records. They are not text `items` or global Intelligence `analysis`; image plans are excluded from daily news. The additive plan-type migration backs up the existing database and preserves legacy plans as `research`. It does not add scheduled jobs or notifications.

Checks include normalization, source isolation, source-setting validation, stable deduplication, credit preservation, reanalysis, cross-run favorites, download restrictions and legacy upgrades. Frontend checks include `node --test scripts/test-images.mjs`. `backend/validate_image_local.py` remains the isolated Openverse acceptance helper. Original evidence is in `docs/evidence/image-reference-validation-20261023.md`; the FilmGrab browser acceptance uses the explicitly labelled live example **电影画面灵感 · 城市氛围示例** (`/research?plan=5`).

The Research workspace has a plan sidebar and separate information-type regions: 模型与版本, 工具与插件, 工作流与应用, 教程与方法, 行业动态 and 其他. The model synthesizes each non-empty region with a summary, key points, a suggested action and cited item IDs. Every analyzed item must belong to exactly one region; missing, duplicate or invented citations fail validation. Within each region, cards show publication time (Asia/Shanghai) newest first, with unknown dates last. Regions are ordered by their newest item. Capture time is never substituted for publication time. The API returns UTC-offset publication timestamps, and the latest 12 dated/undated items are selected for analysis in that order.

**分析已有结果** rebuilds classification and summaries from saved evidence without fetching websites. Old results without regional analysis are labeled pending classification. Items outside the 12-item analysis bound are displayed separately without invented summaries. A failed reanalysis preserves the previous result. The endpoint is `POST /api/v1/research-plans/{plan_id}/runs/{run_id}/analyze`. Frontend semantic rendering/sorting checks: `node --test scripts/test-research-results.mjs` from `frontend`.

Open http://127.0.0.1:5173/settings to create a plan with a name, up to eight free-text topics, up to five public website URLs, and one purpose. In http://127.0.0.1:5173/research click **现在运行** to collect and summarize that plan. This first version runs only on demand; it does not register a scheduler job or send notifications.

The general collector accepts public HTTP(S) RSS/Atom feeds and ordinary HTML pages on ports 80/443. It does not log in, execute browser scripts, bypass paywalls, or promise exhaustive website coverage. It reads at most three entries or articles per site, caps each response at 1 MB, and filters by literal topic text in the title/body; synonyms may be missed. Private/local IP addresses and redirects to them are rejected. A failed site does not stop the other sites. For a service exposed to untrusted users, URL fetching would need stronger network isolation and DNS pinning before deployment.

Zhihu is the first site-specific browser source. Install the backend requirements, then from `backend` run `.\.venv\Scripts\python.exe -m app.commands.zhihu_login`. A separate ordinary Microsoft Edge window opens; sign in there yourself and close it before running a plan. The profile is kept only in `data/zhihu-browser-profile/` and ignored by Git. Never copy a profile, password, or cookie from the ChatGPT browser. Add `https://www.zhihu.com/` as a plan website and enter up to eight topics. A manual plan run searches each topic, opens at most one original answer/article per topic (eight per run), and stores the destination title, body excerpt and canonical URL as raw items. Search-card snippets and Zhihu-generated answer panels are excluded. Login expiry is reported as `ZhihuLoginRequired`; HTTP 403 is reported as `ZhihuAccessBlocked` and is not retried or bypassed. This first source does not handle CAPTCHA, paywalls, other logged-in sites, or automated scheduling. Close the login window before starting a collection because the profile cannot be opened twice.

Matching pages are saved as raw `items`, deduplicated by normalized URL, and linked to a `research_run`. The plan's purpose and at most 12 matching items are sent to the configured `DSIH_LLM_*` provider for a cited summary. If the provider is unavailable or its citations fail validation, the raw items remain and the run reports `SUMMARY_FAILED`. The per-run summary is stored separately in `research_runs`; it does not create global `analysis` rows or alter scores. The daily topic view can read its dated, cited items without changing that boundary. Both the scheduled global candidate queue and the older manual `analyze_pending` command exclude `custom_web` and `mediacrawler` items. This feature requires the existing LLM environment configuration to produce a summary. The Research page shows the latest result and its source links.

### Douban book/movie reviews

Douban has its own Chrome session in `data/douban-browser-profile/` (Git-ignored). In a Douban plan, click **登录豆瓣**, sign in personally in that dedicated window, then close it before **现在运行**. Alternatively, from `backend` run `.\.venv\Scripts\python.exe -m app.commands.douban_login`. DSIH does not request passwords or export browser cookies. This is separate from the daily Chrome/ChatGPT browser session.

Use `https://movie.douban.com/` for movie search, `https://book.douban.com/` for books, or `https://www.douban.com/` for both. Topics should be concrete work titles/keywords. A user-supplied `https://movie.douban.com/subject/<id>/` or book subject URL selects that specific work. The plan assistant can suggest the supported homepages but cannot invent subject IDs. Groups, diaries and unrestricted whole-site collection are not supported.

Per configured Douban entry, the collector considers the first two topics, chooses at most two subjects from the first search results and reads up to three short comments plus one long-review original page per work. Long-review body excerpts are capped at 6000 characters; the existing purpose summary receives at most 12 items, first 1200 characters each. Search ranking is not an exact-title guarantee, and hot comments can be old. The original comment publication times are converted from Asia/Shanghai to UTC; capture time is not substituted. The model distinguishes user opinions from facts and can use **图书与阅读 / 电影与影评** regions.

The independent profile lock prevents concurrent DSIH collectors; close the login window to release Chrome's own profile lock. Collection stops further requests on a challenge, HTTP 403/429 or session expiry. Successful comments survive a later page failure. No CAPTCHA workaround, proxy, account writes, scheduler job or notification is added. Stable comment/review IDs deduplicate raw `custom_web` items, and summaries remain in `research_runs`, outside global `analysis`.

Live validation on 2026-10-23 verified persisted login, movie/book search, six short comments and two original long-review excerpts. The full pipeline and one real provider summary ran in a separate `data/douban-validation-*.db`; a replay of the same captured evidence and saved summary inserted zero more rows without further site/model calls. The isolated database contains two sources, eight items and zero global analyses. This is not a user UI acceptance test. `backend/validate_douban_local.py` is an explicit manual real-network/model acceptance helper, never run by startup or tests. The lab-only `@marvae24/douban-cli@0.6.0` was evaluated separately; its long-review listing returns abstracts, so production uses visible original pages through the existing Playwright dependency and does not depend on that CLI.

### Weibo hot-topic research

A Weibo homepage, hotlist URL or `/newlogin` redirect URL in a Research plan is routed to the existing NewsNow **Weibo-only** endpoint. DSIH does not open the login page or use browser credentials for this route. It considers at most 30 hotlist titles, saves normalized public candidates using existing `newsnow:` IDs and the existing Weibo source, then asks the configured model to select at most 12 candidates by the plan's topic meanings and purpose. Broad categories such as 社会话题 / 男女情感 / 教育话题 are treated semantically, rather than requiring those exact words in every title. Unsupported Weibo article/profile paths continue through the ordinary webpage route and are not promised as authenticated access.

The selected candidates become per-run research evidence and receive a cited summary, with social/lifestyle categories **社会与公共议题 / 情感与生活 / 教育与成长** available alongside the existing technical categories. This does not create global Analysis rows. Source evidence is limited to hotlist titles and links: original posts, comments, event details and publication times have not been verified. The summary is for research/creative leads, not a factual investigation. No unrelated platform is fetched by this adapter.

Provider/network failure is not retried automatically; malformed selection JSON/references get at most one repair against the same candidates. Public candidates are saved before model selection so they survive a model failure; a failed selection is shown as a failure rather than a successful empty search. Repeated runs reuse existing item identities. The displayed inserted count covers newly saved raw hotlist candidates, while matched counts the subset selected for this research run.

### Bilibili collection through an independent MediaCrawler

MediaCrawler runs as a separate local tool and is **not** bundled with DSIH. Set `DSIH_MEDIACRAWLER_DIR` to its installation folder, or keep the validated installation at the workspace's `.lab-tools/MediaCrawler-main`. Its own `.venv/Scripts/python.exe` and dedicated Bilibili browser profile must already be ready. The user signs in personally; DSIH never imports passwords or cookies. Create a plan with `https://www.bilibili.com/` (a bare domain is also accepted), topics and purpose, then click **现在运行**. The adapter starts a separate process, searches each topic, reads at most three details per topic, and returns title/description metadata. It disables comments, media downloads, proxies and interactive login; expired login is reported to the page. A browser lock prevents two DSIH collections from sharing the profile, and a 240-second timeout terminates only the launched process tree. The external tool receives selected Windows runtime variables, not DSIH model or notification credentials. Its public output remains in its `dsih-output/<run-id>/` directory.

The existing manual import command remains available for a previously collected `search_contents_*.jsonl` file:

```powershell
.\.venv\Scripts\python.exe -m app.commands.import_mediacrawler --plan-id 1 --input 'C:\path\to\search_contents_YYYY-MM-DD.jsonl'
```

Replace the plan ID and input path with your own values. Input is limited to 100 rows / 2 MB, Bilibili video URLs, and search keywords matching the plan topics. Plausible topic matches become raw items, deduplicated by normalized URL, and a purpose-specific summary cites stored item IDs. Summary evidence includes publication dates when available, but consists only of titles and descriptions; videos have not been watched and full-site/latest coverage is not guaranteed. At most 12 matched items are summarized. Repeating a run can reuse existing raw items without duplicating them. Raw items survive summary failures. `mediacrawler` items remain outside global Intelligence analysis. No research scheduler or notification job is registered. MediaCrawler's own license applies separately; its source is not copied into DSIH.

Malformed summary JSON/schema/citations receive at most one reconstruction request against the same evidence. Regional analysis defaults to a 90-second provider timeout; an explicit `DSIH_LLM_TIMEOUT` takes precedence. This does not change the global single-item analyzer's timeout. Provider/network failures are not retried automatically; raw items remain available if summarization fails. While one manual research request is active, the local API rejects a second with HTTP 409. A browser refresh during a run does not cancel the server-side work; wait for completion before starting another run.

## Checks

```powershell
# from backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
# from frontend
npm run build
node --test scripts/test-daily.mjs scripts/test-research-results.mjs scripts/test-plan-assistant.mjs
```

Backend tests use an isolated in-memory SQLite database. No GitHub remote or cloud services are required.

## Manual NewsNow collection

From `backend`, run twice to check deduplication:

```powershell
# Optional: replace with your own NewsNow /api/s endpoint.
$env:NEWSNOW_API_URL="https://newsnow.busiyi.world/api/s"
.\.venv\Scripts\python.exe -m app.commands.collect_newsnow
```

Only weibo, zhihu and bilibili-hot-search are fetched. Each source is isolated; failed sources are reported and successful ones still commit. Exit code 1 indicates any failed source. `NewsNowConnector().health()` probes basic availability through weibo; it does not certify every source.

Normalization trims titles/URLs and removes URL fragments. The ID is SHA256 of source + normalized URL, or source + title when URL is absent. Query parameters are preserved; no complex deduplication. Missing author/published_at remain NULL and content is empty. Collection inserts only sources/items, never analysis. Today/UI remain unchanged.

The first startup or collection against a Day 1 database backs up `data/dsih.db` to a timestamped `.bak`, then relaxes author/published_at nullability while preserving existing IDs and analysis. No migration framework is installed. Existing mock data is retained; startup never regenerates it.

## Analyze pending raw items

Configure `DSIH_LLM_BASE_URL`, `DSIH_LLM_API_KEY`, `DSIH_LLM_MODEL` in the process environment. Base URL is an OpenAI-compatible API root (including `/v1` where required); the client appends `/chat/completions`. Optional `DSIH_LLM_TIMEOUT` defaults to 30 seconds. No `.env` auto-loading or SDK is required. Do not put credentials in source, logs or the database.

```powershell
# from backend, after configuring a real provider in your shell
.\.venv\Scripts\python.exe -m app.commands.analyze_pending --limit 5
```

Default limit 5, allowed range 1–20. Missing provider configuration exits 2 with `REAL_LLM_NOT_VALIDATED` and does not analyze or write anything. There is no production Fake fallback. Unit tests use a Fake only in isolated in-memory SQLite.

Only non-mock, non-`custom_web`, non-`mediacrawler` items without analysis are selected, in ID order. Each successful analysis commits independently; invalid JSON, invalid scores or provider failures fail only that item. No automatic retry. Repeating the command selects the next pending records; already analyzed IDs are never sent again. A direct attempt on an analyzed ID returns SKIP without a provider call. Existing unique item_id remains the final duplicate write constraint. Run commands serially; concurrent token-deduplication is outside v0.1.

Model scores are strictly integer 0–100. Category/action enums are validated. Model priority is discarded. `v0.1-no-hotness` computes 40% average relevance + 20% importance + 15% actionability + 10% novelty + 15% credibility, rounded half up. Analysis uses `dsih-analyzer-v0.1`; raw fields are never edited. Profile: `config/intelligence_profile.md`.

This task does not change Today. Real-provider integration has not been validated in this environment. The existing Today response requires a non-null published_at, while raw NewsNow records may have NULL; exposing real analyses through Today needs a later explicit API/UI integration task. Do not infer that real analyzed records are ready for Today from the isolated analyzer tests.

## GitHub raw collection

From `backend`: `.\.venv\Scripts\python.exe -m app.commands.collect_github`.
Optional `GITHUB_TOKEN` is read only from the environment; public anonymous requests are supported.
Only Comfy-Org/ComfyUI, browser-use/browser-use and unclecode/crawl4ai are collected.
One latest stable Release per repository; only a missing latest Release falls back to one default-branch commit.
Second runs skip stable external IDs. No analysis is created. HTTP 403/429 stops further requests, without retry.



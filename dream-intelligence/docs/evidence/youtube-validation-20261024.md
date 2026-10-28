# YouTube 视频灵感 — 2026-10-24

## Status

- Implementation and model-free verification: PASS.
- Live browser creation, save/read and missing-key guard: PASS.
- Real YouTube search, real Chinese organization, live video playback and scheduled collection: NOT_TESTED / awaiting `DSIH_YOUTUBE_API_KEY`.
- User UX acceptance: pending.
- Actual YouTube searches, model calls, video file downloads and Feishu sends for this task: **0**.

## Delivered scope

YouTube Data API connector, normalized stable video IDs, public previews, original links, metadata-only Chinese title/description organization with exact ID/category validation, compact regional video cards ordered by original publication time, on-demand YouTube embedded preview, and plan-scoped persistent favorites. Results use independent `research_videos` / `research_run_videos` / `video_favorites` tables. They do not masquerade as global Intelligence or enter Today.

Video plans reuse Settings/Research and the existing plan assistant. No new top-level page was added. Each plan can save a disabled-by-default automatic schedule at 120/360/720/1440 minutes in `video_schedules`. The updated Scheduler polls due plans every five minutes, at most three plans per tick, and writes a non-secret readiness heartbeat every thirty seconds. A persisted atomic 15-minute lease protects manual/scheduled overlap; failures advance the next schedule rather than immediately retrying. Existing business trigger settings are retained.

Search is bounded to eight topics, three candidates/topic, last thirty days. Global video identity deduplicates across runs/plans, while Chinese organization and favorites remain scoped to the plan. Already organized videos are reused on repeat receipt; untranslated candidates remain explicitly pending. Title/description classification does not establish actual plot, animal behavior, event authenticity or rights. No full-video vision was added.

Keys remain in environment, are sent to Google's fixed HTTPS API endpoint via header, and are not written into URLs or frontend files. Permission/quota failures stop remaining topic requests. Schedule save/GET never triggers collection. Missing configuration stops before creating a run or sending requests.

## Verification

- Final complete backend regression: **259 passed**, 0 failed, including 17 YouTube tests.
- Complete frontend suite: **38 passed**.
- TypeScript/Vite build: PASS, including final video UI.
- New tests cover normalization, malformed IDs, secret-header transport, bounds, duplicate API results, permission isolation, missing key, stable insertion, saved Chinese reuse, failed translation retaining raw entries, exact IDs/categories, source failure vs no results, lease exclusion, schedule-only saves/GETs, favorites, atomic due selection, one execution per due schedule, plan isolation and assistant source/type validation.
- Existing Scheduler tests now include the two new non-overlapping video jobs while checking all original trigger configurations. A former fixed-date rescheduling test now freezes APScheduler's clock rather than depending on the real day being 2026-10-23.
- Browser: created real user-requested plan **6**, **视频灵感 · 趣味与互助**, with four directions: `funny animals`, `animals helping each other`, `funny human moments`, `acts of kindness`. Saved disabled daily schedule. Tested a manual click without a key: displayed the explicit missing-key notice and created no run. No fake videos or fake translations were inserted.
- Screenshot: `youtube-plan-20261024.jpg`, a real empty/pending-configuration page, not a populated collection claim.

## Local state and preservation

- Pre-change backup: `data/dsih.pre-youtube-20261024T072355.bak`.
- Web API and frontend were stopped when checked; started both hidden on loopback ports 8000/5173.
- Existing Windows Scheduler remains Running, single original PID **42652** for this turn; never restarted or stopped. It has not loaded the new video job. No YouTube schedule is active. A controlled Scheduler reload with the configured key remains necessary before real scheduled acceptance; the UI distinguishes pending configuration/readiness.
- Read-only comparison against backup: every original row unchanged in research_plans (5 originals, now 6), research_runs (20), research_images (12), research_image_summaries (4), research_image_visual_reports (0), analysis (326), notification_deliveries (18), post_notifications (2).
- New tables: research_videos=0, research_run_videos=0, video_favorites=0; video_schedules has only plan 6, enabled=false, interval=1440, next_run_at=null.
- No `--once*` commands, existing collection job, Scheduler restart, Watchdog operation, real Feishu send, commit or branch creation.

## Setup handoff

User said they do not yet have a Google key. Application steps are in `docs/YOUTUBE_SETUP.md`: create Google project, enable YouTube Data API v3, create/restrict the API key to that API, store it as Windows user variable `DSIH_YOUTUBE_API_KEY`, restart development host so new processes inherit it, then notify Codex without sending the secret.

Official references: [Getting started](https://developers.google.com/youtube/data/getting-started), [search.list](https://developers.google.com/youtube/data/reference/rest/v3/search/list).

DeepSeek MCP delegation: **not used**. Existing application text-model integration was coded and tested with mocks only; no real model calls were made.

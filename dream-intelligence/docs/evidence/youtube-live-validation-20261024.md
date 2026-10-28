# YouTube 真实采集验收 — 2026-10-24

## Result

Manual public discovery → DSIH SQLite → Chinese metadata organization → regional gallery/favorite/preview: **PASS**.

Scheduled collection: **NOT_ENABLED / pending user interval choice and controlled Scheduler reload**. Human UX acceptance remains pending.

## Configuration and execution

- User reported that the YouTube environment variable was created. Checked booleans only: Windows user variable present=true; current host/backend inherited value=false.
- Read the authorized user variable `DSIH_YOUTUBE_API_KEY` into the launch environment of the verified Web API only. Restarted that API hidden, leaving the existing Scheduler running. No credential was printed, written into a file, URL or evidence, or sent to chat.
- Web API status then reported `configured=true`.
- Backup: `data/dsih.pre-youtube-live-20261024T074533.bak`.
- Executed exactly one normal manual collection for plan 6 (**视频灵感 · 趣味与互助**): four configured topics, at most three results each. No repeated crawl or pressure test.
- Run **21**, status **COMPLETED**, received **12**, inserted **12**, errors **[]**.
- Database: research_videos=12, distinct external_id=12; new run links=12. All 12 have Chinese title, short description and allowed category. All original timestamps are timezone-aware and returned newest-first.
- Chinese organization used one normal application text-model call. Codex reviewed all 12 saved outputs; they preserve title/description evidence limits, including uncertainty about real animal behavior and events. Token usage was not retained by this collection path; no token count is claimed.
- No fake global Intelligence was produced. Global items=15293, analysis=326, notification_deliveries=18, post_notifications=2, unchanged from the pre-run check.

## Categories

| Category | Videos |
|---|---:|
| 动物趣事 | 4 |
| 动物互助与救援 | 1 |
| 人类搞笑 | 3 |
| 温暖互助 | 4 |

These are metadata-based content categories, not proof that events/behavior shown in a video are authentic. No video-vision analysis was performed.

## Browser checks

- Used a separate results tab to preserve the user's unsaved six-hour/enable selection in the older tab. Did not reload, save or discard that form.
- Regional gallery shows the actual saved Chinese outputs, original channels and Beijing publication times. First two cards per category visible; additional cards remain collapsible.
- All seven initially rendered thumbnails loaded successfully (`complete && naturalWidth>0`). Other five are collapsed, not claimed visually checked.
- Temporarily favorited the first real video; favorite-only view showed one item, and a separate read-only API query confirmed persistence. Removed the temporary favorite and restored the original no-favorites state.
- Opened the first video's actual YouTube embed. The 8-second sample reached `0:08 / 0:08`, slider=100 and replay state. This verifies one playable sample; not every video is guaranteed embeddable/playable.
- Closed the player after verification. No video file was downloaded.
- Screenshots: `youtube-live-player-20261024.jpg` (completed playback), `youtube-live-results-20261024.jpg` (actual gallery).

## Scheduling and scope

- Original Windows Scheduler task remains Running, single PID **42652**; not stopped or restarted in this manual validation.
- Saved YouTube schedule remains disabled, interval_minutes=1440, next_run_at=null. The old worker has not loaded the new video job/key; the page correctly reports no connected YouTube worker.
- Asked user to choose daily / six-hour / two-hour frequency. Do not report automatic collection enabled until the preference is saved and new worker heartbeat verified. Do not trigger another immediate collection merely to activate scheduling.
- Existing Feishu jobs, subscription preferences and business jobs were not manually run. No Feishu send, download, code change, commit or branch creation was performed for this validation.
- Prior model-free tests: 259 backend and 38 frontend passed in implementation turn; not rerun or represented as newly executed here because no function code changed.

DeepSeek MCP delegation: **not used**. Distinguish the one existing application model call used for Chinese metadata organization from Codex delegation.

## Later activation: user chose every six hours

- Explicit human reply: **每 6 小时一次**.
- Saved via the normal API: enabled=true, interval_minutes=360. First next_run_at=`2026-10-24T13:59:16.512116+00:00`, i.e. **2026-10-24 21:59:16 Asia/Shanghai**. Service checks due plans about every five minutes; this is a plan time, not a guaranteed exact start.
- Necessary launcher adjustment: added only `DSIH_YOUTUBE_API_KEY` to the existing Windows user-variable refresh list in `scripts/run_scheduler_background.ps1`. It logs SET/MISSING only. PowerShell parser syntax check passed; no key value was output or stored.
- Used existing `stop_scheduler.ps1` / `start_scheduler.ps1` for a normal controlled reload. Worker PID changed from 42652 to **2204**; Windows task enabled/Running, one project scheduler instance. Startup log: formal profile, job_count=11. No once mode was used.
- Live readiness: configured=true, scheduler_connected=true, scheduler_configured=true. Real UI shows checked automatic collection, **每 6 小时**, connected worker and the Beijing next-run time. Screenshot: `youtube-six-hour-schedule-20261024.jpg`.
- Counts before/after activation unchanged: research_runs=21, research_videos=12, notification_deliveries=18, post_notifications=2. No immediate new collection, model call, download or manual Feishu send occurred.
- Activation/registration acceptance: PASS. First future timed execution has not yet occurred and is **NOT_OBSERVED**; do not confuse a connected scheduler with completed six-hour collection evidence.
- DeepSeek delegation/model calls during activation: **0**.

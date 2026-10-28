# YouTube 来源集中修复 — 2026-10-24

## Verified problem

User-created plan 7, **YouTube动物互助温情视频素材定期收集**, had eight bilingual topics. Its run 22 completed with only three unique videos, all from **劉丽小動物救助站**. This confirms the user's observation.

The earlier collector requested only the newest three results for each complete topic string and deduplicated by video ID. It imposed no channel diversity limit. The eight topics append Chinese glosses to English phrases, which were passed unchanged to YouTube. This plausibly narrowed discovery; the old run did not store per-query responses, so identical results from every individual query are not independently provable. No channel ID filter was configured. The text model only translated/classified received metadata; it was not an autonomous search planner or source-balancing agent.

## Local repair

- Separate an English multiword prefix from a trailing Chinese display gloss; retain Chinese-only searches and single-English-term mixed searches. Do not overwrite the stored user topic or purpose.
- Up to eight distinct normalized queries, ten results each, alternating relevance/date order. No extra search calls or pagination beyond the former eight-query ceiling.
- Round-robin query coverage, stable video-ID dedup, maximum twelve selected videos and two per stable channel ID (normalized display-name fallback). Do not invent more sources if the API actually returns only one.
- Add independent `video_search_reports` keyed by run ID, recording actual topics, sent queries, sort modes, per-query returned counts and unique candidate/selected source counts. No credentials or raw HTTP payloads are recorded. Expose a collapsed factual search explanation; old missing provenance remains unknown.
- Update plan-assistant guidance to avoid concatenated bilingual search phrases. Preserve original video history/favorites. Category and Chinese descriptions still use only title/description evidence, with explicit authenticity limits.

## Real validation

- Backup: `data/dsih.pre-youtube-diversity-20261024T081242.bak`.
- Ran exactly one normal manual collection for plan 7 after model-free tests and controlled Web API reload.
- Run **23**: **COMPLETED**, errors=[], inserted=12.
- Eight successful searches each returned ten normalized candidates; after ID dedup: **79 candidates from 73 channels**.
- Selected **12 videos from 12 different channels**. All twelve received Chinese title/description/category organization, reviewed by Codex. This proves source diversification for this run, not visual truthfulness or originality.
- Database totals after validation: research_videos=27; research_runs=23; analysis=326; notification_deliveries=18; post_notifications=2; video_favorites=0. The previous three videos are retained.
- Actual browser verified run 23 statistics, expanded query list and cards from multiple named channels. Screenshot: `youtube-diversity-20261024.jpg`.
- Normal Scheduler reload applies the repair to future timed runs. Plan 6 and 7 remain enabled at 360-minute intervals; plan 6's saved next time remains unchanged. Plan 7's normal manual collection advances its next due time to six hours after completion. No one-shot CLI job or Feishu send was invoked.

## Validation and limits

- Final backend full regression: **263 passed**, 0 failed; YouTube subset: 21 passed. Frontend full regression: **39 passed**; final TypeScript/Vite build passed.
- Frontend full regression: 39 passed, including actual-vs-legacy search explanation. TypeScript/Vite build passed.
- Tests cover bilingual query separation, stable channel-ID caps across display-name changes, round-robin topic selection, query dedup, accurate trace counts, persistence/read without external calls, and existing collection/Intelligence/notification separation.
- Unique channels can repost the same scene; two returned videos have near-identical duckling/cat descriptions. No cross-channel audiovisual deduplication or authenticity classifier is claimed. Keywords can return loosely related or AI-generated material. Source diversity is fixed; suitability/truth must still be checked using actual videos.
- Official API semantics verified against [Google search.list documentation](https://developers.google.com/youtube/data/reference/rest/v3/search/list): query, relevance/date order and maxResults. The final library remains ordered by original publication time.

DeepSeek MCP delegation: **not used**. One real application text-model call organized the twelve public candidates; Codex checked the saved outputs. Token usage was not persisted by this path and is not claimed.

Final preservation check: every old row remains unchanged in research_plans, research_videos, research_run_videos, research_runs, analysis, notification_deliveries, post_notifications and video_favorites. Single live Scheduler PID **9752**; both enabled video schedules remain 360 minutes, configured and connected. Plan 6 next run remains `2026-10-24T13:59:16.512116+00:00`; plan 7 after its normal manual validation is due `2026-10-24T14:13:28.366081+00:00`.

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_SCHEDULER_STARTED

from app.commands.collect_newsnow import save_collection as save_newsnow
from app.commands.collect_github import save_collection as save_github
from app.commands.collect_rss import save_collection as save_rss
from app.commands.analyze_queue import run_queue_once
from app.connectors.newsnow import NewsNowConnector
from app.connectors.github import GitHubConnector
from app.connectors.rss import RSSConnector
from app.db.database import DATA_DIR, initialize_database
from app.commands.scheduler_lock import scheduler_instance_lock
from app.feishu.schedule import load_brief_schedule_config, run_scheduled_brief
from app.market.collection import collect_once as collect_market_once
from app.market.announcement_collection import collect_announcements_once
from app.market.announcement_documents import read_pending_announcements
from app.monitors.tibo import load_tibo_config,run_tibo_job
from app.monitors.tibo_settings import RUNTIME_PATH, atomic_json


NEWSNOW_INTERVAL_MINUTES = 60
GITHUB_INTERVAL_MINUTES = 120
RSS_INTERVAL_MINUTES = 240
ANALYSIS_INTERVAL_MINUTES = 240
ANALYSIS_OFFSET_MINUTES = 12


@dataclass(frozen=True)
class ScheduleProfile:
    name: str
    newsnow_minutes: int
    github_minutes: int
    rss_minutes: int
    analysis_minutes: int
    announcement_hours: str


FORMAL_PROFILE = ScheduleProfile("formal", 60, 120, 240, 240, "18,22")
PHASE_G_PROFILE = ScheduleProfile("phase_g_48h", 15, 30, 60, 120,
                                  "8,10,12,14,16,18,20,22")
PHASE_G_STATE_PATH = DATA_DIR / "phase_g_acceleration.json"


def load_schedule_profile(now=None, path: Path = PHASE_G_STATE_PATH):
    """Use the temporary schedule only inside its saved 48-hour window."""
    instant = now or datetime.now(timezone.utc)
    if not path.is_file():
        return FORMAL_PROFILE
    try:
        state = json.loads(path.read_text(encoding="utf-8-sig"))
        start = datetime.fromisoformat(state["start_at"])
        end = datetime.fromisoformat(state["end_at"])
        if (state.get("active") is True and start.tzinfo and end.tzinfo and
                end - start == timedelta(hours=48) and start <= instant < end):
            return PHASE_G_PROFILE
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return FORMAL_PROFILE


def collect_newsnow_job():
    return save_newsnow(NewsNowConnector().collect())


def collect_github_job():
    return save_github(GitHubConnector().collect())


def collect_rss_job():
    return save_rss(RSSConnector().collect())


def run_auto_analysis_job():
    selection, report = run_queue_once()
    candidates = {candidate.item_id: candidate for candidate in selection.candidates}
    return {**report, "results": [
        {"source": candidates[row["item_id"]].source,
         "title": candidates[row["item_id"]].title, **row}
        for row in report["results"]]}


def collect_market_job():
    return collect_market_once()


def collect_market_announcements_job():
    return collect_announcements_once()


def run_market_announcements_job():
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        rows = collect_market_announcements_job()
        documents = []
        stock_results = []
        docs_failed = 0
        for row in rows:
            stock = {"symbol": row.symbol, "market": row.market,
                     "new_announcements": row.inserted,
                     "result": ("UNSUPPORTED" if row.market != "SZ" and row.failed else
                                "FAILED" if row.failed else "OK")}
            stock_results.append(stock)
            if row.failed:
                continue
            try:
                for document in read_pending_announcements(row.symbol, row.market, limit=3):
                    documents.append({"announcement_id": document.announcement_id,
                                      "title": document.title, "status": document.status,
                                      "error_code": document.error_code})
                    docs_failed += document.status == "FAILED"
            except Exception:
                # Keep other stocks running; never print response bodies or PDF text.
                docs_failed += 1
                stock["result"] = "DOCUMENT_ERROR"
        ann_failed = sum(row.failed for row in rows)
        result = {
            "job": "market_announcements", "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "watchlist_count": len(rows),
            "ann_received": sum(row.received for row in rows),
            "ann_inserted": sum(row.inserted for row in rows),
            "ann_skipped": sum(row.skipped for row in rows),
            "ann_failed": ann_failed,
            "docs_selected": len(documents),
            "docs_readable": sum(row["status"] == "READABLE" for row in documents),
            "docs_skipped_complex": sum(row["status"] == "SKIPPED_COMPLEX" for row in documents),
            "docs_failed": docs_failed,
            "status": "WARNING" if ann_failed or docs_failed else "OK",
            "stocks": stock_results, "documents": documents,
        }
    except Exception:
        result = {
            "job": "market_announcements", "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "watchlist_count": 0, "ann_received": 0, "ann_inserted": 0,
            "ann_skipped": 0, "ann_failed": 1, "docs_selected": 0,
            "docs_readable": 0, "docs_skipped_complex": 0, "docs_failed": 0,
            "status": "FAILED", "stocks": [], "documents": [],
        }
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def run_market_job():
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        rows = collect_market_job()
        inserted = sum(row.inserted for row in rows)
        skipped = sum(row.skipped for row in rows)
        failed = sum(row.failed for row in rows)
        result = {
            "job": "market", "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "watchlist_count": len(rows), "received": inserted + skipped,
            "inserted": inserted, "skipped": skipped, "failed": failed,
            "status": "OK" if failed == 0 else "WARNING",
            "results": [{
                "symbol": row.symbol, "market": row.market, "date": row.date,
                "result": "FAILED" if row.failed else "INSERTED" if row.inserted else "SKIPPED",
            } for row in rows],
        }
    except Exception:
        # Do not log provider/database exception text: it may contain response bodies.
        result = {
            "job": "market", "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "watchlist_count": 0, "received": 0,
            "inserted": 0, "skipped": 0, "failed": 1,
            "status": "FAILED", "results": [],
        }
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


JOBS = (
    ("NewsNow", NEWSNOW_INTERVAL_MINUTES, collect_newsnow_job),
    ("GitHub", GITHUB_INTERVAL_MINUTES, collect_github_job),
    ("RSS", RSS_INTERVAL_MINUTES, collect_rss_job),
)


def run_job(name, collect):
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        report = collect()
        received = report["received"]
        inserted = report["inserted"]
        skipped = report["skipped"]
        failed = report["failed"]
        status = "OK" if failed == 0 else "WARNING"
    except Exception:
        # Connector and database exception text may contain credentials or response bodies.
        received = inserted = skipped = 0
        failed = 1
        status = "FAILED"
    result = {"job": name, "started_at": started_at,
              "finished_at": datetime.now(timezone.utc).isoformat(),
              "received": received, "inserted": inserted, "skipped": skipped,
              "failed": failed, "status": status}
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def run_once():
    return [run_job(name, collect) for name, _, collect in JOBS]


def run_analysis_job():
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        report = run_auto_analysis_job()
        status = ("PROVIDER_UNAVAILABLE" if report["provider_unavailable"] else
                  "WARNING" if report["failed"] else "OK")
        result = {"job": "auto_analysis", "started_at": started_at,
                  "finished_at": datetime.now(timezone.utc).isoformat(),
                  "selected": report["selected"], "analyzed": report["analyzed"],
                  "skipped": report["skipped"], "failed": report["failed"],
                  "normal_llm_calls": report["normal_calls"], "repair_calls": report["repair_count"],
                  "aborted_remaining": report["aborted_remaining"],
                  "status": status, "results": report["results"]}
    except Exception:
        result = {"job": "auto_analysis", "started_at": started_at,
                  "finished_at": datetime.now(timezone.utc).isoformat(),
                  "selected": 0, "analyzed": 0, "skipped": 0, "failed": 1,
                  "normal_llm_calls": 0, "repair_calls": 0, "aborted_remaining": 0,
                  "status": "FAILED", "results": []}
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def run_feishu_brief_job():
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        result = run_scheduled_brief()
    except Exception:
        # Never log exception text: provider and database errors may contain secrets.
        result = {"status": "FAILED", "http_calls": 0, "reason": "BRIEF_JOB_ERROR"}
    result = {"job": "feishu_daily_brief", "started_at": started_at,
              "finished_at": datetime.now(timezone.utc).isoformat(), **result}
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def sync_tibo_schedule(scheduler, now=None, config_path=None, runtime_path=None):
    """Reconcile preferences only. Never execute a collector, model or sender."""
    instant = now or datetime.now(timezone.utc)
    config = load_tibo_config(config_path)
    job = scheduler.get_job('tibo_monitor')
    if config is None or job is None:
        return
    if job.trigger.interval != timedelta(minutes=config.poll_minutes):
        scheduler.reschedule_job('tibo_monitor', trigger='interval', minutes=config.poll_minutes,
                                 start_date=instant + timedelta(minutes=config.poll_minutes))
        job = scheduler.get_job('tibo_monitor')
    next_run = getattr(job, 'next_run_time', None) or job.trigger.get_next_fire_time(None, instant)
    atomic_json(runtime_path or RUNTIME_PATH, {
        'poll_minutes': config.poll_minutes, 'updated_at': instant.isoformat(),
        'next_run_time': next_run.isoformat() if next_run else None})


def create_scheduler(now=None, profile=None, tibo_config=None):
    anchor = now or datetime.now(timezone.utc)
    profile = profile or load_schedule_profile(anchor)
    scheduler = BlockingScheduler(timezone=timezone.utc)
    from app.research.video_schedule import run_due_video_plans, write_video_heartbeat
    scheduler.add_job(run_due_video_plans,'interval',minutes=5,start_date=anchor+timedelta(minutes=5),
                      id='youtube_discovery',name='YouTube Video Inspiration',max_instances=1,coalesce=True)
    scheduler.add_job(write_video_heartbeat,'interval',seconds=30,
                      id='youtube_heartbeat',name='Video Schedule Status',max_instances=1,coalesce=True)
    scheduler.add_listener(lambda event: write_video_heartbeat(), EVENT_SCHEDULER_STARTED)
    intervals = {"NewsNow": profile.newsnow_minutes, "GitHub": profile.github_minutes,
                 "RSS": profile.rss_minutes}
    for name, minutes, collect in JOBS:
        minutes = intervals[name]
        scheduler.add_job(run_job, "interval", minutes=minutes, args=(name, collect),
                          start_date=anchor + timedelta(minutes=minutes),
                          id=name.lower(), name=name, max_instances=1, coalesce=True)
    scheduler.add_job(run_analysis_job, "interval", minutes=profile.analysis_minutes,
                      start_date=anchor + timedelta(minutes=profile.rss_minutes + ANALYSIS_OFFSET_MINUTES),
                      id="auto_analysis", name="Auto Analysis", max_instances=1, coalesce=True)
    scheduler.add_job(run_market_job, "cron", day_of_week="mon-fri", hour=16, minute=10,
                      timezone=ZoneInfo("Asia/Shanghai"),
                      id="market", name="Market Collector", max_instances=1, coalesce=True)
    scheduler.add_job(run_market_announcements_job, "cron", day_of_week="mon-fri",
                      hour=profile.announcement_hours, minute=30,
                      timezone=ZoneInfo("Asia/Shanghai"),
                      id="market_announcements", name="Market Announcements",
                      max_instances=1, coalesce=True)
    brief_config = load_brief_schedule_config()
    if brief_config is not None:
        scheduler.add_job(run_feishu_brief_job, "cron",
                          hour=brief_config.send_time.hour,
                          minute=brief_config.send_time.minute,
                          timezone=brief_config.zone,
                          id="feishu_daily_brief", name="Feishu Daily Brief",
                          max_instances=1, coalesce=True)
    if tibo_config is not None and tibo_config.enabled:
        scheduler.add_job(run_tibo_job,'interval',minutes=tibo_config.poll_minutes,
            start_date=anchor+timedelta(minutes=tibo_config.poll_minutes),id='tibo_monitor',name='Tibo Chinese Updates & Reset Alerts',
            max_instances=1,coalesce=True,misfire_grace_time=60)
        scheduler.add_job(sync_tibo_schedule, 'interval', seconds=30, args=(scheduler,),
                          id='tibo_settings_sync', name='Subscription Preferences',
                          max_instances=1, coalesce=True)
        scheduler.add_listener(lambda event: sync_tibo_schedule(scheduler), EVENT_SCHEDULER_STARTED)
    return scheduler


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run fixed collection and bounded analysis jobs")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run collector jobs only and exit")
    mode.add_argument("--once-analysis", action="store_true", help="Run the analysis job only and exit")
    mode.add_argument("--once-market", action="store_true", help="Run the Market job only and exit")
    mode.add_argument("--once-announcements", action="store_true",
                      help="Run the Market Announcements job only and exit")
    mode.add_argument("--once-brief", action="store_true",
                      help="Run the guarded Feishu Daily Brief job only and exit")
    args = parser.parse_args(argv)
    if args.once:
        initialize_database()
        return 1 if any(result["status"] != "OK" for result in run_once()) else 0
    if args.once_analysis:
        initialize_database()
        return 0 if run_analysis_job()["status"] == "OK" else 1
    if args.once_market:
        initialize_database()
        return 0 if run_market_job()["status"] == "OK" else 1
    if args.once_announcements:
        initialize_database()
        return 1 if run_market_announcements_job()["status"] == "FAILED" else 0
    if args.once_brief:
        initialize_database()
        return 0 if run_feishu_brief_job()["status"] in (
            "SENT", "SKIP_ALREADY_SENT_TODAY", "NO_CONTENT") else 1
    with scheduler_instance_lock() as acquired:
        if not acquired:
            print("SCHEDULER_ALREADY_RUNNING", flush=True)
            return 2
        initialize_database()
        profile = load_schedule_profile()
        scheduler = create_scheduler(profile=profile,tibo_config=load_tibo_config())
        if scheduler.get_job("feishu_daily_brief") is None:
            print(json.dumps({"status": "FEISHU_BRIEF_SCHEDULE_NOT_CONFIGURED"}), flush=True)
        print(json.dumps({"status": "SCHEDULER_STARTED", "job_count": len(scheduler.get_jobs()),
                          "schedule_profile": profile.name}),
              flush=True)
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            if scheduler.running:
                scheduler.shutdown(wait=True)
        print("Scheduler stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

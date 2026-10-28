"""Manual, bounded import of MediaCrawler Bilibili JSONL into a research plan.

MediaCrawler runs separately. This module reads only its public result fields and
never reads browser profiles, cookies, or the crawler's private configuration.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Item, ResearchPlan, ResearchRun, ResearchRunItem, Source
from app.research.collection import item_identity, summarize_items
from app.research.websites import normalize_site_url

MAX_FILE_BYTES = 2_000_000
MAX_ROWS = 100
BILIBILI_HOME = "https://www.bilibili.com/"
BILIBILI_VIDEO = re.compile(r"^/video/(?:av\d+|BV[A-Za-z0-9]+)/*$")


def relevant_to_topic(topic: str, title: str, description: str) -> bool:
    """Small candidate filter; the purpose summary still judges usefulness."""
    needle = "".join(topic.casefold().split())
    haystack = "".join((title + " " + description).casefold().split())
    if not needle:
        return False
    if needle in haystack:
        return True
    if len(needle) <= 3:
        return needle in haystack
    pairs = {needle[i:i + 2] for i in range(len(needle) - 1)}
    # The keyword already matches the plan. Keep partial topic matches as
    # candidates so a useful tutorial is not lost before purpose analysis.
    return any(pair in haystack for pair in pairs)


def normalize_bilibili_row(row: dict) -> dict:
    title = str(row.get("title") or "").strip()[:300]
    url = normalize_site_url(str(row.get("video_url") or ""))
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname != "www.bilibili.com"
            or not BILIBILI_VIDEO.fullmatch(parts.path) or parts.query):
        raise ValueError("Invalid Bilibili video URL")
    if not title:
        raise ValueError("Missing title")
    description = " ".join(str(row.get("desc") or "").split())[:4000]
    keyword = str(row.get("source_keyword") or "").strip()
    published = None
    try:
        timestamp = int(row.get("create_time"))
        if 946684800 <= timestamp <= int(datetime.now(timezone.utc).timestamp()) + 86400:
            published = datetime.fromtimestamp(timestamp, timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    return {"title": title, "url": url, "content": description,
            "keyword": keyword, "published_at": published}


def read_bilibili_jsonl(path: Path) -> tuple[list[dict], int]:
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Input file missing or too large")
    rows: list[dict] = []
    invalid = 0
    with path.open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if number > MAX_ROWS:
                raise ValueError("Input has too many rows")
            try:
                raw = json.loads(line)
                if not isinstance(raw, dict):
                    raise ValueError
                rows.append(normalize_bilibili_row(raw))
            except (ValueError, TypeError):
                invalid += 1
    return rows, invalid


def import_bilibili_jsonl(plan_id: int, path: Path, sessions=SessionLocal,
                         client=None) -> int:
    rows, invalid = read_bilibili_jsonl(path)
    with sessions() as session, session.begin():
        plan = session.get(ResearchPlan, plan_id)
        if plan is None or not plan.enabled:
            raise ValueError("Research plan not found")
        if BILIBILI_HOME not in plan.websites:
            raise ValueError("Research plan must select Bilibili")
        if session.scalar(select(ResearchRun.id).where(
                ResearchRun.plan_id == plan_id, ResearchRun.status == "RUNNING")):
            raise RuntimeError("Research plan is already running")
        topics, purpose = list(plan.topics), plan.purpose
        run = ResearchRun(plan_id=plan_id, status="RUNNING", errors=[])
        session.add(run)
        session.flush()
        run_id = run.id
        source = session.scalar(select(Source).where(
            Source.type == "mediacrawler", Source.url == BILIBILI_HOME))
        selected = [row for row in rows if row["keyword"] in topics and
                    relevant_to_topic(row["keyword"], row["title"], row["content"])]
        if selected and source is None:
            source = Source(name="Bilibili", type="mediacrawler", url=BILIBILI_HOME,
                            category="USER_RESEARCH", enabled=True)
            session.add(source)
            session.flush()
        inserted = 0
        linked_ids: set[int] = set()
        for row in selected:
            identity = item_identity(row["url"])
            item = session.scalar(select(Item).where(Item.external_id == identity))
            if item is None:
                item = Item(source_id=source.id, external_id=identity, title=row["title"],
                            url=row["url"], content=row["content"], author=None,
                            published_at=row["published_at"], captured_at=datetime.now(timezone.utc))
                session.add(item)
                session.flush()
                inserted += 1
            if item.id not in linked_ids:
                session.add(ResearchRunItem(run_id=run_id, item_id=item.id))
                linked_ids.add(item.id)
        run.received = len(rows) + invalid
        run.matched = len(linked_ids)
        run.inserted = inserted
        run.errors = ([{"website": "www.bilibili.com", "reason": "INVALID_ROWS",
                        "count": invalid}] if invalid else [])

    with sessions() as session:
        items = session.scalars(select(Item).join(ResearchRunItem,
            ResearchRunItem.item_id == Item.id).where(
            ResearchRunItem.run_id == run_id).order_by(
                Item.published_at.desc().nulls_last(), Item.id.desc()).limit(12)).all()
    summary = None
    errors = [{"website": "www.bilibili.com", "reason": "INVALID_ROWS",
               "count": invalid}] if invalid else []
    if items:
        try:
            summary = summarize_items(items, topics, purpose, client,
                evidence_scope="仅有 B 站视频标题和简介；未观看视频或读取字幕。")
        except Exception:
            errors.append({"website": None, "reason": "SUMMARY_FAILED"})
    with sessions() as session, session.begin():
        run = session.get(ResearchRun, run_id)
        run.errors = errors
        run.summary = summary.model_dump() if summary else None
        run.status = ("COMPLETED" if not errors else "PARTIAL") if summary else (
            "NO_MATCHES" if not items and not errors else "FAILED" if not items else "SUMMARY_FAILED")
        run.finished_at = datetime.now(timezone.utc)
    return run_id

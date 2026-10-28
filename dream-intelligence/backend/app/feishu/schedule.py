"""A single daily Feishu Brief with a database-backed same-day guard."""

import os
import re
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select

from app.commands.send_feishu_brief import build_current_brief
from app.db.database import SessionLocal
from app.db.models import NotificationDelivery
from app.feishu.sender import FeishuSendError, FeishuWebhookSender


@dataclass(frozen=True)
class BriefScheduleConfig:
    send_time: time
    zone: ZoneInfo
    webhook_url: str


def load_brief_schedule_config(environ: Mapping[str, str] | None = None) -> BriefScheduleConfig | None:
    values = environ if environ is not None else os.environ
    raw_time = values.get("DSIH_FEISHU_BRIEF_TIME", "")
    raw_zone = values.get("DSIH_FEISHU_BRIEF_TIMEZONE", "")
    webhook = values.get("DSIH_FEISHU_WEBHOOK_URL", "")
    if not re.fullmatch(r"[0-9]{2}:[0-9]{2}", raw_time) or not raw_zone or not webhook:
        return None
    try:
        hour, minute = map(int, raw_time.split(":"))
        send_time = time(hour, minute)
        zone = ZoneInfo(raw_zone)
        FeishuWebhookSender(webhook)  # Validate only; no HTTP call.
    except (ValueError, ZoneInfoNotFoundError, FeishuSendError):
        return None
    return BriefScheduleConfig(send_time, zone, webhook)


def run_scheduled_brief(config: BriefScheduleConfig | None = None,
                        session_factory=SessionLocal, now: datetime | None = None,
                        builder=build_current_brief,
                        sender_class=FeishuWebhookSender) -> dict:
    config = config or load_brief_schedule_config()
    if config is None:
        return {"status": "FEISHU_BRIEF_SCHEDULE_NOT_CONFIGURED", "http_calls": 0}
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("Scheduled Brief clock must be timezone-aware")
    delivery_date = instant.astimezone(config.zone).date()
    day = delivery_date.isoformat()
    with session_factory() as session:
        # SQLite write lock serializes concurrent scheduler/CLI processes before the HTTP call.
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        already_sent = session.scalar(select(NotificationDelivery.id).where(
            NotificationDelivery.channel == "feishu",
            NotificationDelivery.notification_type == "daily_brief",
            NotificationDelivery.delivery_date == delivery_date,
            NotificationDelivery.status == "SENT"))
        if already_sent is not None:
            session.rollback()
            return {"status": "SKIP_ALREADY_SENT_TODAY", "delivery_date": day,
                    "http_calls": 0}
        brief = builder(session_factory=session_factory, now=instant.astimezone(config.zone))
        if not brief.has_content:
            session.rollback()
            return {"status": "NO_CONTENT", "delivery_date": day, "http_calls": 0}
        try:
            receipt = sender_class(config.webhook_url).send(brief.payload)
        except FeishuSendError as exc:
            session.rollback()
            return {"status": "FAILED", "delivery_date": day, "http_calls": 1,
                    "reason": exc.code, "http_status": exc.http_status}
        except Exception:
            session.rollback()
            return {"status": "FAILED", "delivery_date": day, "http_calls": 1,
                    "reason": "SEND_ERROR"}
        session.add(NotificationDelivery(
            channel="feishu", notification_type="daily_brief",
            delivery_date=delivery_date, status="SENT",
            sent_at=instant.astimezone(timezone.utc)))
        session.commit()
    return {"status": "SENT", "delivery_date": day, "http_calls": 1,
            "http_status": receipt.http_status, "provider_code": receipt.provider_code}

import unittest
from io import BytesIO
from unittest.mock import Mock, patch

import httpx
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db.models import (MarketAnnouncement, MarketAnnouncementDocument,
                           MarketSnapshot, MarketWatchlist)
from app.db.seed import seed
from app.main import app
from app.market.announcement_documents import read_latest_announcements
from app.market.announcement_reader import (DocumentReadError, Extraction,
                                            download_official_pdf, extract_plain_text)

OFFICIAL = "https://disc.static.szse.cn/download/disc/test.pdf"


def fixture_pdf(text=None, encrypted=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    if text is not None:
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({
                NameObject("/F1"): writer._add_object(font),
            }),
        })
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 72 720 Td (" + text.encode("ascii") + b") Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("fixture-only")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class FakeStream:
    def __init__(self, payload, status=200, content_type="application/pdf"):
        self.payload = payload
        self.status_code = status
        self.headers = {"content-type": content_type, "content-length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def iter_bytes(self):
        yield self.payload


class ReaderTests(unittest.TestCase):
    def test_text_pdf_readable_blank_and_encrypted_skip(self):
        readable = extract_plain_text(fixture_pdf("Useful public announcement text. " * 20))
        self.assertEqual(readable.status, "READABLE")
        self.assertGreaterEqual(readable.char_count, 300)
        self.assertIn("Useful public announcement", readable.text)
        blank = extract_plain_text(fixture_pdf())
        self.assertEqual((blank.status, blank.error_code, blank.text),
                         ("SKIPPED_COMPLEX", "NO_TEXT_LAYER", None))
        encrypted = extract_plain_text(fixture_pdf("Protected content. " * 25, encrypted=True))
        self.assertEqual((encrypted.status, encrypted.error_code, encrypted.text),
                         ("SKIPPED_COMPLEX", "ENCRYPTED", None))

    def test_download_only_official_pdf_and_classify_failures(self):
        payload = fixture_pdf("Public announcement text. " * 20)
        with patch("app.market.announcement_reader.httpx.stream",
                   return_value=FakeStream(payload)) as request:
            self.assertEqual(download_official_pdf(OFFICIAL), payload)
            request.assert_called_once()
            self.assertFalse(request.call_args.kwargs["follow_redirects"])
        with patch("app.market.announcement_reader.httpx.stream") as request:
            with self.assertRaises(DocumentReadError) as context:
                download_official_pdf("https://evil.example/document.pdf")
            self.assertEqual((context.exception.status, context.exception.code),
                             ("FAILED", "NON_OFFICIAL_URL"))
            request.assert_not_called()
        with patch("app.market.announcement_reader.httpx.stream",
                   return_value=FakeStream(payload, content_type="text/html")):
            with self.assertRaises(DocumentReadError) as context:
                download_official_pdf(OFFICIAL)
            self.assertEqual(context.exception.code, "INVALID_CONTENT_TYPE")
        with patch("app.market.announcement_reader.httpx.stream",
                   side_effect=httpx.ConnectError("offline")):
            with self.assertRaises(DocumentReadError) as context:
                download_official_pdf(OFFICIAL)
            self.assertEqual((context.exception.status, context.exception.code),
                             ("FAILED", "NETWORK_ERROR"))


class AnnouncementDocumentTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.factory() as session:
            seed(session)
            session.add(MarketWatchlist(symbol="002782", market="SZ", name="test"))
            session.add(MarketSnapshot(symbol="002782", market="SZ",
                                       date=__import__("datetime").date(2026, 9, 28),
                                       close=14.14, source="fake"))
            for index in range(1, 4):
                session.add(MarketAnnouncement(
                    symbol="002782", market="SZ", external_id=str(index),
                    title=f"Official document {index}", url=OFFICIAL.replace("test.pdf", f"{index}.pdf"),
                    published_at=__import__("datetime").datetime(2026, 9, 28),
                    source="SZSE", raw_json={"annId": index}))
            session.commit()
        self.session = self.factory()
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app)
        self.protected = self._protected_rows()

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.session.close()
        self.engine.dispose()

    def _protected_rows(self):
        with self.engine.connect() as connection:
            return {name: connection.exec_driver_sql(f'SELECT * FROM "{name}" ORDER BY id').all()
                    for name in ("sources", "items", "analysis", "feedback", "watchlist",
                                 "market_watchlist", "market_snapshots", "market_announcements")}

    def test_terminal_skips_retryable_failure_api_and_existing_data_boundary(self):
        baseline_item = self.client.get("/api/v1/market").json()["items"][0]
        full_text = "Public document text. " * 25

        def fake_reader(url):
            if url.endswith("/1.pdf"):
                return Extraction("READABLE", full_text, len(full_text), None)
            if url.endswith("/2.pdf"):
                return Extraction("SKIPPED_COMPLEX", None, 0, "NO_TEXT_LAYER")
            return Extraction("FAILED", None, 0, "NETWORK_ERROR")

        reader = Mock(side_effect=fake_reader)
        first = read_latest_announcements(3, self.factory, reader)
        second = read_latest_announcements(3, self.factory, reader)
        self.assertEqual([row.status for row in first], ["READABLE", "SKIPPED_COMPLEX", "FAILED"])
        self.assertEqual([row.skipped for row in second], [True, True, False])
        self.assertEqual(reader.call_count, 4)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(MarketAnnouncementDocument)), 3)
        after_item = self.client.get("/api/v1/market").json()["items"][0]
        self.assertEqual([row["read_status"] for row in after_item["announcements"]],
                         ["READABLE", "SKIPPED_COMPLEX", "FAILED"])
        self.assertEqual([row["text_available"] for row in after_item["announcements"]],
                         [True, False, False])
        self.assertNotIn("text", after_item["announcements"][0])
        ids = [row["id"] for row in after_item["announcements"]]
        readable = self.client.get(f"/api/v1/market/announcements/{ids[0]}/text")
        self.assertEqual(readable.status_code, 200)
        self.assertEqual(readable.json()["text"], full_text)
        for announcement_id in ids[1:]:
            unavailable = self.client.get(f"/api/v1/market/announcements/{announcement_id}/text")
            self.assertEqual(unavailable.status_code, 409)
            self.assertIn("official URL", unavailable.json()["detail"])
        self.assertEqual(self.client.get("/api/v1/market/announcements/9999/text").status_code, 404)
        self.assertEqual({key: value for key, value in after_item.items()
                          if key != "announcements"},
                         {key: value for key, value in baseline_item.items()
                          if key != "announcements"})
        self.assertEqual(self._protected_rows(), self.protected)


if __name__ == "__main__":
    unittest.main()

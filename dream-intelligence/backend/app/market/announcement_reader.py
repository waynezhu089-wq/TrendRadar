"""Bounded plain PDF text-layer reading for official SZSE announcements only."""

from dataclasses import dataclass
from io import BytesIO
import re
import unicodedata

import httpx
from pypdf import PdfReader

from .announcements import official_url

MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_PAGES = 100
MIN_TEXT_CHARS = 300


class DocumentReadError(Exception):
    def __init__(self, status: str, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


@dataclass(frozen=True)
class Extraction:
    status: str
    text: str | None
    char_count: int
    error_code: str | None


def download_official_pdf(url: str) -> bytes:
    try:
        safe_url = official_url(url)
    except ValueError as exc:
        raise DocumentReadError("FAILED", "NON_OFFICIAL_URL") from exc
    try:
        with httpx.stream("GET", safe_url, timeout=20, follow_redirects=False,
                          headers={"User-Agent": "Mozilla/5.0", "Accept": "application/pdf"}) as response:
            if response.status_code != 200:
                raise DocumentReadError("FAILED", "HTTP_ERROR")
            if response.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/pdf":
                raise DocumentReadError("FAILED", "INVALID_CONTENT_TYPE")
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > MAX_PDF_BYTES:
                raise DocumentReadError("SKIPPED_COMPLEX", "TOO_LARGE")
            chunks = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > MAX_PDF_BYTES:
                    raise DocumentReadError("SKIPPED_COMPLEX", "TOO_LARGE")
                chunks.append(chunk)
            payload = b"".join(chunks)
    except httpx.RequestError as exc:
        raise DocumentReadError("FAILED", "NETWORK_ERROR") from exc
    if not payload.startswith(b"%PDF-"):
        raise DocumentReadError("FAILED", "NOT_PDF")
    return payload


def extract_plain_text(payload: bytes) -> Extraction:
    try:
        reader = PdfReader(BytesIO(payload), strict=False)
        if reader.is_encrypted:
            return Extraction("SKIPPED_COMPLEX", None, 0, "ENCRYPTED")
        if len(reader.pages) > MAX_PAGES:
            return Extraction("SKIPPED_COMPLEX", None, 0, "TOO_MANY_PAGES")
        lines = []
        for page in reader.pages:
            for line in (page.extract_text() or "").splitlines():
                clean_line = re.sub(r"[ \t]+", " ", line).strip()
                if clean_line:
                    lines.append(clean_line)
        text = "\n".join(lines).strip()
    except Exception:
        return Extraction("FAILED", None, 0, "PDF_PARSE_ERROR")
    if not text:
        return Extraction("SKIPPED_COMPLEX", None, 0, "NO_TEXT_LAYER")
    if len(text) < MIN_TEXT_CHARS:
        return Extraction("SKIPPED_COMPLEX", None, 0, "TOO_LITTLE_TEXT")
    bad = sum(char == "\ufffd" or
              (unicodedata.category(char) == "Cc" and char not in "\n\t") for char in text)
    if bad / len(text) > 0.1 or sum(char.isalnum() for char in text) < 100:
        return Extraction("SKIPPED_COMPLEX", None, 0, "UNREADABLE_TEXT")
    return Extraction("READABLE", text, len(text), None)


def read_official_document(url: str) -> Extraction:
    try:
        return extract_plain_text(download_official_pdf(url))
    except DocumentReadError as exc:
        return Extraction(exc.status, None, 0, exc.code)

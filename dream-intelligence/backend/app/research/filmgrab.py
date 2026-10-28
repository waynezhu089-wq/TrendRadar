"""Small public FilmGrab search/gallery reader. Does not inspect image pixels."""
import hashlib
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from .images import ImageCandidate, ImageSourceUnavailable, clean, public_url

ROOT = 'https://film-grab.com/'
MAX_FILMS_PER_QUERY = 2
FRAMES_PER_FILM = 3


def film_url(value):
    url = public_url(urljoin(ROOT, value))
    parsed = urlsplit(url)
    if parsed.hostname not in ('film-grab.com', 'www.film-grab.com'):
        return ''
    return urlunsplit(('https', 'film-grab.com', parsed.path, parsed.query, ''))


def film_links(html):
    soup = BeautifulSoup(html, 'html.parser')
    result = []
    for anchor in soup.select('.entry-title a[href]'):
        url = film_url(anchor['href'])
        if url and re.fullmatch(r'/\d{4}/\d{2}/\d{2}/[^/]+/', urlsplit(url).path) and url not in result:
            result.append(url)
    return result[:MAX_FILMS_PER_QUERY]


def gallery_images(html, source_url):
    soup = BeautifulSoup(html, 'html.parser')
    content, heading = soup.select_one('.entry-content'), soup.select_one('.entry-title')
    if content is None or heading is None:
        raise ImageSourceUnavailable('IMAGE_SOURCE_FORMAT_CHANGED')
    title = clean(heading.get_text(' ', strip=True), 200)
    paragraphs = [clean(p.get_text(' ', strip=True), 500) for p in content.select(':scope > p')]
    metadata = [re.sub(r'\s*:\s*', ': ', value) for value in paragraphs]
    metadata = [value for value in metadata if re.match(
        r'^(Director:|Director of Photography:|Production Design:|Costume Design:|Year:)', value)]
    creator = ' / '.join(value for value in metadata if value.startswith(('Director:', 'Director of Photography:')))
    rights = [value for value in paragraphs if re.search(
        r'commercial use|permissions|copyright|all rights reserved', value, re.I)]
    anchors = content.select('a.bwg_lightbox[href], .gallery-item a[href]')
    # Sample across the gallery; no claim that these individual frames match the visual brief.
    positions = sorted({0, len(anchors) // 2, len(anchors) - 1}) if anchors else []
    result = []
    for position in positions[:FRAMES_PER_FILM]:
        anchor = anchors[position]
        image = anchor.find('img')
        if image is None:
            continue
        image_url = public_url(urljoin(source_url, anchor['href']))
        preview = image.get('data-original') or image.get('data-src') or image.get('src')
        thumbnail = public_url(urljoin(source_url, preview)) if preview else ''
        if not image_url or not thumbnail:
            continue
        canonical = urlsplit(image_url)._replace(query='', fragment='').geturl()
        external_id = 'filmgrab-' + hashlib.sha256(canonical.encode()).hexdigest()
        result.append(ImageCandidate(external_id, f'{title} · 参考帧 {position + 1}',
            source_url, image_url, thumbnail, creator, '', '',
            f'影片：{title}；来源：FilmGrab；' + '；'.join([*metadata, *rights]) + '。仅收集公开参考预览，成片使用授权待确认。',
            [title, *metadata, '电影画面参考', '单帧内容未看图核验'], None, None, provider='filmgrab'))
    if not result:
        raise ImageSourceUnavailable('IMAGE_SOURCE_FORMAT_CHANGED')
    return result


class FilmGrabImageCollector:
    def __init__(self):
        self.cache = {}
        self.provider_errors = []

    def get_html(self, url, params=None):
        target = film_url(url)
        if not target:
            raise ImageSourceUnavailable('IMAGE_SOURCE_REJECTED')
        try:
            # Only same-site public redirects; never forward credentials or read a browser session.
            for _ in range(3):
                response = httpx.get(target, params=params, timeout=15, follow_redirects=False,
                                     headers={'User-Agent': 'DreamIntelligence/0.1 (personal visual research)'})
                if response.status_code in (301, 302, 303, 307, 308):
                    target = film_url(urljoin(target, response.headers.get('location', '')))
                    if not target:
                        raise ImageSourceUnavailable('IMAGE_SOURCE_REJECTED')
                    params = None
                    continue
                response.raise_for_status()
                if len(response.content) > 3 * 1024 * 1024 or 'html' not in response.headers.get('content-type', ''):
                    raise ImageSourceUnavailable('IMAGE_SOURCE_FORMAT_CHANGED')
                return response.text
            raise ImageSourceUnavailable('IMAGE_SOURCE_REJECTED')
        except ImageSourceUnavailable:
            raise
        except httpx.TimeoutException:
            raise ImageSourceUnavailable('IMAGE_SOURCE_TIMEOUT') from None
        except httpx.HTTPStatusError as error:
            reason = 'IMAGE_SOURCE_RATE_LIMITED' if error.response.status_code == 429 else 'IMAGE_SOURCE_REJECTED'
            raise ImageSourceUnavailable(reason) from None
        except httpx.RequestError:
            raise ImageSourceUnavailable('IMAGE_SOURCE_NETWORK_ERROR') from None

    def collect(self, query):
        links = film_links(self.get_html(ROOT, params={'s': query}))
        result = []
        for url in links:
            try:
                if url not in self.cache:
                    self.cache[url] = gallery_images(self.get_html(url), url)
                result.extend(self.cache[url])
            except ImageSourceUnavailable as error:
                if not result:
                    raise
                self.provider_errors.append(error.reason)
                break
        return result

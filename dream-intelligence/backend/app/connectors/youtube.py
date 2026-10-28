"""Bounded public YouTube Data API search; never downloads video or reads cookies."""
import html
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

API = 'https://www.googleapis.com/youtube/v3/search'
CANDIDATES_PER_QUERY = 10
MAX_SELECTED = 12
MAX_PER_CHANNEL = 2


def search_query(topic):
    """Separate an English search phrase from a trailing Chinese display gloss."""
    topic=' '.join(topic.split())
    prefix=re.split(r'[\u4e00-\u9fff]',topic,maxsplit=1)[0].strip(' -—:：/()（）')
    if prefix!=topic and len(re.findall(r'[A-Za-z]+',prefix))>=2:
        return prefix
    return topic


def diversified_selection(batches):
    selected=[];seen=set();channels={}
    # Round robin gives each query a chance before filling remaining positions.
    for rank in range(max((len(batch) for batch in batches),default=0)):
        for batch in batches:
            if rank>=len(batch):continue
            row=batch[rank]
            identity=row.channel_id or row.channel.strip().casefold() or 'unknown-channel'
            if row.external_id in seen or channels.get(identity,0)>=MAX_PER_CHANNEL:continue
            seen.add(row.external_id);channels[identity]=channels.get(identity,0)+1;selected.append(row)
            if len(selected)>=MAX_SELECTED:return selected
    return selected


class YouTubeError(Exception):
    pass


def api_key():
    key = os.environ.get('DSIH_YOUTUBE_API_KEY', '').strip()
    if not key:
        raise YouTubeError('YOUTUBE_NOT_CONFIGURED')
    return key


@dataclass(frozen=True)
class Video:
    external_id: str
    title: str
    description: str
    channel: str
    thumbnail_url: str
    published_at: datetime
    channel_id: str = ''


def normalize(row):
    try:
        ident = row['id']['videoId']
        snippet = row['snippet']
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}', ident):
            return None
        published = datetime.fromisoformat(snippet['publishedAt'].replace('Z','+00:00'))
        if not published.tzinfo:
            return None
        title = html.unescape(snippet['title']).strip()
        if not title:
            return None
        # Construct the preview from the validated ID rather than trusting arbitrary response URLs.
        return Video(ident, title[:500], html.unescape(snippet.get('description',''))[:2000],
                     html.unescape(snippet.get('channelTitle',''))[:200],
                     f'https://i.ytimg.com/vi/{ident}/mqdefault.jpg', published,
                     snippet.get('channelId','') if isinstance(snippet.get('channelId',''),str) else '')
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


class YouTubeConnector:
    def collect(self, topics, now=None):
        key = api_key()
        instant = now or datetime.now(timezone.utc)
        batches=[];errors=[];queries=[];seen_queries=set()
        self.search_report={'queries':queries,'candidate_count':0,'candidate_channel_count':0,
            'selected_count':0,'selected_channel_count':0,'max_per_channel':MAX_PER_CHANNEL,
            'limit':MAX_SELECTED,'basis':'TITLE_AND_DESCRIPTION','version':'diverse.1'}
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            for topic in topics[:8]:
                query=search_query(topic)
                if not query or query.casefold() in seen_queries:continue
                seen_queries.add(query.casefold())
                order='relevance' if len(queries)%2==0 else 'date'
                trace={'topic':topic,'query':query,'order':order,'returned':0,'status':'FAILED'}
                queries.append(trace)
                try:
                    # Use a header so credentials do not appear in request URLs or access logs.
                    response = client.get(API, headers={'X-Goog-Api-Key':key}, params={
                        'part':'snippet','type':'video','q':query,'order':order,'maxResults':CANDIDATES_PER_QUERY,
                        'safeSearch':'moderate','publishedAfter':(instant-timedelta(days=30)).isoformat()})
                    if response.status_code >= 400 or response.is_redirect:
                        raise YouTubeError(f'YOUTUBE_HTTP_{response.status_code}')
                    if len(response.content) > 1_000_000:
                        raise YouTubeError('YOUTUBE_RESPONSE_INVALID')
                    data = response.json()
                    if not isinstance(data.get('items'),list):
                        raise YouTubeError('YOUTUBE_RESPONSE_INVALID')
                    batch=[]
                    for item in data['items'][:CANDIDATES_PER_QUERY]:
                        video = normalize(item)
                        if video:
                            batch.append(video)
                    batches.append(batch);trace.update(returned=len(batch),status='OK')
                except YouTubeError as error:
                    errors.append({'website':'YouTube','reason':str(error)})
                    # Permissions/quota failures affect the shared key; do not try every topic again.
                    break
                except Exception:
                    errors.append({'website':'YouTube','reason':'YOUTUBE_REQUEST_FAILED'})
        candidates={row.external_id:row for batch in batches for row in batch}
        selected=diversified_selection(batches)
        channel_key=lambda row:row.channel_id or row.channel.strip().casefold() or 'unknown-channel'
        self.search_report.update(candidate_count=len(candidates),
            candidate_channel_count=len({channel_key(row) for row in candidates.values()}),
            selected_count=len(selected),selected_channel_count=len({channel_key(row) for row in selected}))
        return sorted(selected, key=lambda row:row.published_at, reverse=True), errors

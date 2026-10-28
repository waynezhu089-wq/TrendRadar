import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from sqlalchemy import func, select

from app.db.models import Analysis, Item, ResearchPlan, ResearchRun, Source
from app.research.douban import (DoubanAccessBlocked, DoubanBrowserCollector,
    DoubanLoginRequired, DoubanUnsupportedPage, parse_review, parse_shorts,
    review_links, search_subjects, subject_url, supports_douban_site)
from app.research.collection import run_research_plan
import test_research as helpers
from test_research import FakeClient, FakeCollector

SUBJECT = 'https://movie.douban.com/subject/1292052/'
SHORT_HTML = '''<h1>作品 短评</h1><div class="comment-item" data-cid="42">
<span class="comment-info"><a>作者甲</a><a class="comment-time" title="2026-10-23 08:30:00">日期</a></span>
<span class="short">希望与自由，读者观点。<script>忽略</script></span></div>'''
REVIEW_HTML = '''<h1>值得讨论的视角</h1><header class="main-hd"><a class="name">作者乙</a>
<span property="v:dtreviewed" content="2026-10-22 20:00:00"></span></header>
<div class="review-content">这是实际长评正文，不是列表摘要。<script>忽略</script></div>'''


class DoubanParserTests(unittest.TestCase):
    def test_urls_are_strict_and_canonical(self):
        self.assertEqual(subject_url(SUBJECT + 'reviews/?sort=new#x'), SUBJECT)
        for url in ('https://movie.douban.com.evil/subject/1/',
                    'https://user:pass@movie.douban.com/subject/1/',
                    'http://movie.douban.com/subject/1/',
                    'https://www.douban.com/group/1/', 'https://movie.douban.com:443/subject/1/'):
            self.assertFalse(supports_douban_site(url), url)
        self.assertTrue(supports_douban_site('https://book.douban.com/'))

    def test_search_unwraps_only_valid_book_movie_subjects(self):
        html = '''<div class="result"><h3><a href="https://www.douban.com/link2/?url=https%3A%2F%2Fmovie.douban.com%2Fsubject%2F1292052%2F">作品</a></h3></div>
        <div class="result"><h3><a href="https://evil.example/subject/1/">外站</a></h3></div>
        <div class="result"><h3><a href="https://book.douban.com/subject/2/">书</a></h3></div>'''
        self.assertEqual(search_subjects(html, 'movie'), [SUBJECT])
        self.assertEqual(search_subjects(html, 'book'), ['https://book.douban.com/subject/2/'])

    def test_shorts_have_stable_identity_original_time_and_bound(self):
        values = parse_shorts(SHORT_HTML, SUBJECT, '作品')
        self.assertEqual(len(values), 1)
        item = values[0]
        self.assertEqual(item.external_id, 'douban:movie.douban.com:comment:42')
        self.assertEqual(item.published_at.isoformat(), '2026-10-23T00:30:00+00:00')
        self.assertIn('作者甲', item.content)
        self.assertNotIn('忽略', item.content)
        html = ''.join(SHORT_HTML.replace('data-cid="42"', f'data-cid="{n}"') for n in range(10))
        self.assertEqual(len(parse_shorts(html, SUBJECT, '作品')), 3)

    def test_review_uses_body_not_abstract_and_bounds_links(self):
        item = parse_review(REVIEW_HTML, 'https://movie.douban.com/review/77/', '作品')
        self.assertIn('实际长评正文', item.content)
        self.assertIn('正文节选', item.content)
        self.assertNotIn('忽略', item.content)
        self.assertIn('作者乙', item.content)
        self.assertEqual(item.published_at.isoformat(), '2026-10-22T12:00:00+00:00')
        listing = ''.join(f'<div class="review-item"><h2><a href="https://movie.douban.com/review/{n}/">标题</a></h2></div>' for n in range(3))
        self.assertEqual(review_links(listing, SUBJECT), ['https://movie.douban.com/review/0/'])
        self.assertFalse(review_links(listing.replace('movie.douban.com', 'evil.example'), SUBJECT))

    def test_requires_profile_and_rejects_unsupported_scope(self):
        with TemporaryDirectory() as folder:
            collector = DoubanBrowserCollector(Path(folder) / 'absent')
            with self.assertRaises(DoubanLoginRequired): collector.collect(SUBJECT, ['书影'])
            with self.assertRaises(DoubanUnsupportedPage): collector.collect('https://www.douban.com/group/', ['书影'])

    def test_access_block_stops_and_closes_profile_without_retry(self):
        page = MagicMock()
        page.goto.return_value.status = 403
        page.url = 'https://www.douban.com/'
        context = MagicMock(); context.pages = [page]
        manager = MagicMock()
        manager.__enter__.return_value.chromium.launch_persistent_context.return_value = context
        with TemporaryDirectory() as folder, patch('playwright.sync_api.sync_playwright', return_value=manager):
            with self.assertRaises(DoubanAccessBlocked):
                DoubanBrowserCollector(Path(folder)).collect(SUBJECT, ['书影'])
        self.assertEqual(page.goto.call_count, 1)
        context.close.assert_called_once()


class DoubanPersistenceTests(unittest.TestCase):
    setUp = helpers.ResearchTests.setUp
    tearDown = helpers.ResearchTests.tearDown

    def collector(self, errors=(), fail=False):
        collector = MagicMock(received=2, errors=list(errors))
        if fail:
            collector.collect.side_effect = DoubanLoginRequired()
        else:
            collector.collect.return_value = [*parse_shorts(SHORT_HTML, SUBJECT, '作品'),
                parse_review(REVIEW_HTML, 'https://movie.douban.com/review/77/', '作品')]
        return collector

    def test_routed_deduped_and_not_global_analysis(self):
        with self.sessions() as db, db.begin():
            plan = db.get(ResearchPlan, self.plan_id)
            plan.websites = [SUBJECT]; plan.topics = ['概念与评论可以不逐字相同']
        for _ in range(2):
            run_research_plan(self.plan_id, self.sessions, FakeCollector(), FakeClient(), douban_collector=self.collector())
        with self.sessions() as db:
            runs = db.scalars(select(ResearchRun).order_by(ResearchRun.id)).all()
            self.assertEqual([(r.status,r.received,r.matched,r.inserted) for r in runs], [('COMPLETED',2,2,2),('COMPLETED',2,2,0)])
            self.assertEqual(db.scalar(select(func.count()).select_from(Analysis)), 0)
            self.assertEqual(db.scalar(select(Source.name)), '豆瓣书影评论')
            self.assertEqual(db.scalar(select(Source.type)), 'custom_web')

    def test_login_failure_does_not_lose_other_source(self):
        with self.sessions() as db, db.begin():
            db.get(ResearchPlan,self.plan_id).websites = [SUBJECT, 'https://example.com/feed']
        ident = run_research_plan(self.plan_id,self.sessions,FakeCollector(),FakeClient(),douban_collector=self.collector(fail=True))
        with self.sessions() as db:
            run = db.get(ResearchRun,ident)
            self.assertEqual((run.status,run.inserted),('PARTIAL',1))
            self.assertEqual(run.errors[0]['reason'],'DoubanLoginRequired')

    def test_partial_browser_results_remain_usable_and_reported(self):
        with self.sessions() as db, db.begin():
            db.get(ResearchPlan,self.plan_id).websites = [SUBJECT]
        ident = run_research_plan(self.plan_id,self.sessions,FakeCollector(),FakeClient(),douban_collector=self.collector(errors=['DoubanAccessBlocked']))
        with self.sessions() as db:
            run = db.get(ResearchRun,ident)
            self.assertEqual((run.status,run.inserted),('PARTIAL',2))
            self.assertEqual(run.errors[0]['reason'],'DoubanAccessBlocked')

    def test_login_endpoint_only_opens_window_and_never_collects(self):
        from fastapi.testclient import TestClient
        from app.main import app
        with patch('app.commands.douban_login.open_login') as login, patch('app.api.v1.research.run_research_plan') as collect:
            response = TestClient(app).post('/api/v1/research-sources/douban/login')
        self.assertEqual(response.status_code, 200)
        login.assert_called_once(); collect.assert_not_called()

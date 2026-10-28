import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.db.models import Analysis, Item, ResearchPlan, ResearchRun, ResearchRunItem, Source
from app.main import app
from app.intelligence.analyzer import Analyzer
from app.research.collection import run_research_plan, summarize_items, reanalyze_research_run
from app.api.v1.research import run_output
from app.research.websites import WebItem, WebsiteCollector, normalize_site_url, require_public_host
from app.research.zhihu import (ZhihuAccessBlocked, ZhihuBrowserCollector,
                                ZhihuLoginRequired, article_url, is_zhihu_search_site,
                                parse_article, search_article_links)


class FakeCollector:
    def __init__(self, fail=()):
        self.fail = fail

    def collect(self, site):
        if site in self.fail:
            raise ValueError("Website HTTP 503")
        return [WebItem("AI视频模型更新", "https://example.com/article/1",
                        "新的 AI 视频功能公开发布。")]


class FakeClient:
    def __init__(self, bad_citation=False):
        self.messages = []
        self.bad_citation = bad_citation

    def analyze(self, messages):
        self.messages = messages
        items = json.loads(messages[1]["content"])["items"]
        return json.dumps({"overview": "针对目标的线索汇总", "findings": [{
            "item_id": -99 if self.bad_citation else items[0]["item_id"],
            "insight": "有新的视频功能", "purpose_relevance": "可供选型比较",
            "suggested_action": "查看原文并试用"}], "limitations": "仅依据公开摘要",
            "sections": [{"category":"工作流与应用","summary":"本组共同关注制作流程",
                          "key_points":["仍需核验"],"suggested_action":"查看原文",
                          "item_ids":[item["item_id"] for item in items]}]}, ensure_ascii=False)


class FakeZhihuCollector:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def collect(self, site, topics):
        self.calls.append((site, topics))
        if self.fail:
            raise ZhihuLoginRequired()
        return [WebItem("第一篇原文", "https://www.zhihu.com/question/12/answer/34",
                        "围绕第一个话题的正文。"),
                WebItem("第二篇原文", "https://zhuanlan.zhihu.com/p/56",
                        "围绕第二个话题的正文。")]


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as session, session.begin():
            plan = ResearchPlan(name="AI 视频选型", topics=["AI视频"],
                websites=["https://example.com/feed"], purpose="为 Dream Stream 比较 AI 视频工具")
            session.add(plan)
            session.flush()
            self.plan_id = plan.id

    def tearDown(self):
        self.engine.dispose()

    def test_public_url_validation_and_private_dns_rejection(self):
        for url in ("http://127.0.0.1/", "https://localhost/", "http://[::1]/",
                    "file:///etc/passwd", "https://user:pass@example.com/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                normalize_site_url(url)
        self.assertEqual(normalize_site_url(" https://EXAMPLE.COM/feed#news "),
                         "https://example.com/feed")
        with patch("socket.getaddrinfo", return_value=[(None, None, None, None,
                                                           ("10.0.0.2", 443))]):
            with self.assertRaises(ValueError):
                require_public_host("https://example.com/")

    def test_zhihu_search_links_and_original_article_text(self):
        search = '''<main><div>AI 生成回答：不要当原文
          <a href="/question/99/answer/88">AI 引用</a></div>
          <div class="SearchResult-Card"><a href="/question/12/answer/34?utm_source=search#x">卡片标题</a></div>
          <div class="SearchResult-Card"><a href="https://zhuanlan.zhihu.com/p/56">专栏</a></div>
          <a href="https://evil.example/question/1/answer/2">外站</a></main>'''
        self.assertEqual(search_article_links(search), [
            "https://www.zhihu.com/question/12/answer/34",
            "https://zhuanlan.zhihu.com/p/56"])
        article = '''<html><h1>真正的原文标题</h1><div>AI 生成回答：不要当原文</div>
          <div class="RichContent-inner">这是作者的原文内容，包含具体的方法、过程和可核对的细节，可供研究方案按目的汇总。
          <script>ignore</script></div></html>'''
        item = parse_article(article, "https://www.zhihu.com/question/12/answer/34")
        self.assertEqual(item.title, "真正的原文标题")
        self.assertNotIn("AI 生成回答", item.content)
        self.assertNotIn("ignore", item.content)
        self.assertIsNone(article_url("https://evil.example/question/1/answer/2"))
        self.assertTrue(is_zhihu_search_site("https://www.zhihu.com/"))
        self.assertFalse(is_zhihu_search_site("https://www.zhihu.com/question/12"))

    def test_zhihu_requires_dedicated_profile_before_collection(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            with self.assertRaises(ZhihuLoginRequired):
                ZhihuBrowserCollector(Path(folder) / "not-logged-in").collect(
                    "https://www.zhihu.com/", ["AI 视频"])

    def test_zhihu_http_403_is_reported_as_access_blocked(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        page = MagicMock()
        page.goto.return_value.status = 403
        page.url = "https://www.zhihu.com/search?type=content"
        context = MagicMock()
        context.pages = [page]
        manager = MagicMock()
        manager.__enter__.return_value.chromium.launch_persistent_context.return_value = context
        with TemporaryDirectory() as folder, patch(
                "playwright.sync_api.sync_playwright", return_value=manager):
            with self.assertRaises(ZhihuAccessBlocked):
                ZhihuBrowserCollector(Path(folder)).collect("https://www.zhihu.com/", ["AI 视频"])
        context.close.assert_called_once()

    def test_feed_and_html_collection_are_bounded(self):
        feed = b'<rss version="2.0"><channel><title>News</title><item><title>AI video</title><link>https://example.com/a</link><description>Launch</description></item></channel></rss>'
        collector = WebsiteCollector()
        with (patch.object(collector, "fetch", return_value=("https://example.com/feed", feed, "application/rss+xml")),
              patch("app.research.websites.require_public_host")):
            items = collector.collect("https://example.com/feed")
        self.assertEqual([(item.title, item.url, item.content) for item in items],
                         [("AI video", "https://example.com/a", "Launch")])
        listing = b'<html><article><h2><a href="/one">One</a></h2></article></html>'
        article = b'<html><title>AI video One</title><article><h1>AI video One</h1><p>Detail</p><script>ignore</script></article></html>'
        def fetch(url):
            return (url, article if url.endswith("/one") else listing, "text/html")
        with patch.object(collector, "fetch", side_effect=fetch):
            items = collector.collect("https://example.com/")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "AI video One")
        self.assertNotIn("ignore", items[0].content)

    def test_private_redirect_and_oversized_response_are_rejected(self):
        collector = WebsiteCollector()
        response = MagicMock()
        response.__enter__.return_value = response
        response.status_code = 302
        response.headers = {"location": "http://127.0.0.1/private"}
        client = MagicMock()
        client.__enter__.return_value = client
        client.stream.return_value = response
        with (patch("app.research.websites.httpx.Client", return_value=client),
              patch("app.research.websites.require_public_host")):
            with self.assertRaises(ValueError):
                collector.fetch("https://example.com/")
        self.assertEqual(client.stream.call_count, 1)

        response.status_code = 200
        response.headers = {"content-type": "text/html"}
        response.iter_bytes.return_value = [b"x" * 1_000_001]
        response.url = "https://example.com/"
        with (patch("app.research.websites.httpx.Client", return_value=client),
              patch("app.research.websites.require_public_host")):
            with self.assertRaisesRegex(ValueError, "size limit"):
                collector.fetch("https://example.com/")

    def test_purpose_summary_citations_dedup_and_raw_analysis_boundary(self):
        client = FakeClient()
        first = run_research_plan(self.plan_id, self.sessions, FakeCollector(), client)
        second = run_research_plan(self.plan_id, self.sessions, FakeCollector(), FakeClient())
        with self.sessions() as session:
            runs = session.scalars(select(ResearchRun).order_by(ResearchRun.id)).all()
            self.assertEqual([run.status for run in runs], ["COMPLETED", "COMPLETED"])
            self.assertEqual([run.inserted for run in runs], [1, 0])
            self.assertEqual(session.scalar(select(func.count()).select_from(Item)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(Analysis)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(ResearchRunItem)), 2)
            self.assertEqual(runs[0].summary["findings"][0]["item_id"],
                             session.scalar(select(Item.id)))
            self.assertEqual(session.scalar(select(Source.type)), "custom_web")
            item_id = session.scalar(select(Item.id))
        self.assertEqual((first, second), (1, 2))
        self.assertIn("为 Dream Stream 比较 AI 视频工具", client.messages[1]["content"])
        global_analyzer = Analyzer(FakeClient(), self.sessions, profile="Test")
        self.assertEqual(global_analyzer.pending_ids(), [])
        self.assertEqual(global_analyzer.analyze_one(item_id).status, "SKIP")

    def test_zhihu_topics_are_searched_without_literal_body_filter_and_deduped(self):
        with self.sessions() as session, session.begin():
            plan = session.get(ResearchPlan, self.plan_id)
            plan.topics = ["AI 视频生成", "AI 游戏开发"]
            plan.websites = ["https://www.zhihu.com/"]
        zhihu = FakeZhihuCollector()
        first = run_research_plan(self.plan_id, self.sessions, FakeCollector(),
                                  FakeClient(), zhihu_collector=zhihu)
        second = run_research_plan(self.plan_id, self.sessions, FakeCollector(),
                                   FakeClient(), zhihu_collector=zhihu)
        with self.sessions() as session:
            runs = session.scalars(select(ResearchRun).order_by(ResearchRun.id)).all()
            self.assertEqual([(run.received, run.matched, run.inserted)
                              for run in runs], [(2, 2, 2), (2, 2, 0)])
            self.assertEqual(session.scalar(select(func.count()).select_from(Item)), 2)
            self.assertEqual(session.scalar(select(func.count()).select_from(Analysis)), 0)
            self.assertEqual(session.scalar(select(Source.name)), "知乎")
            self.assertEqual(runs[0].summary["findings"][0]["item_id"],
                             session.scalar(select(Item.id).order_by(Item.id.desc())))
        self.assertEqual((first, second), (1, 2))
        self.assertEqual(zhihu.calls, [
            ("https://www.zhihu.com/", ["AI 视频生成", "AI 游戏开发"])] * 2)

    def test_zhihu_login_failure_does_not_stop_other_site(self):
        with self.sessions() as session, session.begin():
            plan = session.get(ResearchPlan, self.plan_id)
            plan.websites = ["https://www.zhihu.com/", "https://example.com/feed"]
        run_id = run_research_plan(self.plan_id, self.sessions, FakeCollector(),
                                   FakeClient(), zhihu_collector=FakeZhihuCollector(fail=True))
        with self.sessions() as session:
            run = session.get(ResearchRun, run_id)
            self.assertEqual((run.status, run.received, run.inserted), ("PARTIAL", 1, 1))
            self.assertEqual(run.errors, [{"website": "www.zhihu.com",
                                          "reason": "ZhihuLoginRequired"}])

    def test_failure_isolation_and_invalid_citation(self):
        failing_site = "https://other.example.org/feed"
        with self.sessions() as session, session.begin():
            plan = session.get(ResearchPlan, self.plan_id)
            plan.websites = [*plan.websites, failing_site]
        run_id = run_research_plan(self.plan_id, self.sessions,
                                   FakeCollector(fail=(failing_site,)), FakeClient())
        with self.sessions() as session:
            run = session.get(ResearchRun, run_id)
            self.assertEqual((run.status, run.inserted, len(run.errors)), ("PARTIAL", 1, 1))
            self.assertEqual(run.errors[0]["website"], "other.example.org")
        invalid_id = run_research_plan(self.plan_id, self.sessions,
                                        FakeCollector(), FakeClient(bad_citation=True))
        with self.sessions() as session:
            run = session.get(ResearchRun, invalid_id)
            self.assertEqual(run.status, "SUMMARY_FAILED")
            self.assertIsNone(run.summary)
            self.assertEqual(session.scalar(select(func.count()).select_from(Item)), 1)

    def test_publication_sorting_and_saved_analysis_preserve_raw_items(self):
        with self.sessions() as session, session.begin():
            source=Source(name='Test',type='custom_web',category='USER_RESEARCH',url='https://example.com/')
            session.add(source); session.flush()
            run=ResearchRun(plan_id=self.plan_id,status='COMPLETED',summary={'overview':'old','findings':[], 'limitations':''},errors=[])
            session.add(run);session.flush();rid=run.id
            for n,date in enumerate([datetime(2026,10,20,tzinfo=timezone.utc),None,datetime(2026,10,23,tzinfo=timezone.utc)]):
                item=Item(source_id=source.id,external_id=f'dated-{n}',title=f'Title {n}',url=f'https://example.com/{n}',content='Public',published_at=date)
                session.add(item);session.flush()
                session.add(ResearchRunItem(run_id=rid,item_id=item.id))
        with self.sessions() as session:
            result=run_output(session,session.get(ResearchRun,rid))
            self.assertEqual([i.title for i in result.items],['Title 2','Title 0','Title 1'])
            self.assertIsNotNone(result.items[0].published_at.tzinfo)
            self.assertIsNone(result.items[-1].published_at)
        reanalyze_research_run(self.plan_id,rid,self.sessions,FakeClient())
        with self.sessions() as session:
            previous=dict(session.get(ResearchRun,rid).summary)
            self.assertEqual(len(previous['sections'][0]['item_ids']),3)
            self.assertEqual(session.scalar(select(func.count()).select_from(Item)),3)
            self.assertEqual(session.scalar(select(func.count()).select_from(Analysis)),0)
        with self.assertRaises(ValueError):
            reanalyze_research_run(self.plan_id,rid,self.sessions,FakeClient(bad_citation=True))
        with self.sessions() as session:
            self.assertEqual(session.get(ResearchRun,rid).summary,previous)

    def test_grouping_must_cover_evidence_once_with_valid_citations(self):
        items=[SimpleNamespace(id=n,title='Title',url=f'https://example.com/{n}',content='Text',published_at=None) for n in [1,2]]
        good={'overview':'Summary','findings':[{'item_id':1,'insight':'Insight','purpose_relevance':'Relevant','suggested_action':'Read'}],
              'limitations':'Evidence only','sections':[{'category':'模型与版本','summary':'Group synthesis',
              'key_points':['A shared trend'],'suggested_action':'Verify','item_ids':[1,2]}]}
        for ids in ([1],[1,1],[1,99]):
            client=MagicMock()
            invalid=good | {'sections':[good['sections'][0] | {'item_ids':ids}]}
            client.analyze.return_value=json.dumps(invalid)
            with self.assertRaises(ValueError): summarize_items(items,['Topic'],'Research purpose',client)
            self.assertEqual(client.analyze.call_count,2)
        client=MagicMock();client.analyze.return_value=json.dumps(good)
        self.assertEqual(len(summarize_items(items,['Topic'],'Research purpose',client).sections),1)

    def test_api_plan_validation_history_and_soft_disable(self):
        with self.sessions() as session:
            app.dependency_overrides[get_db] = lambda: session
            client = TestClient(app)
            try:
                invalid = client.post("/api/v1/research-plans", json={"name": "Bad",
                    "topics": ["AI"], "websites": ["http://127.0.0.1/"],
                    "purpose": "Find useful information"})
                self.assertEqual(invalid.status_code, 422)
                private_bare = client.post("/api/v1/research-plans", json={"name": "Private",
                    "topics": ["AI"], "websites": ["127.0.0.1"],
                    "purpose": "Find useful information"})
                self.assertEqual(private_bare.status_code, 422)
                bare_domain = client.post("/api/v1/research-plans", json={"name": "Bilibili",
                    "topics": ["MiniMax H3"], "websites": ["www.bilibili.com"],
                    "purpose": "Track MiniMax H3 workflow updates"})
                self.assertEqual(bare_domain.status_code, 201)
                self.assertEqual(bare_domain.json()["websites"], ["https://www.bilibili.com/"])
                created = client.post("/api/v1/research-plans", json={"name": "Topic",
                    "topics": ["AI video"], "websites": ["https://example.org/feed"],
                    "purpose": "Compare AI video tools for production"})
                self.assertEqual(created.status_code, 201)
                self.assertEqual(len(client.get("/api/v1/research-plans").json()), 3)
                self.assertEqual(client.get(f"/api/v1/research-plans/{created.json()['id']}/runs").json(), [])
                with patch("app.api.v1.research.run_research_plan", side_effect=lambda plan_id, sessions:
                           run_research_plan(plan_id, sessions, FakeCollector(), FakeClient())):
                    ran = client.post(f"/api/v1/research-plans/{created.json()['id']}/run")
                self.assertEqual(ran.status_code, 200)
                self.assertEqual(ran.json()["status"], "NO_MATCHES")
                self.assertEqual(len(client.get(f"/api/v1/research-plans/{created.json()['id']}/runs").json()), 1)
                self.assertEqual(client.delete(f"/api/v1/research-plans/{created.json()['id']}").status_code, 204)
                self.assertEqual(len(client.get("/api/v1/research-plans").json()), 2)
            finally:
                client.close()
                app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock
import subprocess

from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.api.v1.research import run_research
from app.db.models import Analysis, Item, ResearchPlan, ResearchRun, ResearchRunItem, Source
from app.intelligence.analyzer import Analyzer
from app.research.mediacrawler import import_bilibili_jsonl, relevant_to_topic
from app.research.collection import run_research_plan
from app.research.bilibili import (BilibiliMediaCrawlerCollector, BilibiliLoginRequired,
                                  BilibiliTimeout, BilibiliCollectionFailed)
from app.research.websites import WebItem


class FakeClient:
    def __init__(self):
        self.request = None

    def analyze(self, messages):
        self.request = json.loads(messages[1]["content"])
        item_id = self.request["items"][0]["item_id"]
        return json.dumps({"overview": "按选型目的汇总", "findings": [{
            "item_id": item_id, "insight": "有教学资料", "purpose_relevance": "可比较流程",
            "suggested_action": "查看原文"}], "limitations": "仅依据视频标题和简介",
            "sections": [{"category":"教程与方法","summary":"教程提供不同的学习线索",
                          "key_points":["仅根据简介"],"suggested_action":"核实原文",
                          "item_ids":[item["item_id"] for item in self.request["items"]]}]},
            ensure_ascii=False)


class MediaCrawlerImportTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as session, session.begin():
            plan = ResearchPlan(name="视频工具研究", topics=["AI视频工具"],
                websites=["https://www.bilibili.com/"],
                purpose="为 Dream Stream 比较 AI 视频工具和制作流程")
            session.add(plan)
            session.flush()
            self.plan_id = plan.id
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "sample.jsonl"
        records = [
            {"title": "新手入坑必看！AI视频到底该怎么做？", "desc": "AI视频制作工具介绍",
             "video_url": "https://www.bilibili.com/video/av123#source", "source_keyword": "AI视频工具",
             "create_time": 1760000000},
            {"title": "ComfyUI 视频人物替换教程", "desc": "AI视频工作流",
             "video_url": "https://www.bilibili.com/video/BV123abc", "source_keyword": "AI视频工具"},
            {"title": "雀圣去赌场", "desc": "麻将故事",
             "video_url": "https://www.bilibili.com/video/av789", "source_keyword": "AI视频工具"},
        ]
        self.path.write_text("\n".join(json.dumps(row, ensure_ascii=False)
                                       for row in records), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()
        self.engine.dispose()

    def test_realistic_import_filters_unrelated_dedups_and_preserves_raw_boundary(self):
        client = FakeClient()
        first = import_bilibili_jsonl(self.plan_id, self.path, self.sessions, client)
        second = import_bilibili_jsonl(self.plan_id, self.path, self.sessions, FakeClient())
        with self.sessions() as session:
            runs = session.scalars(select(ResearchRun).order_by(ResearchRun.id)).all()
            self.assertEqual([(r.status, r.received, r.matched, r.inserted) for r in runs],
                             [("COMPLETED", 3, 2, 2), ("COMPLETED", 3, 2, 0)])
            self.assertEqual(session.scalar(select(func.count()).select_from(Item)), 2)
            self.assertEqual(session.scalar(select(func.count()).select_from(Analysis)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(ResearchRunItem)), 4)
            self.assertEqual(session.scalar(select(Source.type)), "mediacrawler")
            self.assertEqual({item.url for item in session.scalars(select(Item))}, {
                "https://www.bilibili.com/video/av123",
                "https://www.bilibili.com/video/BV123abc"})
            self.assertIsNotNone(runs[0].summary)
            self.assertEqual(Analyzer(FakeClient(), self.sessions, profile="Test").pending_ids(), [])
            self.assertEqual(Analyzer(FakeClient(), self.sessions, profile="Test").analyze_one(1).status, "SKIP")
        self.assertEqual((first, second), (1, 2))
        self.assertIn("标题和简介", client.request["evidence_scope"])
        self.assertEqual(len(client.request["items"]), 2)
        self.assertEqual(client.request["item_count"], 2)
        self.assertIsNotNone(client.request["items"][0]["published_at"])

    def test_input_and_plan_validation(self):
        self.assertFalse(relevant_to_topic("AI视频工具", "雀圣去赌场", "麻将故事"))
        self.assertTrue(relevant_to_topic("AI视频工具", "ComfyUI 视频人物替换教程", "本地工作流"))
        self.path.write_text(json.dumps({"title": "AI视频教程", "desc": "教程",
            "video_url": "https://evil.example/video/av123",
            "source_keyword": "AI视频工具"}), encoding="utf-8")
        run_id = import_bilibili_jsonl(self.plan_id, self.path, self.sessions, FakeClient())
        with self.sessions() as session:
            run = session.get(ResearchRun, run_id)
            self.assertEqual((run.received, run.matched, run.inserted), (1, 0, 0))
            self.assertEqual(session.scalar(select(func.count()).select_from(Item)), 0)
        with self.sessions() as session, session.begin():
            plan = session.get(ResearchPlan, self.plan_id)
            plan.websites = ["https://example.com/"]
        with self.assertRaisesRegex(ValueError, "select Bilibili"):
            import_bilibili_jsonl(self.plan_id, self.path, self.sessions, FakeClient())

    def test_page_run_collects_summarizes_and_deduplicates(self):
        class Bili:
            received = 3
            def collect(self, url, topics):
                return [WebItem("AI视频教程", "https://www.bilibili.com/video/av123", "简介")]
        with patch('app.api.v1.research.run_research_plan', side_effect=lambda pid,sessions:
                   run_research_plan(pid,sessions,client=FakeClient(),bilibili_collector=Bili())):
            with self.sessions() as session:
                first = run_research(self.plan_id, session)
                second = run_research(self.plan_id, session)
        self.assertEqual((first.received,first.matched,first.inserted,first.status),(3,1,1,'COMPLETED'))
        self.assertEqual((second.inserted,second.status),(0,'COMPLETED'))
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(Source.type)), 'mediacrawler')
            self.assertEqual(session.scalar(select(func.count()).select_from(Analysis)), 0)

    def test_summary_repair_is_bounded_and_preserves_items(self):
        class RepairClient(FakeClient):
            calls=0
            def analyze(self,messages):
                self.calls+=1
                return 'invalid JSON' if self.calls==1 else super().analyze(messages)
        client=RepairClient()
        rid=import_bilibili_jsonl(self.plan_id,self.path,self.sessions,client)
        self.assertEqual(client.calls,2)
        with self.sessions() as session:
            self.assertEqual(session.get(ResearchRun,rid).status,'COMPLETED')
            self.assertEqual(session.scalar(select(func.count()).select_from(Item)),2)
        class Unavailable(FakeClient):
            calls=0
            def analyze(self,messages):
                self.calls+=1
                raise RuntimeError('provider unavailable')
        unavailable=Unavailable()
        rid=import_bilibili_jsonl(self.plan_id,self.path,self.sessions,unavailable)
        self.assertEqual(unavailable.calls,1)
        with self.sessions() as session:
            self.assertEqual(session.get(ResearchRun,rid).status,'SUMMARY_FAILED')
            self.assertEqual(session.scalar(select(func.count()).select_from(Item)),2)

    def test_api_rejects_overlapping_run(self):
        from app.api.v1.research import manual_run_lock
        manual_run_lock.acquire()
        try:
            with self.sessions() as session, self.assertRaises(HTTPException) as caught:
                run_research(self.plan_id,session)
            self.assertEqual(caught.exception.status_code,409)
        finally:
            manual_run_lock.release()

    def test_bilibili_failure_keeps_successful_other_site(self):
        class Bili:
            def collect(self, url, topics): raise BilibiliLoginRequired()
        class Public:
            def collect(self, url):
                return [WebItem('AI视频工具教程','https://example.com/a','公开内容')]
        with self.sessions() as session, session.begin():
            session.get(ResearchPlan,self.plan_id).websites=['https://www.bilibili.com/','https://example.com/']
        run_id=run_research_plan(self.plan_id,self.sessions,collector=Public(),
                                 client=FakeClient(),bilibili_collector=Bili())
        with self.sessions() as session:
            run=session.get(ResearchRun,run_id)
            self.assertEqual((run.status,run.inserted),('PARTIAL',1))
            self.assertEqual(run.errors[0]['reason'],'BilibiliLoginRequired')

    def test_external_adapter_limits_filters_and_isolates_credentials(self):
        root=Path(self.temp.name)/'external'
        (root/'.venv/Scripts').mkdir(parents=True)
        (root/'.venv/Scripts/python.exe').touch()
        (root/'media_platform/bilibili').mkdir(parents=True)
        (root/'media_platform/bilibili/core.py').touch()
        def process(args, **kwargs):
            target=Path(args[-2])/'bili/jsonl'
            target.mkdir(parents=True)
            (target/'search_contents_test.jsonl').write_bytes(self.path.read_bytes())
            result=MagicMock(returncode=0,pid=12345)
            result.communicate.return_value=(b'finished',None)
            self.assertNotIn('DSIH_LLM_API_KEY',kwargs['env'])
            self.assertEqual(kwargs['env']['USERNAME'],'test-user')
            self.assertEqual(args[-1],'AI视频工具')
            self.assertIn('[:3]',args[2])
            return result
        with patch.dict('os.environ',{'USERNAME':'test-user','DSIH_LLM_API_KEY':'test-secret'}), \
             patch('app.research.bilibili.subprocess.Popen',side_effect=process):
            adapter=BilibiliMediaCrawlerCollector(root)
            pages=adapter.collect('https://www.bilibili.com/',['AI视频工具'])
        self.assertEqual((adapter.received,len(pages)),(3,2))
        result=MagicMock(returncode=1,pid=12345)
        result.communicate.return_value=(b'DSIH_LOGIN_REQUIRED',None)
        with patch('app.research.bilibili.subprocess.Popen',return_value=result):
            with self.assertRaises(BilibiliLoginRequired):
                adapter.collect('https://www.bilibili.com/',['AI视频工具'])
        result.communicate.return_value=(b'private failure detail',None)
        with patch('app.research.bilibili.subprocess.Popen',return_value=result):
            with self.assertRaises(BilibiliCollectionFailed):
                adapter.collect('https://www.bilibili.com/',['AI视频工具'])
        result.communicate.side_effect=[subprocess.TimeoutExpired('python',1),(b'',None)]
        with patch('app.research.bilibili.subprocess.Popen',return_value=result), \
             patch('app.research.bilibili.subprocess.run') as kill:
            with self.assertRaises(BilibiliTimeout):
                adapter.collect('https://www.bilibili.com/',['AI视频工具'])
            self.assertEqual(kill.call_args.args[0],['taskkill','/PID','12345','/T','/F'])


if __name__ == "__main__":
    unittest.main()

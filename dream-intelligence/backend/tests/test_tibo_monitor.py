import json
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock,patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine,func,select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base,get_db
from app.db.models import MonitoredPost,PostNotification,NotificationDelivery,Analysis,Item
from app.feishu.sender import FeishuSendError
from app.main import app
from app.monitors.tibo import TiboConfig,poll_tibo,translate_post,alert_payload,effective_signal,PostChinese
from app.monitors.tibo_sources import (TiboPost,ResetFeedCollector,ResetFeedUnavailable,
    XLoginRequired,browser_posts,feed_post,post_identity)
from app.commands.run_scheduler import create_scheduler

NOW=datetime(2026,10,23,7,tzinfo=timezone.utc)


def post(ident='100',date=None,kind='community_x_post',signal='CONFIRMED',text='Codex usage limits have been reset.'):
    return TiboPost(ident,text,kind,'https://codex-resets.com/',signal,
        published_at=date or NOW-timedelta(hours=1))


def translated(signal='CONFIRMED'):
    return json.dumps({'title_zh':'Codex额度重置动态','translation_zh':'Codex 使用额度已重置。',
        'reset_kind':signal,'reason_zh':'此为社区转录消息，请核对原帖与个人账号。'})


class TiboMonitorTests(unittest.TestCase):
    def setUp(self):
        self.directory=TemporaryDirectory()
        self.lock=patch('app.monitors.tibo.DATA_DIR',Path(self.directory.name));self.lock.start()
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine);self.sessions=sessionmaker(bind=self.engine)
        self.feed=Mock();self.feed.collect.return_value=[post()]
        self.model=Mock();self.model.analyze.return_value=translated()
        self.sender=Mock()

    def tearDown(self):
        self.engine.dispose();self.lock.stop();self.directory.cleanup()

    def run_poll(self,now=NOW,config=None,browser=None):
        return poll_tibo(config=config or TiboConfig(),sessions=self.sessions,feed=self.feed,
            browser=browser,client=self.model,sender_class=self.sender,webhook='test-not-a-real-webhook',now=now)

    def test_baseline_no_alert_then_new_chinese_event_sent_once(self):
        first=self.run_poll();self.assertTrue(first['baseline']);self.sender.assert_not_called()
        self.feed.collect.return_value=[post(),post('200',NOW+timedelta(seconds=30))]
        second=self.run_poll(NOW+timedelta(minutes=1))
        self.assertEqual(second['sent'],1)
        self.run_poll(NOW+timedelta(minutes=2))
        self.assertEqual(self.sender.return_value.send.call_count,1)
        payload=self.sender.return_value.send.call_args.args[0]
        self.assertIn('额度已重置',json.dumps(payload,ensure_ascii=False))
        self.assertIn('/status/200',json.dumps(payload));self.assertIn('社区转录',json.dumps(payload,ensure_ascii=False))
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(MonitoredPost)),2)
            self.assertEqual(db.scalar(select(PostNotification.status)),'SENT')
            for model in (Item,Analysis,NotificationDelivery):
                self.assertEqual(db.scalar(select(func.count()).select_from(model)),0)

    def test_english_output_is_never_sent_and_raw_post_survives(self):
        self.run_poll()
        self.feed.collect.return_value=[post('200',NOW+timedelta(seconds=30))]
        self.model.analyze.return_value=json.dumps({'title_zh':'Reset','translation_zh':'All reset.',
            'reset_kind':'CONFIRMED','reason_zh':'Done'})
        result=self.run_poll(NOW+timedelta(minutes=1))
        self.assertEqual(result['status'],'WARNING');self.sender.assert_not_called()
        with self.sessions() as db:
            row=db.scalar(select(MonitoredPost).where(MonitoredPost.external_id=='200'))
            self.assertIsNone(row.translation_zh);self.assertEqual(row.translation_attempts,1)

    def test_x_session_failure_keeps_public_reset_feed(self):
        browser=Mock();browser.collect.side_effect=XLoginRequired()
        result=self.run_poll(config=TiboConfig(browser_enabled=True),browser=browser)
        self.assertEqual(result['sources_ok'],1)
        self.assertEqual(result['errors'],[{'source':'x_browser','reason':'XLoginRequired'}])
        with self.sessions() as db:self.assertEqual(db.scalar(select(func.count()).select_from(MonitoredPost)),1)

    def test_unknown_network_receipt_not_retried_automatically(self):
        self.run_poll();self.feed.collect.return_value=[post('200',NOW+timedelta(seconds=30))]
        self.sender.return_value.send.side_effect=FeishuSendError('NETWORK_ERROR')
        self.assertEqual(self.run_poll(NOW+timedelta(minutes=1))['delivery'],'UNKNOWN')
        self.run_poll(NOW+timedelta(minutes=2))
        self.assertEqual(self.sender.return_value.send.call_count,1)

    def test_ordinary_updates_translate_without_alert(self):
        self.run_poll()
        self.feed.collect.return_value=[post('200',NOW+timedelta(seconds=30),kind='x_browser',signal='NONE',text='Codex performance improved.')]
        self.model.analyze.return_value=translated('NONE')
        self.run_poll(NOW+timedelta(minutes=1));self.sender.assert_not_called()
        with self.sessions() as db:self.assertIsNotNone(db.scalar(select(MonitoredPost.translation_zh).where(MonitoredPost.external_id=='200')))

    def test_later_completion_of_baseline_schedule_can_notify(self):
        self.feed.collect.return_value=[post(signal='SCHEDULED')]
        self.model.analyze.return_value=translated('SCHEDULED');self.run_poll()
        self.feed.collect.return_value=[post(signal='CONFIRMED',text='Reset is complete.')]
        self.model.analyze.return_value=translated('CONFIRMED')
        result=self.run_poll(NOW+timedelta(minutes=1))
        self.assertEqual(result['sent'],1)

    def test_browser_enrichment_does_not_send_completion_twice(self):
        self.run_poll();self.feed.collect.return_value=[post('200',NOW+timedelta(seconds=30))]
        self.run_poll(NOW+timedelta(minutes=1))
        browser=Mock();browser.collect.return_value=[post('200',NOW+timedelta(seconds=30),kind='x_browser',signal='NONE',text='We have reset Codex usage limits.')]
        self.run_poll(NOW+timedelta(minutes=2),TiboConfig(browser_enabled=True),browser)
        self.assertEqual(self.sender.return_value.send.call_count,1)

    def test_read_only_feed_get_does_not_poll_or_send(self):
        self.run_poll()
        with self.sessions() as db:
            app.dependency_overrides[get_db]=lambda:db
            try:
                with patch('app.monitors.tibo.poll_tibo') as poll:
                    response=TestClient(app).get('/api/v1/tibo-monitor')
                    self.assertEqual(response.status_code,200,response.text)
                    poll.assert_not_called()
                    self.assertTrue(response.json()['posts'][0]['translation_zh'])
                    self.assertNotIn('webhook',response.text.lower())
            finally:app.dependency_overrides.clear()


class TiboSourceTests(unittest.TestCase):
    def test_later_community_completion_does_not_masquerade_as_author_confirmation(self):
        value=type('Post',(),{'source_kind':'x_browser','feed_signal':'CONFIRMED'})()
        result=PostChinese(title_zh='预告',translation_zh='这次也有重置。',reset_kind='SCHEDULED',reason_zh='尚未执行。')
        self.assertEqual(effective_signal(value,result),'COMMUNITY_REPORTED')
        self.assertIn('不足以确认',result.reason_zh)
    def test_challenge_reward_does_not_become_a_completed_reset(self):
        model=Mock();model.analyze.return_value=json.dumps({'title_zh':'额度重置预告',
            'translation_zh':'没错，这次也有一次额度重置！','reset_kind':'CONFIRMED','reason_zh':'尚未说明执行状态。'})
        value=type('Post',(),{'original_text':"Day 18/ Codex updates. But yes... that's a reset!",'source_kind':'x_browser','feed_signal':'NONE'})()
        self.assertEqual(translate_post(value,model).reset_kind,'SCHEDULED')
    def test_canonical_links_observed_time_and_wrong_author(self):
        row={'id':'observed-123','text':'Codex limits reset.','announced_at':NOW.isoformat(),
            'source':{'type':'observed','url':'https://x.com/thsottiaux/status/123'}}
        value=feed_post(row,'CONFIRMED')
        self.assertIsNone(value.published_at);self.assertEqual(value.reported_at,NOW)
        self.assertEqual(value.source_kind,'community_observed')
        self.assertIsNone(post_identity('https://x.com.evil/thsottiaux/status/123'))
        self.assertIsNone(feed_post(row|{'source':{'type':'x_post','url':'https://x.com/other/status/123'}},'CONFIRMED'))

    def test_predictions_not_collected_and_stale_envelope_rejected(self):
        collector=ResetFeedCollector(NOW)
        with patch.object(collector,'get',side_effect=[{'active_watch':{'text':'Reset maybe tomorrow'}},[]]):
            self.assertEqual(collector.collect(),[])
        response=Mock();response.content=b'{}';response.json.return_value={'data':{},'meta':{'generated_at':(NOW-timedelta(hours=1)).isoformat()}}
        with patch('app.monitors.tibo_sources.httpx.get',return_value=response):
            with self.assertRaises(ResetFeedUnavailable):collector.get('status')

    def test_browser_only_parses_target_author_and_real_timestamps(self):
        html='''<article data-testid="tweet"><div data-testid="User-Name">Tibo @thsottiaux</div>
        <a href="/thsottiaux/status/123"><time datetime="2026-10-23T06:00:00Z"></time></a>
        <div data-testid="tweetText">Codex update.</div></article>
        <article data-testid="tweet"><div data-testid="User-Name">Someone @other</div>
        <a href="/other/status/456"><time datetime="2026-10-23T06:00:00Z"></time></a>
        <div data-testid="tweetText">Not Tibo.</div></article>'''
        rows=browser_posts(html);self.assertEqual([r.external_id for r in rows],['123'])
        self.assertEqual(rows[0].source_kind,'x_browser')

    def test_only_new_opt_in_scheduler_job_added(self):
        old=create_scheduler(now=NOW);new=create_scheduler(now=NOW,tibo_config=TiboConfig())
        self.assertEqual({j.id for j in new.get_jobs()}-{j.id for j in old.get_jobs()},{'tibo_monitor','tibo_settings_sync'})
        for job in old.get_jobs():self.assertEqual(str(job.trigger),str(new.get_job(job.id).trigger))
        self.assertEqual(new.get_job('tibo_monitor').trigger.interval.total_seconds(),7200)
        self.assertEqual(new.get_job('tibo_monitor').trigger.start_date,NOW+timedelta(hours=2))

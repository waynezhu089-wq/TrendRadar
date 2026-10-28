import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app
from app.monitors import tibo_settings as preferences
from app.commands.run_scheduler import create_scheduler, sync_tibo_schedule

NOW = datetime(2026, 10, 23, 7, tzinfo=timezone.utc)


class SubscriptionSettingsTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.config = Path(directory.name) / 'config.json'
        self.runtime = Path(directory.name) / 'runtime.json'
        self.values = {'account':'thsottiaux', 'enabled':True, 'browser_enabled':True,
                       'poll_minutes':5, 'retained':'unchanged'}
        self.config.write_text(json.dumps(self.values), encoding='utf-8')
        for name, value in [('CONFIG_PATH',self.config), ('RUNTIME_PATH',self.runtime)]:
            patched = patch.object(preferences, name, value)
            patched.start(); self.addCleanup(patched.stop)

    def test_default_and_saved_interval_are_loaded(self):
        self.assertEqual(preferences.TiboConfig().poll_minutes,120)
        self.assertEqual(preferences.load_tibo_config().poll_minutes,5)
        preferences.save_poll_minutes(120)
        self.assertEqual(preferences.load_tibo_config().poll_minutes,120)
        self.assertTrue(preferences.load_tibo_config().browser_enabled)
        self.assertEqual(json.loads(self.config.read_text()),self.values | {'poll_minutes':120})

    def test_invalid_config_is_not_scheduled(self):
        for value in [True,'120',0,-1,999999,None]:
            self.config.write_text(json.dumps(self.values | {'poll_minutes':value}),encoding='utf-8')
            self.assertIsNone(preferences.load_tibo_config())

    def test_save_and_get_are_preferences_only(self):
        with patch('app.monitors.tibo.poll_tibo') as poll, \
             patch('app.monitors.tibo.FeishuWebhookSender') as send, \
             patch('app.monitors.tibo.OpenAICompatibleClient') as model:
            client = TestClient(app)
            response = client.post('/api/v1/tibo-monitor/settings',json={'poll_minutes':120})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['poll_minutes'],120)
            self.assertTrue(response.json()['pending'])
            self.assertFalse(response.json()['scheduler_connected'])
            self.assertEqual(client.get('/api/v1/tibo-monitor/settings').json()['poll_minutes'],120)
            poll.assert_not_called(); send.assert_not_called(); model.assert_not_called()

    def test_invalid_api_requests_do_not_write(self):
        original = self.config.read_bytes()
        client = TestClient(app)
        for value in [True,'120',5,121,0,-1,1.5,None]:
            self.assertEqual(client.post('/api/v1/tibo-monitor/settings',
                                        json={'poll_minutes':value}).status_code,422)
        self.assertEqual(client.post('/api/v1/tibo-monitor/settings',
                                    json={'poll_minutes':120,'enabled':False}).status_code,422)
        self.assertEqual(self.config.read_bytes(),original)

    def test_failed_atomic_replace_preserves_previous_config(self):
        original=self.config.read_bytes()
        with patch.object(preferences.os,'replace',side_effect=OSError):
            self.assertEqual(TestClient(app).post('/api/v1/tibo-monitor/settings',
                                                 json={'poll_minutes':120}).status_code,409)
        self.assertEqual(self.config.read_bytes(),original)
        self.assertFalse(list(self.config.parent.glob('*.tmp')))

    def test_live_reschedule_does_not_run_jobs_or_change_other_triggers(self):
        scheduler=create_scheduler(now=NOW,tibo_config=preferences.TiboConfig(poll_minutes=5))
        old={job.id:str(job.trigger) for job in scheduler.get_jobs() if job.id!='tibo_monitor'}
        preferences.save_poll_minutes(120)
        with patch('app.monitors.tibo.poll_tibo') as poll, patch('apscheduler.schedulers.base.datetime') as clock:
            clock.now.return_value=NOW
            sync_tibo_schedule(scheduler,now=NOW,runtime_path=self.runtime)
            poll.assert_not_called()
        job=scheduler.get_job('tibo_monitor')
        self.assertEqual(job.trigger.interval,timedelta(hours=2))
        self.assertEqual(job.trigger.start_date,NOW+timedelta(hours=2))
        for ident, trigger in old.items():self.assertEqual(str(scheduler.get_job(ident).trigger),trigger)
        status=preferences.settings_status(now=NOW)
        self.assertEqual(status['applied_poll_minutes'],120)
        self.assertEqual(status['next_run_time'],(NOW+timedelta(hours=2)).isoformat())
        self.assertFalse(status['pending'])
        # Re-reading preferences must not keep postponing the next poll.
        sync_tibo_schedule(scheduler,now=NOW+timedelta(seconds=30),runtime_path=self.runtime)
        self.assertEqual(job.trigger.start_date,NOW+timedelta(hours=2))
        self.assertFalse(preferences.settings_status(now=NOW+timedelta(minutes=3))['scheduler_connected'])

    def test_pending_runtime_is_not_reported_as_applied(self):
        preferences.save_poll_minutes(120)
        preferences.atomic_json(self.runtime,{'poll_minutes':5,'updated_at':NOW.isoformat(),
                                              'next_run_time':(NOW+timedelta(minutes=5)).isoformat()})
        status=preferences.settings_status(now=NOW)
        self.assertTrue(status['pending']);self.assertEqual(status['applied_poll_minutes'],5)

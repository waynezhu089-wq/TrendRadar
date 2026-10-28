import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.commands import run_scheduler
from app.commands.scheduler_lock import scheduler_instance_lock


class SchedulerLockTests(unittest.TestCase):
    def test_second_long_running_instance_exits_before_database_or_jobs(self):
        output = io.StringIO()
        with (patch.object(run_scheduler, "scheduler_instance_lock") as lock,
              patch.object(run_scheduler, "initialize_database") as database,
              patch.object(run_scheduler, "create_scheduler") as scheduler,
              contextlib.redirect_stdout(output)):
            lock.return_value.__enter__.return_value = False
            self.assertEqual(run_scheduler.main([]), 2)
        self.assertIn("SCHEDULER_ALREADY_RUNNING", output.getvalue())
        database.assert_not_called()
        scheduler.assert_not_called()

    def test_os_lock_blocks_second_process_and_recovers_after_kill(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "scheduler.lock"
            child_code = (
                "import sys,time; from pathlib import Path; "
                "from app.commands.scheduler_lock import scheduler_instance_lock; "
                "exec('with scheduler_instance_lock(Path(sys.argv[1])) as acquired:\\n"
                " print(acquired,flush=True)\\n time.sleep(60)')"
            )
            process = subprocess.Popen([sys.executable, "-u", "-c", child_code, str(path)],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True)
            try:
                self.assertEqual(process.stdout.readline().strip(), "True")
                with scheduler_instance_lock(path) as acquired:
                    self.assertFalse(acquired)
            finally:
                process.kill()
                process.communicate(timeout=5)
            self.assertEqual(path.read_bytes(), b"")
            with scheduler_instance_lock(path) as recovered:
                self.assertTrue(recovered)

    def test_one_shot_does_not_acquire_resident_lock(self):
        with (patch.object(run_scheduler, "scheduler_instance_lock") as lock,
              patch.object(run_scheduler, "initialize_database"),
              patch.object(run_scheduler, "run_feishu_brief_job",
                           return_value={"status": "SKIP_ALREADY_SENT_TODAY"}) as brief,
              contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(run_scheduler.main(["--once-brief"]), 0)
        lock.assert_not_called()
        brief.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

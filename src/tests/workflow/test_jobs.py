import datetime
from collections import namedtuple

from unittest import TestCase, mock

from gobworkflow.workflow.jobs import job_start, job_end, step_start, step_end

Job = namedtuple("Job", ["id"])
Step = namedtuple("Job", ["id"])


class TestJobManagement(TestCase):

    def setUp(self):
        pass

    @mock.patch("gobworkflow.workflow.jobs.job_save")
    def test_job_start(self, job_save):
        job_save.return_value = Job("any id")
        job = job_start("any job", {"header": {}, "a": 1, "b": "string", "c": True})
        self.assertEqual(job["name"], "any job.1.string.True")
        self.assertEqual(job["type"], "any job")
        self.assertEqual(job["args"], ["1", "string", "True"])
        self.assertIsInstance(job["start"], datetime.datetime)
        self.assertIsNone(job["end"])
        self.assertEqual(job["status"], "started")

    @mock.patch("gobworkflow.workflow.jobs.job_update", mock.MagicMock())
    def test_job_end(self):
        job = job_end({"jobid": "any jobid"})
        self.assertEqual(job["id"], "any jobid")
        self.assertIsInstance(job["end"], datetime.datetime)
        self.assertEqual(job["status"], "ended")

    @mock.patch("gobworkflow.workflow.jobs.job_update", mock.MagicMock())
    def test_job_end_missing_id(self):
        job = job_end({})
        self.assertIsNone(job)

    @mock.patch("gobworkflow.workflow.jobs.step_save")
    def test_step_start(self, step_save):
        step_save.return_value = Step("any id")
        step = step_start("any step", {})
        self.assertEqual(step["name"], "any step")
        self.assertIsInstance(step["start"], datetime.datetime)
        self.assertIsNone(step["end"])
        self.assertEqual(step["status"], "started")

    @mock.patch("gobworkflow.workflow.jobs.step_update", mock.MagicMock())
    def test_step_end(self):
        step = step_end({"stepid": "any stepid"})
        self.assertIsInstance(step["end"], datetime.datetime)
        self.assertEqual(step["status"], "ended")

    @mock.patch("gobworkflow.workflow.jobs.step_update", mock.MagicMock())
    def test_step_end_missing_id(self):
        step = step_end({})
        self.assertIsNone(step)
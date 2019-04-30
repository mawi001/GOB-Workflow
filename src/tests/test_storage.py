from unittest import TestCase, mock

from sqlalchemy.exc import DBAPIError

from gobcore.model.sa.management import Job, JobStep

import gobworkflow.storage

from gobworkflow.storage.storage import connect, disconnect, is_connected
from gobworkflow.storage.storage import save_log, get_services, remove_service, mark_service_dead, update_service, _update_tasks
from gobworkflow.storage.storage import job_save, job_update, step_save, step_update, get_job_step

class MockedService:

    service_id = None
    id = None
    host = None
    name = None

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class MockedSession:

    def __init__(self):
        self._first = None
        self._add = None
        self._delete = None
        self._all = []
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def execute(self):
        pass

    def query(self, anyClass):
        return self

    def get(self, arg):
        return arg

    def filter_by(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._all

    def first(self):
        return self._first

    def add(self, anyObject):
        self._add = anyObject
        return self

    def delete(self, anyObject=None):
        self._delete = anyObject
        return self

    def commit(self):
        pass

class MockedEngine:

    def dispose(self):
        pass

    def execute(self, stmt):
        self.stmt = stmt

class MockException(Exception):
    pass

def raise_exception(e):
    raise e("Raised")

class TestStorage(TestCase):

    def setUp(self):
        gobworkflow.storage.storage.engine = MockedEngine()
        gobworkflow.storage.storage.session = MockedSession()

    def test_update_service(self):
        mockedSession = MockedSession()
        gobworkflow.storage.storage.session = mockedSession
        gobworkflow.storage.storage.Service = MockedService
        gobworkflow.storage.storage.ServiceTask = MockedService

        service = {
            "name": "AnyService",
            "host": "AnyHost",
            "pid": 123,
            "is_alive": True,
            "timestamp": "timestamp"
        }

        # If the service is not found, it should be added
        mockedSession._first = None
        update_service(service, [])
        self.assertEqual(mockedSession._add.name, "AnyService")

        # If the service is found, it should be updated
        mockedSession._first = MockedService(**{"name": "AnyService", "is_alive": None, "timestamp": None})
        update_service(service, [])
        self.assertEqual(mockedSession._first.is_alive, service["is_alive"])

    @mock.patch("gobworkflow.storage.storage.alembic.config")
    @mock.patch("gobworkflow.storage.storage.create_engine")
    def test_connect(self, mock_create, mock_alembic):
        mock_alembic.main = mock.MagicMock()

        result = connect()

        mock_create.assert_called()
        mock_alembic.main.assert_called()
        self.assertEqual(result, True)
        self.assertEqual(is_connected(), True)

    @mock.patch("gobworkflow.storage.storage.DBAPIError", MockException)
    @mock.patch("gobworkflow.storage.storage.create_engine", mock.MagicMock())
    @mock.patch("gobworkflow.storage.storage.alembic.config")
    def test_connect_error(self, mock_alembic):
        # Operation errors should be catched
        mock_alembic.main = lambda argv: raise_exception(MockException)

        result = connect()

        self.assertEqual(result, False)
        self.assertEqual(is_connected(), False)

    @mock.patch("gobworkflow.storage.storage.alembic.config")
    @mock.patch("gobworkflow.storage.storage.create_engine", mock.MagicMock())
    def test_connect_other_error(self, mock_alembic):
        # Only operational errors should be catched
        mock_alembic.main = lambda argv: raise_exception(MockException)

        with self.assertRaises(MockException):
            connect()

    @mock.patch("gobworkflow.storage.storage.engine.dispose")
    @mock.patch("gobworkflow.storage.storage.session.close")
    @mock.patch("gobworkflow.storage.storage.session.rollback")
    def test_disconnect(self, mock_rollback, mock_close, mock_dispose):

        disconnect()

        mock_rollback.assert_called()
        mock_close.assert_called()
        mock_dispose.assert_called()

        self.assertEqual(gobworkflow.storage.storage.session, None)
        self.assertEqual(gobworkflow.storage.storage.engine, None)
        self.assertEqual(is_connected(), False)

    @mock.patch("gobworkflow.storage.storage.DBAPIError", MockException)
    @mock.patch("gobworkflow.storage.storage.engine.dispose", lambda: raise_exception(MockException))
    @mock.patch("gobworkflow.storage.storage.session.close", mock.MagicMock())
    @mock.patch("gobworkflow.storage.storage.session.rollback", mock.MagicMock())
    def test_disconnect_operational_error(self):
        # Operation errors should be catched

        disconnect()

        self.assertEqual(gobworkflow.storage.storage.session, None)
        self.assertEqual(gobworkflow.storage.storage.engine, None)

    @mock.patch("gobworkflow.storage.storage.engine.dispose", lambda: raise_exception(MockException))
    @mock.patch("gobworkflow.storage.storage.session.close", mock.MagicMock())
    @mock.patch("gobworkflow.storage.storage.session.rollback", mock.MagicMock())
    def test_disconnect_other_error(self):
        # Only operational errors should be catched

        with self.assertRaises(MockException):
            disconnect()

    def test_is_connected_not_ok(self):
        result = is_connected()
        self.assertEqual(result, False)

    @mock.patch("gobworkflow.storage.storage.session.execute", mock.MagicMock())
    def test_is_connected_ok(self):
        result = is_connected()
        self.assertEqual(result, True)

    @mock.patch("gobworkflow.storage.storage.session.add")
    @mock.patch("gobworkflow.storage.storage.session.commit")
    def test_save_log(self, mock_commit, mock_add):
        msg = {
            "timestamp": "2020-06-20T12:20:20.000"
        }

        save_log(msg)

        mock_add.assert_called_with(mock.ANY)
        mock_commit.assert_called_with()

    def test_update_tasks(self):
        gobworkflow.storage.storage.Service = MockedService
        gobworkflow.storage.storage.ServiceTask = MockedService

        mockedSession = MockedSession()
        gobworkflow.storage.storage.session = mockedSession
        # No action on empty lists
        _update_tasks(MockedService(), tasks=[])
        self.assertEqual(mockedSession._add, None)
        self.assertEqual(mockedSession._delete, None)

        mockedSession = MockedSession()
        gobworkflow.storage.storage.session = mockedSession
        # add task when not yet exists
        _update_tasks(MockedService(), tasks=[{"name": "AnyTask"}])
        self.assertEqual(mockedSession._add.name, "AnyTask")

        mockedSession = MockedSession()
        gobworkflow.storage.storage.session = mockedSession
        # delete task when it no longer exists
        _update_tasks(MockedService(), tasks=[])
        self.assertEqual(mockedSession._delete, None)

        mockedSession = MockedSession()
        gobworkflow.storage.storage.session = mockedSession
        mocked_task = MockedService(**{"name": "AnyTask", "is_alive": None})
        other_task = MockedService(**{"name": "AnyTask2", "is_alive": None})
        # update task
        mockedSession._all = [mocked_task, other_task]
        _update_tasks(MockedService(), tasks=[{"name": "AnyTask", "is_alive": True}])
        self.assertEqual(mocked_task.is_alive, True)

    def test_get_services(self):
        mockedSession = MockedSession()
        gobworkflow.storage.storage.session = mockedSession
        services = get_services()
        self.assertEqual(services, [])

    @mock.patch("gobworkflow.storage.storage._update_tasks")
    def test_mark_as_dead(self, mock_update_tasks):
        mockedSession = MockedSession()
        gobworkflow.storage.storage.session = mockedSession

        mockedService = MockedService()
        mark_service_dead(mockedService)

        self.assertEqual(mockedService.is_alive, False)
        mock_update_tasks.assert_called_with(mockedService, [])

    def test_remove_service(self):
        mockedSession = MockedSession()
        gobworkflow.storage.storage.session = mockedSession

        mockedService = MockedService()
        remove_service(mockedService)

        self.assertEqual(mockedSession._delete, None)

    def test_job_save(self):
        result = job_save({"name": "any name"})
        self.assertIsInstance(result, Job)
        self.assertEqual(result.name, "any name")

    def test_job_update(self):
        mockedSession = MockedSession()
        gobworkflow.storage.storage.session = mockedSession
        mockedSession.get = lambda id: Job()

        result = job_update({"id": 123})
        self.assertIsInstance(result, Job)
        self.assertEqual(result.id, 123)

    def test_step_save(self):
        result = step_save({"name": "any name"})
        self.assertIsInstance(result, JobStep)
        self.assertEqual(result.name, "any name")

    def test_step_update(self):
        mockedSession = MockedSession()
        gobworkflow.storage.storage.session = mockedSession
        mockedSession.get = lambda id: JobStep()

        result = step_update({"id": 123})
        self.assertIsInstance(result, JobStep)
        self.assertEqual(result.id, 123)

    def test_get_job_step(self):
        mockedSession = MockedSession()
        gobworkflow.storage.storage.session = mockedSession
        job, step = get_job_step(1, 2)
        self.assertEqual(job, 1)
        self.assertEqual(step, 2)

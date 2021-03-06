"""Storage

This module encapsulates the GOB Management storage.
"""
import datetime
import json

from alembic.runtime import migration
import alembic.config
import alembic.script

from sqlalchemy import create_engine, or_, and_
from sqlalchemy.exc import DBAPIError
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import Session

from gobcore.typesystem.json import GobTypeJSONEncoder

from gobcore.model.sa.management import Base, Job, JobStep, Log, Service, ServiceTask, Task, AuditLog

from gobworkflow.config import GOB_MGMT_DB
from gobworkflow.storage.auto_reconnect_wrapper import auto_reconnect_wrapper

session = None
engine = None


def connect(force_migrate=False):
    """Module initialisation

    The connection with the underlying storage is initialised.
    Meta information is available via the Base variale.
    Data retrieval is facilitated via the session object

    :return: True when the connection has been established
    """
    global session, engine

    try:
        engine = create_engine(URL(**GOB_MGMT_DB))

        migrate_storage(force_migrate)

        # Declarative base model to create database tables and classes
        Base.metadata.bind = engine

        session = Session(engine)
    except DBAPIError as e:
        # Catch any connection errors
        print(f"Connect failed: {str(e)}")
        disconnect()  # Cleanup

    return is_connected()


def migrate_storage(force_migrate):
    """
    Migrate storage to latest version.

    In order to prevent that multiple instances will migrate at the same time
    and to prevent migration locks, access to this method is normally acquired
    by a lock.

    This method will always unlock the lock, even if a lock has not been set.
    When using the force_migrate option the lock is passed and any open lock will be released

    The reason for setting the lock is to prevent multiple migrations that might lock each other
    :return:
    """
    MIGRATION_LOCK = 248517090  # Just some random number

    if not force_migrate:
        # Don't force
        # Nicely wait for any migrations to finish before continuing
        engine.execute(f"SELECT pg_advisory_lock({MIGRATION_LOCK})")

    try:
        # Check if storage is up-to-date
        alembic_cfg = alembic.config.Config('alembic.ini')
        script = alembic.script.ScriptDirectory.from_config(alembic_cfg)
        with engine.begin() as conn:
            context = migration.MigrationContext.configure(conn)
            up_to_date = context.get_current_revision() == script.get_current_head()

        if not up_to_date:
            print('Migrating storage')
            alembicArgs = [
                '--raiseerr',
                'upgrade', 'head',
            ]
            alembic.config.main(argv=alembicArgs)
    except Exception as e:
        print(f'Storage migration failed: {str(e)}')
    else:  # No exception
        print('Storage is up-to-date')

    # Always unlock
    engine.execute(f"SELECT pg_advisory_unlock({MIGRATION_LOCK})")


def disconnect():
    """Disconnect from the database

    Cancel any running transactions and close the session and engine

    :return: None
    """
    global engine, session

    try:
        if session is not None:
            session.rollback()
            session.close()
        if engine is not None:
            engine.dispose()
    except DBAPIError as e:
        # Catch any connection errors
        print(f"Disconnect failed: {str(e)}")
    finally:
        engine = None
        session = None


def is_connected():
    """Is connected

    Tells whether the database connection is alive

    A simple statement is executed to test if the database communication is OK

    :return: True when the database connection is OK
    """
    if engine is None or session is None:
        return False
    else:
        try:
            session.execute("SELECT 1")
            return True
        except Exception:
            return False


# Create a wrapper to protect database functions against connection loss
# Any failed operation will automatically be retried when the connection becomes available again
session_auto_reconnect = auto_reconnect_wrapper(is_connected=is_connected, connect=connect, disconnect=disconnect)


@session_auto_reconnect
def save_log(msg):
    # Encode the json data
    json_data = json.dumps(msg.get('data', None), cls=GobTypeJSONEncoder)

    # Create the log record
    record = Log(
        timestamp=datetime.datetime.strptime(msg['timestamp'], '%Y-%m-%dT%H:%M:%S.%f'),
        process_id=msg.get('process_id', None),
        source=msg.get('source', None),
        application=msg.get('application', None),
        destination=msg.get('destination', None),
        catalogue=msg.get('catalogue', None),
        entity=msg.get('entity', None),
        level=msg.get('level', None),
        name=msg.get('name', None),
        msgid=msg.get('id', None),
        msg=msg.get('msg', None),
        jobid=msg.get('jobid', None),
        stepid=msg.get('stepid', None),
        data=json_data,
    )
    session.add(record)
    session.commit()


@session_auto_reconnect
def save_audit_log(msg):
    record = AuditLog(
        timestamp=datetime.datetime.strptime(msg['timestamp'], '%Y-%m-%dT%H:%M:%S.%f'),
        source=msg.get('source'),
        destination=msg.get('destination'),
        type=msg.get('type'),
        data=msg.get('data'),
        request_uuid=msg.get('request_uuid'),
    )
    session.add(record)
    session.commit()


@session_auto_reconnect
def get_services():
    """Get services

    :return: All current services (alive or dead)
    """
    return session.query(Service).all()


@session_auto_reconnect
def mark_service_dead(service):
    """Mark a service as not being alive anymore

    :param service: the service to mark as dead
    :return: None
    """
    # mark as dead
    service.is_alive = False
    # remove any tasks
    _update_servicetasks(service, [])

    session.commit()


@session_auto_reconnect
def remove_service(service):
    """Remove a service

    :param service: the servie to remove
    :return: None
    """
    # remove any tasks
    _update_servicetasks(service, [])
    # remove service
    session.query(Service) \
        .filter(Service.host == service.host) \
        .filter(Service.name == service.name) \
        .delete()

    session.commit()


@session_auto_reconnect
def update_service(service, tasks):
    """Update service state in storage

    :param service:
    :param tasks:
    :return: None
    """
    # Get the current service or create it if not yet exists
    current = session.query(Service)\
        .filter(or_(Service.host == service["host"], Service.host == None))\
        .filter(Service.name == service["name"])\
        .first()  # noqa: E711

    if current:
        current.is_alive = service["is_alive"]
        current.timestamp = service["timestamp"]
        current.host = service["host"]
        current.pid = service["pid"]
    else:
        current = Service(**service)
        session.add(current)
        session.commit()

    # Update status with current tasks
    _update_servicetasks(current, tasks)

    session.commit()


@session_auto_reconnect
def _update_servicetasks(service, tasks):
    """Update tasks

    Delete all current tasks that are not in tasks
    Update or add all taska with the current status

    :param current_tasks:
    :param tasks:
    :return:
    """
    # Update db and refresh model
    session.commit()

    # Remove any dangling tasks
    session.query(ServiceTask).filter(ServiceTask.service_id == None).delete()  # noqa: E711
    session.commit()

    # Get currently registered tasks for the service
    current_tasks = session.query(ServiceTask).filter(ServiceTask.service_id == service.id).all()

    # Delete tasks that have ended
    for task in current_tasks:
        matches = [t for t in tasks if t["name"] == task.name]
        if len(matches) == 0:
            session.delete(task)
            session.commit()

    # Add or update tasks that are active
    for task in tasks:
        matches = [t for t in current_tasks if t.name == task["name"]]
        if len(matches) == 0:
            task = ServiceTask(**task)
            task.service_id = service.id
            session.add(task)
        else:
            matches[0].is_alive = task["is_alive"]

    # Commit is done by the caller


@session_auto_reconnect
def job_get(job_id):
    """Returns task with task_id

    :param task_id:
    :return:
    """
    # Force fetching latest job
    session.commit()
    return session.query(Job).get(job_id)


@session_auto_reconnect
def job_runs(jobinfo):
    job = session.query(Job)\
        .filter(Job.id != jobinfo['id'])\
        .filter(Job.name == jobinfo['name'])\
        .filter(Job.end == None)\
        .order_by(Job.start.desc())\
        .first()  # noqa E711 (== None)
    if job is None:
        return False
    else:
        # Consider jobs of less than 12 hours old as still running
        duration = datetime.datetime.now() - job.start
        zombie = duration.total_seconds() >= (12 * 60 * 60)
        print("Found already running job", job.id, job.start, duration, zombie)
        return not zombie


@session_auto_reconnect
def job_save(job_info):
    """
    Create Job using the information in job_info and store it
    :param job_info: Job attributes
    :return: Job instance
    """
    job = Job(**job_info)
    session.add(job)
    session.commit()
    return job


@session_auto_reconnect
def job_update(job_info):
    """
    Update Job using the information in job_info
    :param job_info: Job attributes
    :return: Job instance
    """
    job = session.query(Job).get(job_info["id"])
    for key, value in job_info.items():
        setattr(job, key, value)
    session.commit()
    return job


@session_auto_reconnect
def step_save(step_info):
    """
    Create JobStep using the information in step_info and store it
    :param step_info: JobStep attributes
    :return: JobStep instance
    """
    step = JobStep(**step_info)
    session.add(step)
    session.commit()
    return step


@session_auto_reconnect
def step_update(step_info):
    """
    Update JobStep using the information in step_info
    :param step_info: JobStep attributes
    :return: JobStep instance
    """
    step = session.query(JobStep).get(step_info["id"])
    for key, value in step_info.items():
        setattr(step, key, value)
    session.commit()
    return step


@session_auto_reconnect
def task_get(task_id):
    """Returns task with task_id

    :param task_id:
    :return:
    """
    return session.query(Task).get(task_id)


@session_auto_reconnect
def task_save(task_info):
    """
    Create Task using the information in task_info and store it

    :param task_info:
    :return:
    """
    task = Task(**task_info)
    session.add(task)
    session.commit()
    return task


@session_auto_reconnect
def task_update(task_info):
    """
    Update JobStep using the information in step_info
    :param step_info: JobStep attributes
    :return: JobStep instance
    """
    task = session.query(Task).get(task_info["id"])
    for key, value in task_info.items():
        setattr(task, key, value)
    session.commit()
    return task


@session_auto_reconnect
def task_lock(task):
    """Places the current timestamp in the 'lock' attribute of the Task.

    :param task:
    :return:
    """
    step_cnt = session.query(Task).filter(and_(Task.id == task.id, Task.lock == None)) \
        .update({'lock': int(datetime.datetime.now().timestamp())})  # noqa: E711 (== None)
    session.commit()

    return step_cnt > 0


@session_auto_reconnect
def task_unlock(task):
    """Removes the lock from a Task

    :param task:
    :return:
    """
    step_cnt = session.query(Task).filter(and_(Task.id == task.id, Task.lock != None)) \
        .update({'lock': None})  # noqa: E711 (!= None)
    session.commit()
    assert step_cnt > 0, "Task was already unlocked. That can't be right."


@session_auto_reconnect
def get_tasks_for_stepid(stepid):
    """Returns all tasks for the given stepid

    :param stepid:
    :return:
    """
    return session.query(Task).filter_by(stepid=stepid).all()


@session_auto_reconnect
def get_job_step(jobid, stepid):
    """
    Retrieve the job and step for the given ids

    :param jobid: identification of the job
    :param stepid: identification of the step
    :return: Job and JobStep object for the given ids
    """
    job = session.query(Job).get(jobid)
    step = session.query(JobStep).get(stepid)
    return job, step

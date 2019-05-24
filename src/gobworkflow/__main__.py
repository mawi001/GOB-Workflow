"""Main workflow logic

The workflow manager subscribes to the workflow and log queues.

Log messages are simply printed (for now)
Workflow messages consist of proposals. A proposal is evaluated (for now always OK) and then routed as a request
to the service that can handle the proposal.

"""
from gobcore.status.heartbeat import STATUS_OK, STATUS_FAIL
from gobcore.message_broker.config import LOG_EXCHANGE, STATUS_EXCHANGE, HEARTBEAT_QUEUE, WORKFLOW_EXCHANGE
from gobcore.message_broker.config import RESULT_QUEUE
from gobcore.message_broker.messagedriven_service import messagedriven_service
from gobcore.logging.logger import logger

from gobworkflow.storage.storage import connect, save_log
from gobworkflow.workflow.jobs import step_status
from gobworkflow.workflow.workflow import Workflow
from gobworkflow.heartbeats import on_heartbeat
from gobworkflow.storage.storage import get_job_step


def handle_result(msg):
    """
    Handle the result of a message.
    Result messages are received via the result queue

    The message is matched with a step in a workflow and the result handling method
    of this workflow step is executed
    :param msg: The result message
    :return: None
    """
    # Retrieve the job and step from the message header
    header = msg['header']
    jobid = header['jobid']
    stepid = header['stepid']
    # Get the job and step from the database
    job, step = get_job_step(jobid, stepid)
    # Start the result handler method with the given message
    Workflow(job.type, step.name).handle_result()(msg)


def start_workflow(msg):
    """
    Start a workflow using the parameters that are contained in the message header

    :param msg: The message that will be used to start a workflow
    :return: None
    """
    # Retrieve the workflow parameters
    workflow_name = msg['workflow']['workflow_name']
    step_name = msg['workflow']['step_name']
    # Delete the parameters so that they do not get transferred in the workflow
    del msg['workflow']
    # Start the workflow with the given message
    Workflow(workflow_name, step_name).start(msg)


def on_workflow_progress(msg):
    """
    Process a workflow progress message

    The progress report is START, OK or FAIL
    :param msg: The message that contains the progress info
    :return: None
    """
    status = msg['status']
    step_info = step_status(msg['jobid'], msg['stepid'], status)
    if status in [STATUS_OK, STATUS_FAIL]:
        logger.configure(msg, "WORKFLOW")
        logger.info(f"Duration {str(step_info.end - step_info.start).split('.')[0]}")
        if status == STATUS_FAIL:
            logger.error(f"Program error: {msg['info_msg']}")
            logger.info(f"End of workflow")


SERVICEDEFINITION = {
    'step_completed': {
        'exchange': WORKFLOW_EXCHANGE,
        'queue': RESULT_QUEUE,
        'key': '*.result',
        'handler': handle_result
    },
    'start_workflow': {
        'exchange': WORKFLOW_EXCHANGE,
        'queue': RESULT_QUEUE,
        'key': 'workflow.start',
        'handler': start_workflow
    },
    'save_logs': {
        'exchange': LOG_EXCHANGE,
        'queue': 'gob.log.all',
        'key': '#',
        'handler': save_log
    },
    'heartbeat_monitor': {
        'exchange': STATUS_EXCHANGE,
        'queue': HEARTBEAT_QUEUE,
        'key': 'HEARTBEAT',
        'handler': on_heartbeat
    },
    'workflow_progress': {
        'exchange': STATUS_EXCHANGE,
        'queue': HEARTBEAT_QUEUE,
        'key': 'PROGRESS',
        'handler': on_workflow_progress
    },
}

connect()
params = {
    "prefetch_count": 1,
    "load_message": False
}
messagedriven_service(SERVICEDEFINITION, "Workflow", params)

import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from multi_agents.temporal.workflow import SupervisorWorkflow
from multi_agents.temporal.activities.run_supervisor import run_supervisor_activity
from multi_agents.utils.logger import setup_logger

logger = setup_logger()

TASK_QUEUE = "supervisor-task-queue"


async def run_worker_until_hitl(client: Client):
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SupervisorWorkflow],
        activities=[run_supervisor_activity],
    )
    async with worker:
        while True:
            await asyncio.sleep(2)
            workflows = [
                w
                async for w in client.list_workflows(
                    f'TaskQueue="{TASK_QUEUE}" AND ExecutionStatus="Running"'
                )
            ]
            pending = [w for w in workflows if not w.is_done()]
            if not pending:
                logger.info("No active workflows — worker shutting down.")
                break


async def start_agent(message: str, thread_id: str):
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SupervisorWorkflow],
        activities=[run_supervisor_activity],
    )

    async with worker:
        handle = await client.start_workflow(
            SupervisorWorkflow.run_workflow,
            args=[message, False, thread_id],
            id=thread_id,
            task_queue=TASK_QUEUE,
        )
        logger.info(f"Workflow started: {handle.id}")

        outcome = await handle.execute_update(
            SupervisorWorkflow.wait_until_hitl_or_done
        )
        logger.info(f"Outcome: {outcome} — shutting down worker.")

    logger.info("start_agent done — container can die now.")


async def resume_agent(thread_id: str, feedback: str):
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SupervisorWorkflow],
        activities=[run_supervisor_activity],
    )

    async with worker:
        handle = client.get_workflow_handle(thread_id)
        await handle.signal(SupervisorWorkflow.submit_feedback, feedback)
        logger.info(f"Signal sent to: {thread_id}")

        while True:
            await asyncio.sleep(2)
            workflows = [
                w
                async for w in client.list_workflows(
                    f'TaskQueue="{TASK_QUEUE}" AND ExecutionStatus="Running"'
                )
            ]
            if not workflows:
                logger.info("Workflow done — shutting down worker.")
                break

    logger.info("resume_agent done — container can die now.")


if __name__ == "__main__":
    import uuid

    thread_id = str(uuid.uuid4())

    # asyncio.run(
    #     resume_agent(
    #         "08fd3b0d-1ff9-45b1-b96b-89d420150d9f",
    #         "HITL Confirmation Status: Reorder Status is Approved (True) | Proceed sending the email even if the previous agent said false",
    #     )
    # )

    asyncio.run(
        start_agent("Start the inventory optimization task for today", thread_id)
    )

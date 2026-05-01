import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from multi_agents.temporal.workflow import SupervisorWorkflow
from multi_agents.temporal.activities.run_supervisor import run_supervisor_activity
from temporalio.client import WorkflowExecutionStatus

TASK_QUEUE = "supervisor-task-queue"


async def run_worker_until_hitl(client: Client):
    """Worker runs until workflow suspends at HITL, then exits."""
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
                print("No active workflows — worker shutting down.")
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
        print(f"Workflow started: {handle.id}")

        while True:
            await asyncio.sleep(1)
            desc = await handle.describe()

            if desc.status == WorkflowExecutionStatus.COMPLETED:
                print("Workflow completed — shutting down.")
                break

            in_hitl = await handle.query(SupervisorWorkflow.get_hitl_status)
            if in_hitl:
                print("HITL triggered — shutting down worker.")
                break

    print("start_agent done — container can die now.")


async def resume_agent(thread_id: str, feedback: str):
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SupervisorWorkflow],
        activities=[run_supervisor_activity],
    )

    async with worker:
        # Worker alive FIRST, then send signal
        handle = client.get_workflow_handle(thread_id)
        await handle.signal(SupervisorWorkflow.submit_feedback, feedback)
        print(f"Signal sent to: {thread_id}")

        while True:
            await asyncio.sleep(2)
            workflows = [
                w
                async for w in client.list_workflows(
                    f'TaskQueue="{TASK_QUEUE}" AND ExecutionStatus="Running"'
                )
            ]
            if not workflows:
                print("Workflow done — shutting down worker.")
                break

    print("resume_agent done — container can die now.")


#
if __name__ == "__main__":
    asyncio.run(
        resume_agent(
            "234",
            "HITL Confirmation Status: Order Approved | Proceed sending the email",
        )
    )

# if __name__ == "__main__":
#     asyncio.run(start_agent("Start the inventory optimization task for today", "234"))

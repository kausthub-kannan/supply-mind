import asyncio
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker

from multi_agents.temporal.activities.run_supervisor import run_supervisor_activity
from multi_agents.temporal.workflow import SupervisorWorkflow


async def main():
    client = await Client.connect("localhost:7233")

    async with Worker(
        client,
        task_queue="supervisor-task-queue",
        workflows=[SupervisorWorkflow],
        activities=[run_supervisor_activity],
    ):
        # Start the workflow
        # handle = await client.start_workflow(
        #     SupervisorWorkflow.run_workflow,
        #     args=["Start the inventory optimization task for today", True],
        #     id="supervisor-workflow-id-2",
        #     task_queue="supervisor-task-queue",
        #     execution_timeout=timedelta(minutes=10),
        # )
        #
        # print(f"Workflow started: {handle.id}")

        handle = client.get_workflow_handle("supervisor-workflow-id-2")
        await handle.signal(
            SupervisorWorkflow.submit_feedback,
            "I approve the order, please go ahead and apply the order",
        )
        result = await handle.result()
        print(f"Workflow result: {result}")

        result = await handle.result()
        print(f"Workflow result: {result}")


if __name__ == "__main__":
    asyncio.run(main())

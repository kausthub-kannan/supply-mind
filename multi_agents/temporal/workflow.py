from datetime import timedelta
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from multi_agents.temporal.activities.run_supervisor import run_supervisor_activity


@workflow.defn
class SupervisorWorkflow:
    def __init__(self):
        self._human_feedback = None
        self._in_hitl = False

    @workflow.update
    async def wait_until_hitl_or_done(self) -> str:
        await workflow.wait_condition(
            lambda: self._in_hitl or self._human_feedback is not None
        )
        return "hitl" if self._in_hitl else "done"

    @workflow.signal
    def submit_feedback(self, feedback: str):
        self._in_hitl = False
        self._human_feedback = feedback

    @workflow.run
    async def run_workflow(self, message: str, in_hitl: bool, thread_id: str):
        result = await workflow.execute_activity(
            run_supervisor_activity,
            {"message": message, "in_hitl": in_hitl, "thread_id": thread_id},
            start_to_close_timeout=timedelta(minutes=5),
        )

        if result.get("in_hitl"):
            self._in_hitl = True
            await workflow.wait_condition(lambda: self._human_feedback is not None)
            self._in_hitl = False

            result = await workflow.execute_activity(
                run_supervisor_activity,
                {"human_feedback": self._human_feedback, "thread_id": thread_id},
                start_to_close_timeout=timedelta(minutes=5),
            )

        return result

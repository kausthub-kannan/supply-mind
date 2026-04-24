from langgraph.types import Command
from temporalio import activity
from multi_agents.agents.supervisor import supervisor_agent
from multi_agents.utils.logger import setup_logger


@activity.defn
async def run_supervisor_activity(input_data: dict) -> dict:
    logger = setup_logger(use_agentops=True)

    config = {"configurable": {"thread_id": input_data["thread_id"]}}

    if input_data.get("human_feedback"):
        result = await supervisor_agent.ainvoke(
            Command(resume={"feedback": input_data["human_feedback"]}), config
        )
    else:

        result = await supervisor_agent.ainvoke(
            {
                "notification_message": input_data["message"],
                "in_hitl": input_data["in_hitl"],
                "workflow_id": input_data["thread_id"],
            },
            config,
        )

    state = await supervisor_agent.aget_state(config)
    is_interrupted = len(state.tasks) > 0 and any(t.interrupts for t in state.tasks)

    return {"output": result, "in_hitl": is_interrupted}

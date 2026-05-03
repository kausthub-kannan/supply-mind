from langchain_core.messages import SystemMessage, HumanMessage
from multi_agents.utils.llm_inference import get_model
from multi_agents.utils.logger import setup_logger

logger = setup_logger()


def summarizer(system_prompt, content):
    model = get_model("mistral-medium")
    result = model.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=content)]
    ).content
    return result

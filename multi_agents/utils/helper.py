from langchain_core.messages import SystemMessage, HumanMessage
from multi_agents.utils.llm_inference import get_model

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def summarizer(system_prompt, content):
    model = get_model("mistral-medium")
    result = model.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=content)]
    ).content
    return result

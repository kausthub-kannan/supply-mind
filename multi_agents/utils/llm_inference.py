import os
from langchain_openai import ChatOpenAI
import agentops

agentops.init()


def get_model(model_name, tools=None, temperature=0):
    return ChatOpenAI(
        model=model_name,
        base_url=os.getenv("LITELLM_API_URI"),
        api_key=os.getenv("LITELLM_API_KEY"),
        temperature=temperature,
        max_retries=8,
    ).bind_tools(tools=tools if tools else [])

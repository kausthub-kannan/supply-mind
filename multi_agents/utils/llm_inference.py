import os
from langchain_openai import ChatOpenAI

def get_model(model_name, temperature=0.7):
    return ChatOpenAI(
        model=model_name,
        base_url=os.getenv("LITELLM_API_URI"),
        api_key=os.getenv("LITELLM_API_KEY"),
        temperature=temperature
    )
import os
from langchain_openai import ChatOpenAI

model = ChatOpenAI(
    model="mistral-large",
    base_url=os.getenv("LITELLM_API_URI"),
    api_key=os.getenv("LITELLM_API_KEY")
)
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class OpenAIClient:
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        api_base = os.environ.get("OPENAI_API_BASE")
        
        if not api_key:
            raise ValueError("未找到 OPENAI_API_KEY 环境变量")
        
        client_args = {"api_key": api_key}
        if api_base:
            client_args["base_url"] = api_base
        
        self.client = OpenAI(**client_args)
    
    def get_llm_response(self, messages, model="gpt-3.5-turbo", temperature=0.5):
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=2048,
            n=1,
            stream=False,
            top_p=0.99,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )
        
        return response.choices[0].message.content
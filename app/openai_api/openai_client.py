import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_DEFAULT_MODEL = os.environ.get("LLM_MODEL", "gpt-3.5-turbo")

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
    
    def get_llm_response(self, messages, model=None, temperature=0.5):
        model = model or _DEFAULT_MODEL
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=4096,
            n=1,
            stream=False,
            top_p=0.99,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            timeout=60.0  # 增加超时时间到 60s，防止复杂推理时超时
        )
        
        return response.choices[0].message.content

if __name__ == "__main__":
    client = OpenAIClient()
    print(client.get_llm_response([{"role": "user", "content": "你是什么模型"}]))

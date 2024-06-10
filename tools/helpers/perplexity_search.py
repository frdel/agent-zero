
import requests

from langchain.llms import BaseLLM # type: ignore
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.outputs.llm_result import LLMResult
from typing import List, Optional, Any
from openai import OpenAI
import os


api_key_from_env = os.getenv("API_KEY_PERPLEXITY")

class PerplexityCrewLLM(BaseLLM):
    api_key: str
    model_name: str

    def call_perplexity_ai(self, prompt: str) -> LLMResult:
        url = "https://api.perplexity.ai/chat/completions"

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "Be precise and concise."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "accept": "application/json",
            "content-type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)

        # Convert the response JSON to dictionary
        json_response = response.json()

        return json_response

    def _generate(self, prompts: List[str], stop: Optional[List[str]] = None,
                  run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> LLMResult:
        generations = []
        for prompt in prompts:
            generations.append([self._call(prompt, stop=stop, **kwargs)])
        return LLMResult.construct(generations=generations)

    def _call(self, prompt: str, stop: Optional[List[str]] = None, max_tokens: Optional[int] = None) -> LLMResult:
        response_data = self.call_perplexity_ai(prompt)
        model = LLMResult.construct(text=response_data['choices'][0]["message"]["content"]) # type: ignore

        return model

    @property
    def _llm_type(self) -> str:
        return "PerplexityAI"
    

def PerplexitySearchLLM(api_key,model_name="sonar-medium-online",base_url="https://api.perplexity.ai"):    
    client = OpenAI(api_key=api_key_from_env, base_url=base_url)
        
    def call_model(query:str):
        messages = [
        #It is recommended to use only single-turn conversations and avoid system prompts for the online LLMs (sonar-small-online and sonar-medium-online).
        
        # {
        #     "role": "system",
        #     "content": (
        #         "You are an artificial intelligence assistant and you need to "
        #         "engage in a helpful, detailed, polite conversation with a user."
        #     ),
        # },
        {
            "role": "user",
            "content": (
                query
            ),
        },
        ]
        
        response = client.chat.completions.create(
            model=model_name,
            messages=messages, # type: ignore
        )
        result = response.choices[0].message.content #only the text is returned
        return result
    
    return call_model


call_llm = PerplexitySearchLLM(api_key=api_key_from_env,model_name="sonar-medium-online")

def perplexity_search(search_query: str):
    return call_llm(search_query)
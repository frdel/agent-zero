
from openai import OpenAI
import models

def perplexity_search(query:str, model_name="llama-3.1-sonar-large-128k-online",api_key=None,base_url="https://api.perplexity.ai"):    
    api_key = api_key or models.get_api_key("perplexity")

    client = OpenAI(api_key=api_key, base_url=base_url)
        
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
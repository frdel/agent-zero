from openai import OpenAI
import models

def process_image(query: str, image_urls: list, model_name="gpt-4o-mini", api_key=None):
    
    api_key = api_key or models.get_api_key("openai")

    if not api_key:
        raise ValueError("The image processing tool requires an openai api key.")

    client = OpenAI(api_key=api_key)
    
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": query},
                *[
                    {"type": "image_url", "image_url": {"url": url}}
                    for url in image_urls
                ]
            ]
        }
    ]
    
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
    )
    
    result = response.choices[0].message.content  # only the text is returned
    
    return result
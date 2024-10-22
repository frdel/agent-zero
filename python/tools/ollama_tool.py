import json
import time
import requests
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get configuration from .env file
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.1')


class OllamaTool:
    def __init__(self):
        self.ollama_url = OLLAMA_URL
        self.ollama_model = OLLAMA_MODEL

    def make_api_call(self, messages, max_tokens, is_final_answer=False):
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.ollama_model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": 0.2
                        }
                    }
                )
                response.raise_for_status()
                return json.loads(response.json()["message"]["content"])
            except Exception as e:
                if attempt == 2:
                    if is_final_answer:
                        return {"title": "Error",
                                "content": f"Failed to generate final answer after 3 attempts. Error: {str(e)}"}
                    else:
                        return {"title": "Error", "content": f"Failed to generate step after 3 attempts. Error: {str(e)}",
                                "next_action": "final_answer"}
                time.sleep(1)  # Wait for 1 second before retrying

    def generate_response(self, prompt):
        messages = [
            {"role": "system", "content": """You are an expert AI assistant with advanced reasoning capabilities. Your task is to provide detailed, step-by-step explanations of your thought process. For each step:

1. Provide a clear, concise title describing the current reasoning phase.
2. Elaborate on your thought process in the content section.
3. Decide whether to continue reasoning or provide a final answer.

Response Format:
Use JSON with keys: 'title', 'content', 'next_action' (values: 'continue' or 'final_answer')

Key Instructions:
- Employ at least 5 distinct reasoning steps.
- Acknowledge your limitations as an AI and explicitly state what you can and cannot do.
- Actively explore and evaluate alternative answers or approaches.
- Critically assess your own reasoning; identify potential flaws or biases.
- When re-examining, employ a fundamentally different approach or perspective.
- Utilize at least 3 diverse methods to derive or verify your answer.
- Incorporate relevant domain knowledge and best practices in your reasoning.
- Quantify certainty levels for each step and the final conclusion when applicable.
- Consider potential edge cases or exceptions to your reasoning.
- Provide clear justifications for eliminating alternative hypotheses.


Example of a valid JSON response:
```json
{
    "title": "Initial Problem Analysis",
    "content": "To approach this problem effectively, I'll first break down the given information into key components. This involves identifying...[detailed explanation]... By structuring the problem this way, we can systematically address each aspect.",
    "next_action": "continue"
}```
"""}
        ]

        steps = []
        step_count = 1
        total_thinking_time = 0

        while True:
            start_time = time.time()
            step_data = self.make_api_call(messages, 300)
            end_time = time.time()
            thinking_time = end_time - start_time
            total_thinking_time += thinking_time

            steps.append((f"Step {step_count}: {step_data['title']}", step_data['content'], thinking_time))

            messages.append({"role": "assistant", "content": json.dumps(step_data)})

            if step_data['next_action'] == 'final_answer':
                break

            step_count += 1

            # Yield after each step for Streamlit to update
            yield steps, None  # We're not yielding the total time until the end

        # Generate final answer
        messages.append({"role": "user", "content": "Please provide the final answer based on your reasoning above."})

        start_time = time.time()
        final_data = self.make_api_call(messages, 200, is_final_answer=True)
        end_time = time.time()
        thinking_time = end_time - start_time
        total_thinking_time += thinking_time

        steps.append(("Final Answer", final_data['content'], thinking_time))

        yield steps, total_thinking_time

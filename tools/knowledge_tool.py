from agent import Agent
from . import online_knowledge_tool
from . import memory_tool
import concurrent.futures

def execute(agent, question, **kwargs):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Schedule the two functions to be run in parallel
        future_online = executor.submit(online_knowledge_tool.execute, agent, question)
        future_memory = executor.submit(memory_tool.execute, agent, question)

        # Wait for both functions to complete
        online_result = future_online.result()
        memory_result = future_memory.result()

    return f"# Online sources:\n{online_result}\n\n# Memory:\n{memory_result}"
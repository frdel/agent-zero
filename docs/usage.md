# Usage Guide

This guide explores more advanced usage scenarios for Agent Zero, building upon the basics covered in the Quick Start.

## Prompt Engineering

Effective prompt engineering is crucial for getting the most out of Agent Zero. Here are some tips and techniques:

* **Be Clear and Specific:** Clearly state your desired outcome.  The more specific you are, the better Agent Zero can understand and fulfill your request.  Avoid vague or ambiguous language.
* **Provide Context:** If necessary, provide background information or context to help the agent understand the task better. This might include relevant details, constraints, or desired format for the response.
* **Break Down Complex Tasks:**  For complex tasks, break them down into smaller, more manageable sub-tasks.  This makes it easier for the agent to reason through the problem and generate a solution.
* **Iterative Refinement:** Don't expect perfect results on the first try.  Experiment with different prompts, refine your instructions based on the agent's responses, and iterate until you achieve the desired outcome.
* **System-Level Instructions:** A custom prompts directory changes the agent's overall behavior.  You can copy the default files and modify them to give the agent specific instructions, biases, or constraints. The same goes for the tool files, that you can modify to give the agent specific instructions, biases, or constraints for each tool. See (architecture.md#prompts) for more information.

## Tool Usage

Agent Zero's power comes from its ability to use tools. Here's how to leverage them effectively:

* **Default Tools:** Agent Zero typically includes default tools like web search, memory access, code execution, and communication.  Understand the capabilities of these tools and how to invoke them.
* **Creating Custom Tools:**  Extend Agent Zero's functionality by creating your own custom tools.  Refer to the (link to section on custom tool creation if available) for detailed instructions.
* **Tool Arguments:**  Provide the necessary arguments to the tools.  Agent Zero expects tools to be invoked with a JSON-formatted string containing the tool name and arguments.  Refer to the Quick Start and example prompts for how to format tool calls.

## Multi-Agent Cooperation

One of Agent Zero's unique features is multi-agent cooperation.

* **Creating Sub-Agents:** Agents can create sub-agents to delegate sub-tasks.  This helps manage complexity and distribute workload.
* **Communication:** Agents can communicate with each other, sharing information and coordinating actions. The system prompt and message history play a key role in guiding this communication.
* **Hierarchy:** Agent Zero uses a hierarchical structure, with superior agents delegating tasks to subordinates.  This allows for structured problem-solving and efficient resource allocation.

## Customizing Agent Behavior

* **System Prompt:**  The core of Agent Zero's behavior is defined in the system prompt.  Experiment with different system prompts to customize the agent's personality, biases, and reasoning approach.
* **Prompts Directory:** The `prompts` directory contains various prompt templates used by the framework. You can modify these templates to customize the agent's communication style, instructions, and responses.
* **Extensions:** Extend Agent Zero's capabilities with custom extensions.  (Link to section on creating extensions if available.)  This allows you to add new features, modify existing behavior, and integrate with other systems.

## Memory Management

* **Persistence:** Agent Zero's memory persists across sessions, allowing agents to learn from past interactions.
* **Memory Retrieval:** Agents can access their memory to retrieve relevant information and experiences.  The `memory_tool` is used for this purpose.
* **Knowledge Base:** You can augment the agent's knowledge by providing external knowledge files. (Link to documentation on knowledge base management).

## Example: Web Search and Code Execution

Let's say you want Agent Zero to find the current price of Bitcoin and then convert it to Euros. Here's a possible prompt:

```
Find the current price of Bitcoin in USD and convert it to EUR.  Use the 'knowledge_tool' to find the price and the 'code_execution_tool' to perform the conversion.  The current EUR/USD exchange rate is 0.85.
```

Agent Zero might then:

1. Use the `knowledge_tool` to query a reliable source for the Bitcoin price.
2. Extract the price from the search results.
3. Use the `code_execution_tool` to execute a Python script that performs the conversion using the provided exchange rate.
4. Return the final price in Euros.

This example demonstrates how to combine multiple tools to achieve a complex task. By mastering prompt engineering and tool usage, you can unlock the full potential of Agent Zero.
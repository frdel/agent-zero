# Hacking and Customization in Agent Zero

Agent Zero is designed with flexibility at its core, allowing advanced users to "hack" and customize its behavior and functionality extensively. This document explores how you can tailor Agent Zero to create unique agent personas, modify its operational dynamics, and extend its capabilities.

## Understanding Prompt Engineering & Personas

The heart of an agent's personality and operational guidelines lies within its prompts. By customizing these, you can create distinct agent personas.

### Prompts Directory Structure
All prompt files are located within the `/prompts/` directory.
-   **`prompts/default/`**: This subdirectory contains the base set of prompts that define the standard Agent Zero behavior. It's a good practice to use these as templates when creating your own.
-   **Custom Prompt Directories (e.g., `prompts/hacker/`)**: To create a new persona (e.g., a "hacker" persona), you would create a new subdirectory like `prompts/hacker/`. Agent Zero will look for prompt files in your custom directory first, and if a specific file isn't found, it will fall back to the `prompts/default/` version. This allows you to override only the aspects you want to change.

### Creating a New Agent Persona
1.  **Create a New Prompt Subdirectory**: In the `/prompts/` directory, create a new folder. The name of this folder will be your persona identifier (e.g., `my_expert_analyst`).
2.  **Copy and Modify Prompts**: Copy the relevant prompt files from `prompts/default/` into your new subdirectory.
3.  **Key Prompt Files for Persona Definition**:
    *   `agent.system.main.role.md`: Defines the agent's overall role, purpose, and high-level capabilities. This is crucial for setting the persona.
    *   `agent.system.main.communication.md`: Specifies how the agent should communicate (e.g., tone, style, verbosity, language).
    *   `agent.system.main.solving.md`: Describes the agent's approach to tasks and problem-solving strategies.
    *   `agent.system.main.tips.md`: Can provide additional persona-specific tips or guidance for the agent.
    *   You can also customize tool-specific prompts (`agent.system.tool.*.md`) within your persona's directory if you want the persona to use tools in a specific way.
4.  **Select in Settings**: Once your custom prompt set is ready, you can select it from the Agent Zero UI in the Settings page (Agent Config section) to activate your new persona.

Agent Zero intelligently merges your custom prompt files with the default ones. If a file exists in your custom directory, it's used; otherwise, the default is used.

### Tips for Effective Persona Creation
-   **Be Specific**: Clearly define the desired traits, knowledge domains, and communication style.
-   **Iterate**: Test your persona with various inputs and refine the prompts based on the agent's responses.
-   **Consistency**: Ensure that the different prompt files work together harmoniously to create a coherent persona.
-   **Start Small**: Modify one or two key files first to see the impact before overhauling the entire set.

## Dynamic Behavior System

The Dynamic Behavior System allows for real-time adjustments to an agent's behavior based on user instructions during a conversation, without needing to modify the underlying prompt files permanently.

-   **Recap**: As detailed in the [Architecture Overview](architecture.md#dynamic-behavior-system), agents can modify their behavior (e.g., "respond in UK English," "be more concise") based on user requests. These changes are integrated into the system prompt for the current session.
-   **`behavior_adjustment` Tool**: This built-in tool is used by the agent to process user requests for behavior changes. The agent identifies behavioral instructions and uses this tool to update its rules.
-   **Storage**: These dynamic rules are stored in the agent's memory directory as a file named `behaviour.md`. They are intelligently merged with existing rules to avoid duplicates and conflicts.
-   **Process**:
    1.  User requests a behavior change.
    2.  The system identifies this as a behavioral instruction.
    3.  New rules are formulated and merged with the existing `behaviour.md`.
    4.  The updated behavior is immediately applied as the rules are injected at the start of the system prompt by the `_20_behaviour_prompt.py` extension.

This system offers a flexible way to adapt agent behavior on-the-fly, making interactions more dynamic and personalized.

## Extending Functionality

Agent Zero provides several mechanisms to extend its core functionality: Custom Tools, Instruments, and Extensions.

### Custom Tools
-   **Overview**: Tools are functionalities that agents can directly leverage to perform actions (e.g., code execution, web search). You can create custom tools to integrate new capabilities.
-   **Further Reading**: For detailed instructions on creating custom tools, refer to the [Custom Tools section in `docs/architecture.md`](architecture.md#custom-tools). This includes how to define the tool's prompt (`agent.system.tool.$TOOLNAME.md` in your prompt set) and, if necessary, implement its Python class in `/python/tools/`.
-   **Example Use Case**: Imagine creating a `calendar_tool` that allows the agent to interact with your Google Calendar to schedule meetings or check availability. This would involve a prompt defining how the agent requests calendar actions and a Python class to handle the API interaction.
-   **Important Note**: Custom Tools are always included in the system prompt, which consumes tokens. For functionalities that don't need to be reasoned about by the LLM for every turn or are more like background scripts, consider Instruments.

### Instruments
-   **Overview**: Instruments are custom scripts or executables that provide functionalities without adding to the system prompt's token count. They are stored in Agent Zero's long-term memory and recalled by the agent when a specific procedure or function is needed.
-   **Further Reading**: Details on adding instruments can be found in the [Instruments section of `docs/architecture.md`](architecture.md#6-instruments). This involves creating a folder in `instruments/custom/`, adding a Markdown description file for the agent to understand its use, and an executable script (e.g., `.sh`, `.py`).
-   **When to Use Instruments vs. Tools**:
    *   **Tools**: Use for capabilities the agent needs to reason about using, decide when to deploy, and interpret results from, as part of its core decision-making loop (e.g., searching the web, running code to answer a question). They are part of the agent's "active skillset."
    *   **Instruments**: Use for predefined procedures, complex calculations, or interactions with external systems that can be executed as a command without extensive reasoning by the LLM. They are more like utilities the agent can call upon. For example, an instrument could be a script that processes a large data file in a specific way once the agent decides it's necessary.

### Extensions
-   **Overview**: Extensions are Python scripts that modify or enhance various parts of the Agent Zero framework itself, such as the message loop, memory management, or system integrations. They are designed to keep the main codebase clean and organized while allowing for significant modular customization.
-   **Further Reading**: The [Extensions section in `docs/architecture.md`](architecture.md#7-extensions) provides information on their structure (located in `/python/extensions/` in specific subfolders), execution order (numerical prefix in filenames), and how to add new ones.
-   **Purpose**: Extensions are for deeper framework modifications. For instance, you could write an extension to log specific types of agent interactions to an external monitoring service or to implement a custom memory recall strategy.

## Ethical Considerations and Best Practices for "Hacking"

Customizing Agent Zero offers immense power, but it also comes with responsibilities.

-   **Responsible Customization**:
    *   Be mindful of the potential impact of your custom personas and functionalities.
    *   Avoid creating agents that could be harmful, deceptive, or violate privacy.
    *   Ensure your customizations align with ethical AI principles.
-   **Testing and Debugging**:
    *   Thoroughly test your custom prompts, tools, instruments, and extensions in various scenarios.
    *   Start with small, incremental changes to make debugging easier.
    *   Utilize Agent Zero's logging features and the "Context" and "History" views in the UI to understand how your customizations are affecting agent behavior.
    *   Isolate custom components to identify the source of issues.
-   **Documentation**: Keep notes on your customizations, especially if you're making significant changes. This will help you (and potentially others) understand and maintain your modified Agent Zero instance.
-   **Stay Updated**: When Agent Zero is updated, your custom components might need adjustments. Keep an eye on the official documentation and release notes.

By following these guidelines, you can explore the depths of Agent Zero's customizability in a safe and effective manner, truly making the agent your own.

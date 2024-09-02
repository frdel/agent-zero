import streamlit as st
import threading
import time
from agent import Agent, AgentConfig
import models
from python.helpers import files
from python.helpers.print_style import PrintStyle
from promptflow.tracing import start_trace

# Initialize session state
if 'agent' not in st.session_state:
    st.session_state.agent = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'logs' not in st.session_state:
    st.session_state.logs = []

def initialize_agent():
    chat_llm = models.get_azure_openai_chat(deployment_name="gpt-4o", temperature=0)
    utility_llm = chat_llm
    embedding_llm = models.get_azure_openai_embedding(deployment_name="text-embedding-3-small")

    config = AgentConfig(
        chat_model=chat_llm,
        utility_model=utility_llm,
        embeddings_model=embedding_llm,
        auto_memory_count=0,
        code_exec_docker_enabled=True,
        code_exec_docker_name="Herbie-exe",
        code_exec_docker_image="parrotsec/security",
        code_exec_docker_ports={"8022/tcp": 8022},
        code_exec_docker_volumes={files.get_abs_path("work_dir"): {"bind": "/root", "mode": "rw"}},
    )

    return Agent(number=0, config=config)

def main():
    st.title("AI Agent Interaction")

    # Initialize agent if not already done
    if st.session_state.agent is None:
        with st.spinner("Initializing agent..."):
            st.session_state.agent = initialize_agent()
        st.success("Agent initialized successfully!")

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # User input
    user_input = st.chat_input("Type your message here...")

    if user_input:
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        # Get agent response
        with st.spinner("Agent is thinking..."):
            response = st.session_state.agent.message_loop(user_input)

        # Add agent response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.write(response)

    # Sidebar for logs and hints
    with st.sidebar:
        st.header("Logs and Hints")
        if st.button("Clear Logs"):
            st.session_state.logs = []
        
        for log in st.session_state.logs:
            st.text(log)

        st.header("Hints")
        st.info("Hint: You can ask the agent about its capabilities or to perform specific tasks.")

if __name__ == "__main__":
    start_trace()
    main()
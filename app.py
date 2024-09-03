import streamlit as st
import time
from agent import Agent, AgentConfig
import models
from python.helpers import files
from python.helpers.print_style import PrintStyle
from promptflow.tracing import start_trace
from python.helpers.template_manager import load_templates, save_templates, templates_page, Template

# Initialize session state
if 'agent' not in st.session_state:
    st.session_state.agent = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'templates' not in st.session_state:
    st.session_state.templates = []

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
    st.set_page_config(layout="wide", page_title="AI Agent Interaction")
    
    # Load templates
    if 'templates' not in st.session_state:
        st.session_state.templates = load_templates()

    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Create", "Templates", "Chat History"])

    if page == "Create":
        create_page()
    elif page == "Templates":
        templates_page()
    elif page == "Chat History":
        chat_history_page()

    # Check if a template was selected to be used
    if 'use_template' in st.session_state:
        template = st.session_state.use_template
        del st.session_state.use_template  # Clear the flag
        process_user_input(f"Execute template: {template.name}", template)

def process_user_input(user_input, template=None):
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.spinner("Agent is processing..."):
        if template:
            # Use template information to guide the agent
            prompt = f"URL: {template.url}\nNavigation Goal: {template.navigation_goal}\nData Extraction Goal: {template.data_extraction_goal}\nUser Input: {user_input}"
        else:
            prompt = user_input

        # Process the input and capture the response and thoughts
        response, thoughts = st.session_state.agent.message_loop(prompt)
        
    # Add the response and thoughts to the message history
    st.session_state.messages.append({
        "role": "assistant", 
        "content": response,
        "thoughts": thoughts
    })

    # Display the response immediately
    with st.chat_message("assistant"):
        st.write(response)
    with st.expander("Agent's Thoughts"):
        for thought in thoughts:
            st.markdown(f"**{thought['type']}**: {thought['content']}")

def create_page():
    st.title("AI Agent Interaction")

    # Initialize agent if not already done
    if st.session_state.agent is None:
        with st.spinner("Initializing agent..."):
            st.session_state.agent = initialize_agent()
        st.success("Agent initialized successfully!")

    # "Try a prompt" section
    st.subheader("Try a prompt")
    user_input = st.text_input("Enter your prompt...")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("What is the top post on Hacker News?"):
            user_input = "What is the top post on Hacker News?"
    with col2:
        if st.button("Search for AAPL stock price"):
            user_input = "Search for AAPL stock price"

    if user_input:
        process_user_input(user_input)

    # Display chat messages with thoughts
    st.subheader("Chat History")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
        if "thoughts" in message:
            with st.expander("Agent's Thoughts"):
                for thought in message["thoughts"]:
                    st.markdown(f"**{thought['type']}**: {thought['content']}")

def use_template(template):
    st.session_state.messages.append({"role": "user", "content": f"Using template: {template.name}"})
    process_user_input(f"Execute template: {template.name}", template)
    st.success("Template executed successfully!")

def chat_history_page():
    st.title("Chat History")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
        if "thoughts" in message:
            with st.expander("Agent's Thoughts"):
                for thought in message["thoughts"]:
                    st.markdown(f"**{thought['type']}**: {thought['content']}")



if __name__ == "__main__":
    start_trace()
    main()
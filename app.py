import streamlit as st
import time
from agent import Agent, AgentConfig
import models
from python.helpers import files
from python.helpers.print_style import PrintStyle
from promptflow.tracing import start_trace
from python.helpers.template_manager import Template, load_templates, save_templates, templates_page
import json

# Initialize session state
if 'agent' not in st.session_state:
    st.session_state.agent = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'templates' not in st.session_state:
    st.session_state.templates = load_templates()
if 'conversation_started' not in st.session_state:
    st.session_state.conversation_started = False

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
    st.set_page_config(layout="wide", page_title="AI Agent Interaction", page_icon="🤖")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Chat", "Templates", "History"])

    if page == "Chat":
        chat_page()
    elif page == "Templates":
        templates_page()
    elif page == "History":
        history_page()

def chat_page():
    st.title("AI Agent Interaction 🤖")

    if st.session_state.agent is None:
        with st.spinner("Initializing agent..."):
            st.session_state.agent = initialize_agent()
        st.success("Agent initialized successfully!")

    st.subheader("Chat with AI Agent")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
        if "thoughts" in message:
            with st.expander("Agent's Thoughts", expanded=True):
                st.markdown(message["thoughts"])

    user_input = st.chat_input("Type your message here...")
    
    if user_input:
        st.session_state.conversation_started = True
        process_user_input(user_input)

    if not st.session_state.conversation_started:
        st.subheader("Available Templates")
        for i, template in enumerate(st.session_state.templates):
            if st.button(f"Use Template: {template.name}", key=f"quick_template_{i}"):
                process_template(template)
                st.session_state.conversation_started = True

def parse_and_format_thoughts(logs):
    combined_log = ''.join(logs).replace('\n', '')
    try:
        thought_data = json.loads(combined_log)
        formatted_output = ""
        
        if "thoughts" in thought_data:
            formatted_output += "📝 **Thoughts:**\n"
            for thought in thought_data["thoughts"]:
                formatted_output += f"- {thought}\n"
        
        if "tool_name" in thought_data:
            formatted_output += f"\n🛠️ **Tool:** `{thought_data['tool_name']}`\n"
        
        if "tool_args" in thought_data:
            formatted_output += "**Arguments:**\n"
            for key, value in thought_data["tool_args"].items():
                formatted_output += f"- *{key}:* `{value}`\n"
        
        return formatted_output
    except json.JSONDecodeError:
        return f"💭 {combined_log}\n"
    


def process_user_input(user_input):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.spinner("Agent is thinking..."):
        st.session_state.logs = []
        response = st.session_state.agent.message_loop(user_input)
    
    formatted_thoughts = parse_and_format_thoughts(st.session_state.logs)
    
    st.session_state.messages.append({
        "role": "assistant", 
        "content": response,
        "thoughts": formatted_thoughts
    })
    
    with st.chat_message("assistant"):
        st.write(response)
    
    with st.expander("Agent's Thoughts", expanded=True):
        st.markdown(formatted_thoughts)

    # Keep raw logs in sidebar for debugging
    with st.sidebar:
        st.write("Raw logs:")
        st.code(''.join(st.session_state.logs))


def process_template(template):
    prompt = f"Execute template: {template.name}\nURL: {template.url}\nNavigation Goal: {template.navigation_goal}\nData Extraction Goal: {template.data_extraction_goal}"
    if template.advanced_settings:
        prompt += "\nAdvanced Settings: " + ", ".join(f"{k}: {v}" for k, v in template.advanced_settings.items())
    process_user_input(prompt)

def history_page():
    st.title("Chat History")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
        if "thoughts" in message:
            with st.expander("Agent's Thoughts", expanded=True):
                for thought in message["thoughts"]:
                    st.markdown(thought)

if __name__ == "__main__":
    start_trace()
    main()
import streamlit as st
import time
from agent import Agent, AgentConfig
import models
from python.helpers import files
from python.helpers.print_style import PrintStyle
from promptflow.tracing import start_trace
from python.helpers.template_manager import Template, load_templates, save_templates, templates_page
import json


st.set_page_config(layout="wide", page_title="Multi-Agent Interaction", page_icon="🤖")

# Custom CSS for a polished look that highlights multi-agent interactions
st.markdown("""
<style>
    .reportview-container {
        background: #f0f2f6;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h1, h2, h3 {
        color: #1e1e1e;
        font-weight: 300;
    }
    .stButton>button {
        background-color: #007AFF;
        color: white;
        border-radius: 20px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #0056b3;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .chat-message.user {
        background-color: #DCF8C6;
    }
    .chat-message.agent {
        background-color: #E3F2FD;
    }
    .chat-message .header {
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .chat-message .content {
        margin-bottom: 0.5rem;
    }
    .chat-message .thoughts {
        background-color: #FFFFFF;
        border-radius: 5px;
        padding: 0.5rem;
        font-style: italic;
    }
    .sub-agent {
        margin-left: 2rem;
        border-left: 2px solid #007AFF;
        padding-left: 1rem;
    }
</style>
""", unsafe_allow_html=True)


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
        code_exec_docker_name="agent-zero-exe",
        code_exec_docker_image="frdel/agent-zero-exe:latest",
        code_exec_docker_ports={"8022/tcp": 8022},
        code_exec_docker_volumes={files.get_abs_path("work_dir"): {"bind": "/root", "mode": "rw"}},
    )

    return Agent(number=0, config=config)

def main():
    if st.session_state.agent is None:
        st.session_state.agent = initialize_agent()
    
    with st.sidebar:
        st.title("Navigation")
        page = st.radio("Select Page", ["Chat", "Templates", "History"], key="navigation")
        
        if st.button("Clear Conversation", key="clear_conversation"):
            st.session_state.messages = []
            st.session_state.conversation_started = False
            st.session_state.agent = initialize_agent()
            st.rerun()

    if page == "Chat":
        chat_page()
    elif page == "Templates":
        templates_page()
    elif page == "History":
        history_page()

def chat_page():
    st.title("Multi-Agent Interaction 🤖")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if "thoughts" in message:
                with st.expander("Agent's Thoughts", expanded=False):
                    st.write(message["thoughts"])

    # User input
    user_input = st.chat_input("Type your message here...", key="user_input")
    if user_input:
        process_user_input(user_input)

    if not st.session_state.conversation_started:
        st.subheader("Available Templates")
        templates_grid = st.columns(3)
        for i, template in enumerate(st.session_state.templates):
            with templates_grid[i % 3]:
                if st.button(f"{template.name}", key=f"quick_template_{i}"):
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
    
    with st.spinner("Agent is thinking..."):
        main_response = st.session_state.agent.message_loop(user_input)
    
    main_thoughts = parse_and_format_thoughts(st.session_state.logs)
    
    agent_message = {
        "role": "assistant",
        "content": main_response,
        "thoughts": main_thoughts,
    }
    
    st.session_state.messages.append(agent_message)
    st.session_state.conversation_started = True
    st.rerun()

def process_template(template):
    prompt = f"Execute template: {template.name}\nURL: {template.url}\nNavigation Goal: {template.navigation_goal}\nData Extraction Goal: {template.data_extraction_goal}"
    if template.advanced_settings:
        prompt += "\nAdvanced Settings: " + ", ".join(f"{k}: {v}" for k, v in template.advanced_settings.items())
    process_user_input(prompt)

def history_page():
    st.title("Chat History")
    for message in st.session_state.messages:
        st.write(f"{message['role'].capitalize()}: {message['content']}")

if __name__ == "__main__":
    main()
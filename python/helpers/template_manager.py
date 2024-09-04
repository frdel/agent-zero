import streamlit as st
import json
import os
from streamlit_card import card
import uuid

class Template:
    def __init__(self, id, name, url, navigation_goal, data_extraction_goal, advanced_settings=None):
        self.id = id
        self.name = name
        self.url = url
        self.navigation_goal = navigation_goal
        self.data_extraction_goal = data_extraction_goal
        self.advanced_settings = advanced_settings or {}

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "navigation_goal": self.navigation_goal,
            "data_extraction_goal": self.data_extraction_goal,
            "advanced_settings": self.advanced_settings
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            url=data["url"],
            navigation_goal=data["navigation_goal"],
            data_extraction_goal=data["data_extraction_goal"],
            advanced_settings=data.get("advanced_settings", {})
        )

def get_templates_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates.json')

def truncate_text(text, max_length):
    return text[:max_length] + '...' if len(text) > max_length else text

def load_templates():
    template_file = get_templates_file_path()
    if not os.path.exists(template_file):
        return []
    
    try:
        with open(template_file, 'r') as f:
            data = json.load(f)
            return [Template.from_dict(item) for item in data]
    except json.JSONDecodeError:
        st.error(f"Error decoding {template_file}. Starting with empty templates.")
        return []
    except Exception as e:
        st.error(f"Unexpected error loading templates: {str(e)}")
        return []

def save_templates(templates):
    template_file = get_templates_file_path()
    with open(template_file, 'w') as f:
        json.dump([template.to_dict() for template in templates], f, indent=2)

def templates_page():
    st.title("Template Manager")

    if 'templates' not in st.session_state:
        st.session_state.templates = load_templates()

    # Add New Template button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("➕ Add New Template", key="add_new_template"):
            st.session_state.show_new_template_form = True

    # New Template Form
    if st.session_state.get('show_new_template_form', False):
        with st.form("new_template_form"):
            new_template_name = st.text_input("Template Name")
            new_template_url = st.text_input("URL")
            new_template_navigation_goal = st.text_area("Navigation Goal")
            new_template_data_extraction_goal = st.text_area("Data Extraction Goal")
            
            with st.expander("Advanced Settings"):
                advanced_settings = {}
                advanced_settings['custom_field'] = st.text_input("Custom Field")

            submitted = st.form_submit_button("Save Template")
            
            if submitted and new_template_name and new_template_url and new_template_navigation_goal and new_template_data_extraction_goal:
                new_template = Template(
                    id=str(uuid.uuid4()),
                    name=new_template_name,
                    url=new_template_url,
                    navigation_goal=new_template_navigation_goal,
                    data_extraction_goal=new_template_data_extraction_goal,
                    advanced_settings=advanced_settings
                )
                st.session_state.templates.append(new_template)
                save_templates(st.session_state.templates)
                st.session_state.show_new_template_form = False
                st.success("Template saved successfully!")
                st.rerun()

    # Display existing templates
    st.subheader("Available Templates")
    cols = st.columns(3)
    for idx, template in enumerate(st.session_state.templates):
        with cols[idx % 3]:
            card_content = f"""
            **URL:** {truncate_text(template.url, 30)}
            **Navigation Goal:** {truncate_text(template.navigation_goal, 50)}
            **Data Extraction Goal:** {truncate_text(template.data_extraction_goal, 50)}
            """
            card(
                title=template.name,
                text=card_content,
                key=f"card_{template.id}",
                on_click=lambda t=template: st.session_state.update({"use_template": t.id})
            )
            # Add edit button separately
            if st.button("✏️ Edit", key=f"edit_{template.id}"):
                st.session_state.edit_template = template.id


    # Handle edit template
    if 'edit_template' in st.session_state:
        template = next((t for t in st.session_state.templates if t.id == st.session_state.edit_template), None)
        if template:
            st.subheader(f"Edit Template: {template.name}")
            with st.form("edit_template_form"):
                edited_name = st.text_input("Template Name", value=template.name)
                edited_url = st.text_input("URL", value=template.url)
                edited_navigation_goal = st.text_area("Navigation Goal", value=template.navigation_goal)
                edited_data_extraction_goal = st.text_area("Data Extraction Goal", value=template.data_extraction_goal)
                
                with st.expander("Advanced Settings"):
                    edited_advanced_settings = template.advanced_settings.copy()
                    edited_advanced_settings['custom_field'] = st.text_input("Custom Field", value=template.advanced_settings.get('custom_field', ''))

                save_edits = st.form_submit_button("Save Changes")
                
                if save_edits:
                    template.name = edited_name
                    template.url = edited_url
                    template.navigation_goal = edited_navigation_goal
                    template.data_extraction_goal = edited_data_extraction_goal
                    template.advanced_settings = edited_advanced_settings
                    save_templates(st.session_state.templates)
                    st.success("Template updated successfully!")
                    del st.session_state.edit_template
                    st.rerun()

    # Handle use template
    if 'use_template' in st.session_state:
        template = next((t for t in st.session_state.templates if t.id == st.session_state.use_template), None)
        if template:
            st.success(f"Using template: {template.name}")
            # Add your logic here to use the template
            del st.session_state.use_template


if __name__ == "__main__":
    templates_page()
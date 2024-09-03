import json
import os
import streamlit as st

class Template:
    def __init__(self, name, url, navigation_goal, data_extraction_goal, advanced_settings=None):
        self.name = name
        self.url = url
        self.navigation_goal = navigation_goal
        self.data_extraction_goal = data_extraction_goal
        self.advanced_settings = advanced_settings or {}

    def to_dict(self):
        return {
            "name": self.name,
            "url": self.url,
            "navigation_goal": self.navigation_goal,
            "data_extraction_goal": self.data_extraction_goal,
            "advanced_settings": self.advanced_settings
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data["name"],
            url=data["url"],
            navigation_goal=data["navigation_goal"],
            data_extraction_goal=data["data_extraction_goal"],
            advanced_settings=data.get("advanced_settings", {})
        )

def load_templates():
    template_file = 'templates.json'
    if not os.path.exists(template_file):
        with open(template_file, 'w') as f:
            json.dump([], f)
        return []
    
    try:
        with open(template_file, 'r') as f:
            content = f.read().strip()
            if not content:
                return []
            data = json.loads(content)
            return [Template.from_dict(item) for item in data]
    except json.JSONDecodeError:
        print(f"Error decoding {template_file}. Starting with empty templates.")
        return []
    except Exception as e:
        print(f"Unexpected error loading templates: {str(e)}")
        return []

def save_templates(templates):
    with open('templates.json', 'w') as f:
        json.dump([template.to_dict() for template in templates], f, indent=2)

def templates_page():
    st.title("Templates")

    # Display existing templates
    for i, template in enumerate(st.session_state.templates):
        st.subheader(f"Template: {template.name}")
        st.write(f"URL: {template.url}")
        st.write(f"Navigation Goal: {template.navigation_goal}")
        st.write(f"Data Extraction Goal: {template.data_extraction_goal}")
        if st.button(f"Use Template {i+1}"):
            st.session_state.use_template = template
            st.rerun()

    # Create new template
    st.subheader("Create New Template")
    new_template_name = st.text_input("Template Name")
    new_template_url = st.text_input("URL")
    new_template_navigation_goal = st.text_area("Navigation Goal")
    new_template_data_extraction_goal = st.text_area("Data Extraction Goal")
    
    # Advanced Settings (expandable section)
    with st.expander("Advanced Settings"):
        # Add any advanced settings fields here
        pass

    if st.button("Save Template"):
        if new_template_name and new_template_url and new_template_navigation_goal and new_template_data_extraction_goal:
            new_template = Template(
                name=new_template_name,
                url=new_template_url,
                navigation_goal=new_template_navigation_goal,
                data_extraction_goal=new_template_data_extraction_goal
            )
            st.session_state.templates.append(new_template)
            save_templates(st.session_state.templates)
            st.success("Template saved successfully!")
        else:
            st.error("Please fill in all fields.")

def use_template(template):
    return template 
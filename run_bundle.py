def post_install():
    # if "_internal.zip" exists, unzip and remove
    import os
    if os.path.exists("_internal.zip"):
        import zipfile
        print("\nDecompressing internal binaries...\n")
        with zipfile.ZipFile("_internal.zip", 'r') as zip_ref:
            zip_ref.extractall("_internal")
        os.remove("_internal.zip")
        
def run_bundle():
    print("\nImporting dependencies, this may take a while...\n")
    
    # dependencies to bundle
    import ansio
    import bs4
    import docker
    import duckduckgo_search
    import faiss
    from flask import Flask
    import flask_basicauth
    import inputimeout
    import langchain.embeddings
    import langchain_anthropic
    import langchain_community
    import langchain_google_genai
    import langchain_groq
    import langchain_huggingface
    import langchain_mistralai
    import langchain_ollama
    import langchain_openai
    import lxml_html_clean
    import emoji
    from emoji import unicode_codes
    import markdown
    import newspaper
    import paramiko
    import pypdf
    import dotenv
    import sentence_transformers
    from tiktoken import model, registry
    from tiktoken_ext import openai_public
    import unstructured
    import unstructured_client
    import webcolors



    # but do not bundle project files, these are to be imported at runtime



    import sys
    import os
    import importlib.util

    # Add the project_files directory to the Python path
    project_files_dir = os.path.join(os.path.dirname(sys.executable), 'agent-zero-files')
    sys.path.insert(0, project_files_dir)

    # Dynamically load the 'run_ui' module
    module_name = "run_ui"
    module_path = os.path.join(project_files_dir, f"{module_name}.py")

    # Load the module at runtime
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec and spec.loader:
        run_ui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(run_ui)

        # Now you can call the function in the dynamically imported module
        run_ui.run()  # Call the 'run' function from run_ui
    else:
        raise Exception(f"Could not load {module_name} from {module_path}")


# post_install()
run_bundle()
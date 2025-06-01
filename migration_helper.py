# migration_helper.py  
def migrate_env_vars():  
    """Helper script to migrate environment variables to LiteLLM format"""  
    migrations = {  
        "API_KEY_OPENAI": "OPENAI_API_KEY",  
        "API_KEY_ANTHROPIC": "ANTHROPIC_API_KEY",   
        "API_KEY_GOOGLE": "GOOGLE_API_KEY",  
        "API_KEY_GROQ": "GROQ_API_KEY",  
        "API_KEY_MISTRAL": "MISTRAL_API_KEY",  
    }  
      
    print("Environment variable migration suggestions:")  
    for old_key, new_key in migrations.items():  
        print(f"Consider renaming {old_key} to {new_key}")
# test_litellm_migration.py  
import models  
from models import ModelType, ModelProvider  
  
def test_model_creation():  
    """Test that all model types can be created"""  
      
    # Test chat models  
    chat_providers = [  
        ModelProvider.OPENAI,  
        ModelProvider.ANTHROPIC,  
        ModelProvider.GOOGLE,  
        ModelProvider.GROQ,  
        ModelProvider.MISTRALAI,  
    ]  
      
    for provider in chat_providers:  
        try:  
            model = models.get_model(ModelType.CHAT, provider, "test-model")  
            print(f"✓ {provider.value} chat model created successfully")  
        except Exception as e:  
            print(f"✗ {provider.value} chat model failed: {e}")  
      
    # Test embedding models  
    embedding_providers = [  
        ModelProvider.OPENAI,  
        ModelProvider.GOOGLE,  
    ]  
      
    for provider in embedding_providers:  
        try:  
            model = models.get_model(ModelType.EMBEDDING, provider, "test-embedding")  
            print(f"✓ {provider.value} embedding model created successfully")  
        except Exception as e:  
            print(f"✗ {provider.value} embedding model failed: {e}")  
  
if __name__ == "__main__":  
    test_model_creation()
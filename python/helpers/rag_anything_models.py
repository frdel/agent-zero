import asyncio
from typing import List, Dict, Any, Callable, Awaitable, Optional
from langchain_core.messages import BaseMessage

from agent import Agent
from python.helpers.print_style import PrintStyle
import models


class RAGAnythingModelAdapter:
    """
    Model integration layer that maps RAG-Anything's model functions 
    to Agent Zero's model system with rate limiting and provider management
    """
    
    def __init__(self, agent: Agent):
        self.agent = agent
    
    def get_llm_model_func(self) -> Callable:
        """
        Get LLM model function compatible with RAG-Anything
        Maps to Agent Zero's chat model
        """
        async def llm_model_func(
            messages: List[Dict[str, str]],
            temperature: float = 0.0,
            max_tokens: Optional[int] = None,
            **kwargs
        ) -> str:
            try:
                # Convert RAG-Anything message format to Agent Zero format
                langchain_messages = []
                for msg in messages:
                    if msg.get("role") == "system":
                        from langchain_core.messages import SystemMessage
                        langchain_messages.append(SystemMessage(content=msg["content"]))
                    elif msg.get("role") == "user":
                        from langchain_core.messages import HumanMessage
                        langchain_messages.append(HumanMessage(content=msg["content"]))
                    elif msg.get("role") == "assistant":
                        from langchain_core.messages import AIMessage
                        langchain_messages.append(AIMessage(content=msg["content"]))
                
                # Use Agent Zero's chat model with rate limiting
                response, _reasoning = await self.agent.call_chat_model(
                    messages=langchain_messages
                )
                
                return response
                
            except Exception as e:
                PrintStyle(font_color="red", padding=True).print(f"Error in LLM model function: {e}")
                raise e
        
        return llm_model_func
    
    def get_vision_model_func(self) -> Callable:
        """
        Get vision model function compatible with RAG-Anything
        Maps to Agent Zero's vision-enabled chat model
        """
        async def vision_model_func(
            image_data: str,
            prompt: str,
            temperature: float = 0.0,
            max_tokens: Optional[int] = None,
            **kwargs
        ) -> str:
            try:
                # Check if chat model supports vision
                if not self.agent.config.chat_model.vision:
                    raise ValueError("Chat model does not support vision. Enable vision in settings.")
                
                # Create message with image
                from langchain_core.messages import HumanMessage
                
                # Format image content for vision model
                message_content = [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }
                    }
                ]
                
                messages = [HumanMessage(content=message_content)]
                
                # Use Agent Zero's chat model with rate limiting
                response, _reasoning = await self.agent.call_chat_model(
                    messages=messages
                )
                
                return response
                
            except Exception as e:
                PrintStyle(font_color="red", padding=True).print(f"Error in vision model function: {e}")
                raise e
        
        return vision_model_func
    
    def get_embedding_func(self) -> Callable:
        """
        Get embedding function compatible with RAG-Anything
        Maps to Agent Zero's embedding model
        """
        async def embedding_func(
            texts: List[str],
            **kwargs
        ) -> List[List[float]]:
            try:
                # Get embedding model
                embedding_model = self.agent.get_embedding_model()
                
                # Apply rate limiting
                text_input = " ".join(texts)
                await self.agent.rate_limiter(
                    model_config=self.agent.config.embeddings_model,
                    input=text_input
                )
                
                # Generate embeddings
                embeddings = await embedding_model.aembed_documents(texts)
                
                return embeddings
                
            except Exception as e:
                PrintStyle(font_color="red", padding=True).print(f"Error in embedding function: {e}")
                raise e
        
        return embedding_func
    
    def get_utility_model_func(self) -> Callable:
        """
        Get utility model function for lightweight tasks
        Maps to Agent Zero's utility model
        """
        async def utility_model_func(
            system_prompt: str,
            user_prompt: str,
            temperature: float = 0.0,
            **kwargs
        ) -> str:
            try:
                response = await self.agent.call_utility_model(
                    system=system_prompt,
                    message=user_prompt
                )
                
                return response
                
            except Exception as e:
                PrintStyle(font_color="red", padding=True).print(f"Error in utility model function: {e}")
                raise e
        
        return utility_model_func
    
    def get_model_config(self) -> Dict[str, Any]:
        """
        Get model configuration for RAG-Anything initialization
        """
        return {
            "chat_model": {
                "provider": self.agent.config.chat_model.provider.value,
                "name": self.agent.config.chat_model.name,
                "vision": self.agent.config.chat_model.vision,
                "ctx_length": self.agent.config.chat_model.ctx_length,
                "kwargs": self.agent.config.chat_model.kwargs
            },
            "utility_model": {
                "provider": self.agent.config.utility_model.provider.value,
                "name": self.agent.config.utility_model.name,
                "ctx_length": self.agent.config.utility_model.ctx_length,
                "kwargs": self.agent.config.utility_model.kwargs
            },
            "embedding_model": {
                "provider": self.agent.config.embeddings_model.provider.value,
                "name": self.agent.config.embeddings_model.name,
                "kwargs": self.agent.config.embeddings_model.kwargs
            }
        }
    
    def validate_model_capabilities(self) -> Dict[str, bool]:
        """
        Validate that configured models support required capabilities
        """
        capabilities = {
            "chat_model_available": True,
            "vision_model_available": self.agent.config.chat_model.vision,
            "embedding_model_available": True,
            "utility_model_available": True
        }
        
        try:
            # Test chat model
            chat_model = self.agent.get_chat_model()
            if not chat_model:
                capabilities["chat_model_available"] = False
        except Exception:
            capabilities["chat_model_available"] = False
        
        try:
            # Test utility model
            utility_model = self.agent.get_utility_model()
            if not utility_model:
                capabilities["utility_model_available"] = False
        except Exception:
            capabilities["utility_model_available"] = False
        
        try:
            # Test embedding model
            embedding_model = self.agent.get_embedding_model()
            if not embedding_model:
                capabilities["embedding_model_available"] = False
        except Exception:
            capabilities["embedding_model_available"] = False
        
        return capabilities
    
    def get_model_functions(self) -> Dict[str, Callable]:
        """
        Get all model functions in a dictionary for RAG-Anything initialization
        """
        return {
            "llm_model_func": self.get_llm_model_func(),
            "vision_model_func": self.get_vision_model_func(),
            "embedding_func": self.get_embedding_func(),
            "utility_model_func": self.get_utility_model_func()
        }


def create_model_adapter(agent: Agent) -> RAGAnythingModelAdapter:
    """
    Factory function to create a model adapter for the given agent
    """
    return RAGAnythingModelAdapter(agent)


def validate_model_setup(agent: Agent) -> tuple[bool, List[str]]:
    """
    Validate that the agent's model configuration is suitable for RAG-Anything
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    adapter = RAGAnythingModelAdapter(agent)
    capabilities = adapter.validate_model_capabilities()
    
    issues = []
    
    if not capabilities["chat_model_available"]:
        issues.append("Chat model is not available or properly configured")
    
    if not capabilities["vision_model_available"]:
        issues.append("Vision model is not available - enable vision support for full RAG-Anything functionality")
    
    if not capabilities["embedding_model_available"]:
        issues.append("Embedding model is not available or properly configured")
    
    if not capabilities["utility_model_available"]:
        issues.append("Utility model is not available or properly configured")
    
    is_valid = len(issues) == 0 or (len(issues) == 1 and "Vision model" in issues[0])
    
    return is_valid, issues
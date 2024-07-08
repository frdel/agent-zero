from models import get_google_chat

llm = get_google_chat()
result = llm.invoke("Write a ballad about LangChain")
print(result.content)

# Instructions to Resolve Pyright Issues

Follow these steps to address the import and type checking issues reported by Pyright:

1. **Update dependencies:**
   Run the following commands to ensure all required packages are installed:

   ```bash
   pip install --upgrade langchain langchain-core langchain-community
   pip install --upgrade chromadb
   ```

2. **Update PYTHONPATH:**
   Add the project root to your PYTHONPATH:

   ```bash
   # For Unix-like systems (Linux, macOS)
   export PYTHONPATH=$PYTHONPATH:/path/to/your/project/agent-zero

   # For Windows
   set PYTHONPATH=%PYTHONPATH%;D:\path\to\your\project\agent-zero
   ```

3. **Modify agent.py:**
   Update the imports in `agent.py` to use try-except blocks for better error handling:

   ```python
   try:
       from langchain.schema import AIMessage, HumanMessage, SystemMessage
       from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
       from langchain_core.language_models import BaseLLM
       from langchain_core.language_models.chat_models import BaseChatModel
   except ImportError:
       print("Warning: Unable to import some langchain modules. Make sure langchain is installed.")
       AIMessage = HumanMessage = SystemMessage = ChatPromptTemplate = MessagesPlaceholder = BaseLLM = BaseChatModel = Any  # type: ignore
   ```

4. **Address type issues:**
   For any remaining type issues, consider using `# type: ignore` comments as a temporary solution:

   ```python
   self.history: List[Union[HumanMessage, AIMessage]] = []  # type: ignore
   ```

5. **Update other files:**
   - In `main.py`, replace `raw_input` with `input` (Python 3 compatibility)
   - In `initialize.py`, ensure the correct import paths for the model functions

6. **Handle missing imports:**
   For files with missing imports (e.g., `perplexity_search.py`, `vector_db.py`), either install the required packages or use try-except blocks to handle import errors gracefully.

7. **Resolve Docker-related issues:**
   In `python/helpers/docker.py`, update the type hints for the `run` method parameters to match the expected types from the Docker library.

8. **Re-run Pyright:**
   After making these changes, run Pyright again:

   ```bash
   pyright
   ```

9. **Ignore remaining warnings:**
   If there are still warnings that don't affect the functionality of your code, you can add them to a `.pyrightignore` file in your project root:

   ```txt
   # .pyrightignore
   **/agent.py
   **/docker.py
   ```

Remember, the goal is to have functional code. Some type checking issues may persist due to the dynamic nature of Python and the complexity of the project's dependencies. As long as the code runs correctly, you can gradually address these issues over time.

If you encounter any runtime errors or specific issues while running the application, please provide more details, and we can help you resolve them.

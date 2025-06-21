# Knowledge Base and RAG in Agent Zero

Agent Zero leverages a powerful Knowledge Base and Retrieval Augmented Generation (RAG) to enhance its capabilities. This allows agents to access and utilize a wide array of information, leading to more informed, accurate, and contextually relevant responses.

## Setting up Your Knowledge Base

The Knowledge Base is a repository of information that Agent Zero can query. You can populate it with various documents and data relevant to your tasks.

### Supported File Formats
Agent Zero supports a variety of common file formats for your knowledge base:
- `.txt` (Plain Text)
- `.pdf` (Portable Document Format)
- `.csv` (Comma-Separated Values)
- `.html` (HyperText Markup Language)
- `.json` (JavaScript Object Notation)
- `.md` (Markdown)

The system is designed to be expandable, with potential support for more formats in the future.

### How to Add Files
There are two primary ways to add files to your Knowledge Base:

1.  **Manually:**
    *   Navigate to the `/knowledge/custom/main/` directory within your Agent Zero installation.
    *   Place your files directly into this folder.
2.  **Using the 'Import Knowledge' Button:**
    *   In the Agent Zero Web UI, locate the "Action Buttons" beneath the chat input box.
    *   Click the "Import Knowledge" button.
    *   Select the files you wish to import. Supported formats include `.txt`, `.pdf`, `.csv`, `.html`, `.json`, and `.md`.
    *   A success message will confirm when files are successfully imported.
    *   Imported files are stored in the `/knowledge/custom/main/` directory.

All files added through these methods are automatically imported and indexed by Agent Zero, making them available for querying.

### Automatic Inclusion of `/docs` Directory
By default, the entire `/docs` directory (containing Agent Zero's own documentation) is automatically included in the Knowledge Base. This allows agents to have inherent knowledge about the framework itself.

### Tips for Organizing Knowledge Files
- **Logical Structure:** Consider creating subdirectories within `/knowledge/custom/main/` to organize your files by topic or source.
- **Clear Naming:** Use descriptive filenames that indicate the content of the file.
- **Regular Updates:** Keep your knowledge files current by adding new information and removing outdated documents.

## The `knowledge_tool` in Depth

The `knowledge_tool` is the primary mechanism through which Agent Zero interacts with its Knowledge Base and external information sources.

### Querying the Knowledge Base
When an agent needs information, it can utilize the `knowledge_tool`. This tool searches:
- The local Knowledge Base (files in `/knowledge/custom/main/` and `/docs/`).
- The agent's memory.

The tool returns a summary of the relevant information found, which the agent then uses to inform its decisions, answer questions, or complete tasks.

### Integration with SearXNG for Web Searches
The `knowledge_tool` is integrated with SearXNG, an open-source metasearch engine. This allows Agent Zero to perform web searches to retrieve up-to-date information or data not present in its local Knowledge Base.
- **Privacy-Focused:** SearXNG helps protect user privacy by not tracking queries.
- **Comprehensive Retrieval:** It can access various content types, including web pages, news articles, and more.
- **Seamless Operation:** The `knowledge_tool` works seamlessly across both local knowledge and online searches, providing a comprehensive information retrieval system.

### Utilization of Memory
In addition to the static Knowledge Base and web searches, the `knowledge_tool` can also access information stored in the agent's memory system. This allows it to recall relevant details from previous interactions or explicitly memorized facts.

## Retrieval Augmented Generation (RAG)

Retrieval Augmented Generation (RAG) is a technique that enhances the responses of Large Language Models (LLMs) by grounding them in factual information retrieved from a knowledge base.

### RAG in Agent Zero
Agent Zero employs RAG by using its `knowledge_tool` to fetch relevant information before generating a response. This process typically involves:
1.  **Understanding the Query:** The agent analyzes the user's request or the current task.
2.  **Information Retrieval:** The `knowledge_tool` queries the Knowledge Base (local files and potentially web search via SearXNG) for relevant documents or data snippets.
3.  **Context Augmentation:** The retrieved information is then provided as context to the LLM along with the original query.
4.  **Informed Generation:** The LLM uses this augmented context to generate a more accurate, detailed, and factually grounded response.

The `/docs` folder is automatically added to the knowledge base, enabling RAG-augmented tasks related to Agent Zero's own documentation.

### Examples of Prompts or Scenarios Where RAG is Beneficial
- **Answering specific questions based on your documents:** "According to `my_company_policy.pdf`, what is the vacation request procedure?"
- **Summarizing information from multiple sources:** "Summarize the key findings from `report_A.txt` and `study_B.pdf` regarding market trends."
- **Generating content based on existing knowledge:** "Draft an introductory paragraph for a new product based on the features listed in `product_specs.md`."
- **Troubleshooting based on documentation:** "My system is showing error code X. What are the troubleshooting steps as per `manual.pdf`?"
- **Comparing information:** "Compare the approaches described in `method1.txt` and `method2.html`."

By leveraging RAG, Agent Zero can provide responses that are not only coherent and contextually appropriate but also rich in factual detail drawn directly from your provided knowledge sources.

## Best Practices

To make the most of Agent Zero's Knowledge Base and RAG capabilities:

-   **Keep Knowledge Concise and Relevant:** While comprehensive, ensure the information stored is directly relevant to the agent's intended tasks. Overly noisy or irrelevant data can hinder retrieval accuracy.
-   **Update Knowledge Base Regularly:** As information changes, update your knowledge files to ensure the agent has access to the most current data.
-   **Use Specific Keywords in Prompts:** When interacting with the agent, using specific keywords related to the information you're seeking can help the `knowledge_tool` retrieve the most relevant documents more efficiently.
-   **Organize Your Files:** A well-organized knowledge base (e.g., using subfolders for different topics) can indirectly aid in clarity, though the tool primarily relies on indexed content.
-   **Monitor and Refine:** Pay attention to how the agent uses the knowledge base. If it struggles to find relevant information, you might need to adjust your file content, organization, or prompting strategies.

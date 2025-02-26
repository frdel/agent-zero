### knowledge_tool:
Tool for answering questions using memory database and online Islamic sources.

**Features:**
- Searches memory database by default
- Searches online Islamic sources with enhanced capabilities
- Provides comprehensive search results from multiple sources
- Maintains source attribution and citations
- Supports multilingual search (Arabic, English, and Bengali)

**Website Selection Guide:**
The tool intelligently selects relevant websites from the Islamic Websites Directory (`knowledge/default/main/websites/websites.md`) based on:

1. Question Category:
   - Quran interpretation and recitation
   - Hadith verification and translations
   - Islamic jurisprudence (Fiqh)
   - Contemporary Islamic issues
   - Educational resources
   - General Islamic references

2. Language Requirements:
   - Always to provide Bengali content
   - English translations
   - Arabic source texts

3. Content Depth:
   - Basic information
   - Detailed scholarly analysis
   - Academic research
   - Practical guidance

**Example usage:**
~~~json
{
    "thoughts": ["Checking memory and online sources for comprehensive information..."],
    "tool_name": "knowledge_tool",
    "tool_args": {
        "question": "Your question here",
        "search_sites": ["relevant sites based on question context"]
    }
}
~~~

**Response Format:**
- Maintains text formatting and encoding
- Includes citations and references
- Lists relevant sources used

**Boundaries:**
- Always use this tool for answering Islamic questions
- Provide source citations for all references
- Prioritize scholarly consensus when available
- Respect Islamic ethical guidelines in content

**Note:** The tool automatically selects the most relevant websites from the Islamic Websites Directory based on the question context and required depth of information.
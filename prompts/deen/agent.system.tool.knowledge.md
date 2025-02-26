### knowledge_tool:
Tool for answering questions using memory database and online Islamic sources.

**Features:**
- Searches memory database by default
- Searches online Islamic sources with enhanced capabilities
- Provides comprehensive search results from multiple sources
- Maintains source attribution and citations
- Supports multilingual search (Arabic, English, and Bengali)

**Website Selection Rules:**
You MUST follow these strict rules for website selection:

1. ONLY use websites listed in the Islamic Websites Directory (`knowledge/default/main/websites/websites.md`)
2. You MUST read and parse the websites.md file to get the current approved list
3. You MUST NEVER use any website not listed in websites.md
4. If a search returns results from non-approved domains, IGNORE them completely
5. If you cannot find information from approved sites, state this explicitly rather than using unapproved sources

The tool selects relevant websites from the approved list based on:

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
    "thoughts": ["Reading websites.md for approved sources and searching relevant ones..."],
    "tool_name": "knowledge_tool",
    "tool_args": {
        "question": "Your question here",
        "search_sites": ["approved sites from websites.md based on context"]
    }
}
~~~

**Response Format:**
- Maintains text formatting and encoding
- Includes citations and references
- Lists relevant sources used
- Clearly indicates when information comes from approved sources

**Boundaries:**
- Always use this tool for answering Islamic questions
- Provide source citations for all references
- Prioritize scholarly consensus when available
- Respect Islamic ethical guidelines in content
- NEVER use or cite unapproved websites

**Note:** The tool will select relevant websites ONLY from the approved list in websites.md based on the question context and required depth of information.
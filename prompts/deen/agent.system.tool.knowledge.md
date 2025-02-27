### Knowledge Tool
Islamic information search and verification tool.

## Core Rules:
1. **Source Restrictions**:
   - ONLY use websites from `knowledge/default/main/websites/websites.md`
   - MUST parse websites.md for current approved list
   - NEVER use unapproved websites
   - If no approved sources have information, explicitly state this

2. **Language Requirements**:
   - Primary: Bengali content
   - Secondary: English translations
   - Source: Arabic texts

3. **Search Categories**:
   - Quran (interpretation/recitation)
   - Hadith (verification/translations)
   - Fiqh (Islamic jurisprudence)
   - Contemporary issues
   - Educational resources
   - General references

## Usage Format:
```json
{
    "thoughts": ["Searching approved sources from websites.md..."],
    "tool_name": "knowledge_tool",
    "tool_args": {
        "question": "<query>",
        "search_sites": ["<approved_sites_based_on_context>"]
    }
}
```

## Response Requirements:
- Include source citations
- Maintain text formatting
- Indicate approved source usage
- Prioritize scholarly consensus
- Follow Islamic ethical guidelines

Note: Website selection is strictly based on websites.md and question context.
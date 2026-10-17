### search_engine
find live news, prices, and other real-time web data
arg: `query` (keyword-based text search query)
returns urls, titles, and descriptions

query rules:
- use keywords, names, exact phrases, model/version numbers, dates, and domains
- do not write a natural-language question or sentence
- omit filler words like "what", "who", "can you tell me", "find information about"
- use 3-10 high-signal terms; add alternatives only when they improve recall
- bad: "What is the latest LiteLLM release and what changed?"
- good: "LiteLLM latest release notes changelog"

example:
~~~json
{
  "thoughts": ["I need current information rather than relying on memory."],
  "headline": "Searching the web",
  "tool_name": "search_engine",
  "tool_args": {
    "query": "LiteLLM latest release notes changelog"
  }
}
~~~

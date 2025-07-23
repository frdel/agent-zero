### pubmed_search:
advanced literature search in PubMed database
comprehensive biomedical literature analysis with filtering
**Parameters:**
- query: search query using PubMed syntax
- max_results: number of results (default 20, max 200)
- date_range: filter by date ("last_year", "last_5_years", "2020-2024")
- sort_order: result sorting ("relevance", "pub_date", "first_author", "journal")
- include_abstracts: fetch full abstracts (default true)

**Example usage:**
~~~json
{
    "thoughts": [
        "I need to search for recent research on COVID-19 treatments",
    ],
    "headline": "Searching PubMed for COVID-19 treatment literature",
    "tool_name": "pubmed_search",
    "tool_args": {
        "query": "COVID-19 treatment clinical trial",
        "max_results": 50,
        "date_range": "2020-2024",
        "sort_order": "pub_date",
        "include_abstracts": true
    }
}
~~~
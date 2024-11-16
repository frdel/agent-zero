
import os
from googleapiclient.discovery import build
import models

# Function to perform Google search
def google_search(query):
    api_key = models.get_api_key("google")
    cse_id = models.get_api_key("google_cse")
    
    service = build('customsearch', 'v1', developerKey=api_key)
    res = service.cse().list(
        q=query, 
        cx=cse_id, 
        hl='lang_en', 
        gl='us', 
        num=10
    ).execute()
    return res

# Function to parse search results
def parse_search_results(results):
    items = results.get('items', [])
    return [{'title': item['title'], 'link': item['link']} for item in items]

# Example usage
if __name__ == '__main__':
    query = 'OpenAI'
    results = google_search(query)
    parsed_results = parse_search_results(results)
    print(parsed_results)
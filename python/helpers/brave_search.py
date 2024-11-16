import requests
from models import get_api_key

class BraveSearchAPI:
    def __init__(self):
        self.api_key = get_api_key('brave')
        self.base_url = 'https://api.search.brave.com/res/v1/web/search'

    def search(self, query, num_results=5):
        # Truncate the query to 50 words to comply with API requirements
        max_words = 50
        truncated_query = ' '.join(query.split()[:max_words])

        headers = {
            'X-Subscription-Token': self.api_key,
            'Accept': 'application/json'
        }
        params = {
            'q': truncated_query,
            'count': num_results,
            'country': 'us',
            'lr': 'lang_en'
        }
        response = requests.get(self.base_url, headers=headers, params=params)
        if response.status_code == 200:
            response_json = response.json()
            # Extract only the relevant 'web' results to provide a more structured output
            if 'web' in response_json and 'results' in response_json['web']:
                return response_json['web']['results']
            else:
                return response_json
        else:
            raise Exception(f'Error: {response.status_code} - {response.text}')

# Example usage
if __name__ == '__main__':
    brave_search = BraveSearchAPI()
    results = brave_search.search('example query')
    print(results)

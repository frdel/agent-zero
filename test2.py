import requests
from bs4 import BeautifulSoup
import random
import re

# List of user agents
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.101 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/91.0.4472.80 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
]

def clean_text(text):
    """Utility function to clean HTML tags and whitespace."""
    text = re.sub(r'class="[^"]*"', '', text)
    text = re.sub(r'id="[^"]*"', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def scrape_page(url):
    headers = {
        'User-Agent': random.choice(user_agents)
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()  # Check if the request was successful
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract title
        title = soup.title.string if soup.title else 'No Title'

        # Extract meta information
        def get_meta_content(name):
            meta = soup.find('meta', attrs={'name': name}) or soup.find('meta', property=name)
            return meta['content'] if meta else None

        author = get_meta_content('author')
        publish_date = get_meta_content('article:published_time') or get_meta_content('date')
        keywords = get_meta_content('keywords')
        description = get_meta_content('description') or get_meta_content('og:description')

        # Extract main content
        def get_main_content():
            content_selectors = ['main', '#content', '#main-content', '.content', '.post-content', '.entry-content', '.article-content', '#mw-content-text', '.mw-parser-output']
            for selector in content_selectors:
                element = soup.select_one(selector)
                if element:
                    return clean_text(element.get_text())
            return clean_text(soup.body.get_text() if soup.body else "")

        # Extract images
        def get_images():
            images = []
            for img in soup.find_all('img'):
                if not img.get('src', '').endswith('.svg'):
                    images.append({
                        'src': img['src'],
                        'alt': img.get('alt', '')
                    })
            return images

        # Extract product listings
        def get_products():
            products = []
            product_selectors = ['.s-result-item', '.product-item', '[data-component-type="s-search-result"]', '.sg-col-inner']
            for selector in product_selectors:
                elements = soup.select(selector)
                if elements:
                    for product in elements[:10]:
                        title_element = product.select_one('h2 a, .a-link-normal.a-text-normal')
                        price_element = product.select_one('.a-price .a-offscreen, .a-price')
                        image_element = product.select_one('img.s-image')
                        price = clean_text(price_element.text) if price_element else None
                        price = re.sub(r'(\$\d+(?:\.\d{2})?)\1+', r'\1', price) if price else None
                        products.append({
                            'title': clean_text(title_element.text) if title_element else None,
                            'link': title_element['href'] if title_element else None,
                            'price': price,
                            'image': image_element['src'] if image_element else None
                        })
            return products

        # Extract lists
        def get_lists():
            lists = []
            list_selectors = ['.mw-parser-output > ul', '.mw-parser-output > ol', 'main ul', 'main ol', '.content ul', '.content ol']
            for selector in list_selectors:
                elements = soup.select(selector)
                for element in elements:
                    list_items = [clean_text(li.get_text()) for li in element.find_all('li') if len(li.get_text().strip()) > 10]
                    if 3 <= len(list_items) <= 20:
                        lists.append({'type': element.name, 'items': list_items[:10]})
            return lists

        # Gather all extracted data
        return {
            'url': url,
            'title': title,
            'author': author,
            'publishDate': publish_date,
            'keywords': keywords,
            'metaDescription': description,
            'mainContent': get_main_content(),
            'images': get_images(),
            'products': get_products(),
            'lists': get_lists()
        }

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# Example usage:
result = scrape_page('https://github.com/frdel/agent-zero')
print(result)

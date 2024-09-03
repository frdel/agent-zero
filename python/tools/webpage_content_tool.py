import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from newspaper import Article
from python.helpers.tool import Tool, Response
from python.helpers.errors import handle_error


class WebpageContentTool(Tool):
    async def execute(self, url="", **kwargs):
        if not url:
            return Response(message="Error: No URL provided.", break_loop=False)

        try:
            # Validate URL
            parsed_url = urlparse(url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                return Response(message="Error: Invalid URL format.", break_loop=False)

            # Fetch webpage content
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # Use newspaper3k for article extraction
            article = Article(url)
            article.download()
            article.parse()

            # If it's not an article, fall back to BeautifulSoup
            if not article.text:
                soup = BeautifulSoup(response.content, 'html.parser')
                text_content = ' '.join(soup.stripped_strings)
            else:
                text_content = article.text

            return Response(message=f"Webpage content:\n\n{text_content}", break_loop=False)

        except requests.RequestException as e:
            return Response(message=f"Error fetching webpage: {str(e)}", break_loop=False)
        except Exception as e:
            handle_error(e)
            return Response(message=f"An error occurred: {str(e)}", break_loop=False)
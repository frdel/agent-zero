from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from python.helpers.print_style import PrintStyle
import asyncio
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

async def scrape_page(url, headless=True):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                user_agent=random.choice(user_agents)
            )
            page = await context.new_page()
            page.set_default_timeout(30000)
            
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_selector('body', timeout=5000)
            
            result = await page.evaluate(r'''() => {
                const cleanText = (text) => {
                    return text
                        .replace(/class="[^"]*"/g, '')
                        .replace(/id="[^"]*"/g, '')
                        .replace(/<[^>]+>/g, '')
                        .replace(/\s+/g, ' ')
                        .trim();
                };
                const getMetaContent = (name) => {
                    const meta = document.querySelector(`meta[name="${name}"], meta[property="${name}"]`);
                    return meta ? cleanText(meta.content) : null;
                };
                const getMainContent = () => {
                    const contentSelectors = [
                        'main', '#content', '#main-content', '.content', 
                        '.post-content', '.entry-content', '.article-content',
                        '#mw-content-text', '.mw-parser-output'
                    ];
                    for (const selector of contentSelectors) {
                        const element = document.querySelector(selector);
                        if (element) {
                            return cleanText(element.innerText);
                        }
                    }
                    return cleanText(document.body.innerText);
                };
                const getProducts = () => {
                    const productSelectors = [
                        '.s-result-item', '.product-item', '[data-component-type="s-search-result"]', '.sg-col-inner'
                    ];
                    for (const selector of productSelectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            return Array.from(elements).slice(0, 10).map(product => {
                                const titleElement = product.querySelector('h2 a, .a-link-normal.a-text-normal');
                                const priceElement = product.querySelector('.a-price .a-offscreen, .a-price');
                                const imageElement = product.querySelector('img.s-image');
                                let price = priceElement ? cleanText(priceElement.textContent) : null;
                                // Remove duplicate price
                                price = price ? price.replace(/(\$\d+(?:\.\d{2}?))\1+/, '$1') : null;
                                return {
                                    title: titleElement ? cleanText(titleElement.textContent) : null,
                                    link: titleElement ? titleElement.href : null,
                                    price: price,
                                    image: imageElement ? imageElement.src : null
                                };
                            }).filter(product => product.title && product.link);
                        }
                    }
                    return [];
                };
                const getNavigation = () => {
                    const navSelectors = ['nav', 'header', '[data-cy="header-nav"]'];
                    for (const selector of navSelectors) {
                        const navElement = document.querySelector(selector);
                        if (navElement) {
                            return Array.from(navElement.querySelectorAll('a'))
                                .filter(link => !link.href.endsWith('.svg'))
                                .slice(0, 10)  // Limit to 10 items
                                .map(link => ({
                                    href: link.href,
                                    text: cleanText(link.textContent)
                                }));
                        }
                    }
                    return [];
                };
                const getImages = () => {
                    return Array.from(document.querySelectorAll('img'))
                        .filter(img => !img.src.endsWith('.svg'))
                        .map(img => ({
                            src: img.src,
                            alt: img.alt,
                        }));
                };
                const getLists = () => {
                    const listSelectors = [
                        '.mw-parser-output > ul', '.mw-parser-output > ol',
                        '[data-cy="main-content"] ul', '[data-cy="main-content"] ol',
                        'main ul', 'main ol',
                        '.content ul', '.content ol',
                        '#content ul', '#content ol'
                    ];
                    let lists = [];
                    for (const selector of listSelectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            lists = Array.from(elements)
                                .filter(list => list.children.length >= 3 && list.children.length <= 20)
                                .map(list => ({
                                    type: list.tagName.toLowerCase(),
                                    items: Array.from(list.children)
                                        .filter(li => li.textContent.trim().length > 10)
                                        .map(li => {
                                            // Remove CSS classes, IDs, and inline styles
                                            let text = li.textContent.replace(/\s+/g, ' ').trim();
                                            // Remove any remaining HTML tags
                                            text = text.replace(/<[^>]+>/g, '');
                                            // Remove CSS-related content
                                            text = text.replace(/\.mw-parser-output[^{]+\{[^}]+\}/g, '');
                                            // Remove ISBN prefix if present
                                            text = text.replace(/^ISBN\s+/, '');
                                            return text;
                                        })
                                        .filter(text => text.length > 0 && !text.includes('mw-parser-output'))
                                        .slice(0, 10)
                                }))
                                .filter(list => list.items.length >= 3)
                                .slice(0, 3);
                            if (lists.length > 0) break;
                        }
                    }
                    return lists;
                };
                const getSocialMediaLinks = () => {
                    const socialSelectors = [
                        'a[href*="facebook.com"]',
                        'a[href*="twitter.com"]',
                        'a[href*="x.com"]',
                        'a[href*="github.com"]',
                        'a[href*="reddit.com"]',
                        'a[href*="tiktok.com"]',
                        'a[href*="discord.com"]',           
                        'a[href*="instagram.com"]',
                        'a[href*="linkedin.com"]',
                        'a[href*="youtube.com"]',
                        'a[href*="pinterest.com"]',
                        'a[href*="snapchat.com"]',
                        'a[href*="tumblr.com"]',
                        'a[href*="medium.com"]',
                        'a[href*="whatsapp.com"]',
                        'a[href*="telegram.org"]',
                        'a[href*="vimeo.com"]',
                        'a[href*="flickr.com"]',
                        'a[href*="quora.com"]',
                        'a[href*="twitch.tv"]'
                    ];
                    return socialSelectors.map(selector => {
                        const element = document.querySelector(selector);
                        return element ? element.href : null;
                    }).filter(Boolean);
                };
                const getCodeScripts = () => {
                    const codeBlocks = document.querySelectorAll('pre code, .highlight pre, .code-block');
                    return Array.from(codeBlocks).map(block => ({
                        language: block.className.match(/language-(\w+)/)?.[1] || 'text',
                        code: cleanText(block.textContent)
                    })).filter(script => script.code.length > 0);
                };
                return {
                    url: window.location.href,
                    title: document.title,
                    author: getMetaContent('author'),
                    publishDate: getMetaContent('article:published_time') || getMetaContent('date'),
                    lastModified: document.lastModified,
                    keywords: getMetaContent('keywords'),
                    metaDescription: getMetaContent('description') || getMetaContent('og:description'),
                    mainContent: getMainContent(),
                    navigation: getNavigation(),
                    images: getImages(),
                    lists: getLists(),
                    products: getProducts(),
                    socialMediaLinks: getSocialMediaLinks(),
                    codeScripts: getCodeScripts(),
                };
            }''')
                
            await browser.close()
            return result
    except PlaywrightTimeoutError as e:
        PrintStyle(font_color="yellow", padding=True).print(f"Attempt {attempt + 1} failed due to timeout: {str(e)}")
    except Exception as e:
        PrintStyle(font_color="red", padding=True).print(f"Attempt {attempt + 1} failed: {str(e)}")
        

async def scrape_url(url, headless):
    try:
        result = await scrape_page(url, headless)
        
        if result is None:
            raise ValueError("Scraping result is None")
        
        markdown_content = f"# {result.get('title', 'No Title')}\n\n"
        
        if result.get('url'):
            markdown_content += f"URL: {result['url']}\n\n"
        
        if result.get('author'):
            markdown_content += f"Author: {result['author']}\n\n"
        
        if result.get('publishDate'):
            markdown_content += f"Published: {result['publishDate']}\n\n"
        
        if result.get('keywords'):
            markdown_content += f"Keywords: {result['keywords']}\n\n"
        
        if result.get('metaDescription'):
            markdown_content += f"## Description\n\n{result['metaDescription']}\n\n"
        
        if result.get('mainContent'):
            markdown_content += "## Webpage Content:\n\n"
            markdown_content += result['mainContent'] + "\n\n"
        
        if result.get('lists'):
            markdown_content += "## Lists\n\n"
            for list_item in result['lists']:
                markdown_content += f"### {list_item['type'].upper()} List\n\n"
                for item in list_item['items']:
                    markdown_content += f"- {item}\n"
                markdown_content += "\n"
        
        if result.get('products'):
            markdown_content += "## Products\n\n"
            for product in result['products']:
                markdown_content += f"### {product.get('title', 'Untitled Product')}\n\n"
                if product.get('price'):
                    price = product['price']
                    price = re.sub(r'(\$\d+(?:\.\d{2})?)\1+', r'\1', price)
                    markdown_content += f"Price: {price}\n\n"
                if product.get('link'):
                    markdown_content += f"[View Product]({product['link']})\n\n"
                if product.get('image'):
                    markdown_content += f"![Product Image]({product['image']})\n\n"
                markdown_content += "---\n\n"
        
        if result.get('socialMediaLinks'):
            markdown_content += "## Social Media Links\n\n"
            for link in result['socialMediaLinks']:
                markdown_content += f"- [{link.split('.com')[0].split('/')[-1].capitalize()}]({link})\n"
            markdown_content += "\n"
        
        if result.get('codeScripts'):
            markdown_content += "## Code Snippet\n\n"
            for script in result['codeScripts']:
                markdown_content += f"```{script['language']}\n{script['code']}\n```\n\n"
        
        markdown_content = markdown_content.strip()
        
        return markdown_content
    except Exception as e:
        return f"Error: Failed to scrape URL. Reason: {str(e)}"

async def fetch_page_content(url: str, max_retries: int = 2, headless: bool = True):
    for attempt in range(max_retries):
        try:
            content = await scrape_url(url, headless)
            if content.startswith("Error:"):
                raise Exception(content)
            return str(content)
        except Exception as e:
            PrintStyle(font_color="red", padding=True).print(f"Attempt {attempt + 1} failed: {str(e)}")
    
    raise Exception("Error: Webpage content is not available.")


async def test():
    url = "https://github.com/frdel/agent-zero"
    content = await fetch_page_content(url)
    print(content)
    
asyncio.run(test())
import os
import json
import requests
from bs4 import BeautifulSoup
import logging
import time
import re

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# GitBook base URL
BASE_URL = "https://guide.devfolio.co"  # Using the URL from your screenshot

def fetch_page(url):
    """Fetch a page from GitBook"""
    try:
        logger.info(f"Fetching {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None

def extract_links(html, base_url):
    """Extract all GitBook internal links from a page"""
    if not html:
        return []
        
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    
    # Find all links
    for a in soup.find_all('a', href=True):
        href = a['href']
        
        # Skip external links, anchors, and non-GitBook links
        if href.startswith('/') and not href.startswith('//'):
            full_url = base_url + href
            links.append(full_url)
            
    return links

def extract_content(html, url):
    """Extract title and content from a GitBook page"""
    if not html:
        return None
        
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract title
    title_tag = soup.find('h1') or soup.find('h2') or soup.find('title')
    title = title_tag.get_text().strip() if title_tag else os.path.basename(url)
    
    # Find the main content container
    # This is more specific to GitBook's structure
    content_div = None
    
    # Try different possible content containers
    for selector in [
        'main', 'article', 
        'div.page-content', 'div.gitbook-page', 
        'div[role="main"]', 'div.markdown'
    ]:
        content_div = soup.select_one(selector)
        if content_div:
            break
    
    # If we still can't find the content, use the body
    if not content_div:
        logger.warning(f"Could not find main content in {url}, using body")
        content_div = soup.body
    
    # Extract all paragraphs, headings, lists, code blocks, etc.
    content_parts = []
    
    # Add all text content elements
    for element in content_div.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'pre', 'code', 'blockquote', 'table']):
        text = element.get_text().strip()
        if text:
            # Add heading markers for structure
            if element.name.startswith('h') and len(element.name) == 2:
                level = int(element.name[1])
                prefix = '#' * level + ' '
                text = prefix + text
            content_parts.append(text)
    
    # Join with double newlines to preserve paragraph structure
    full_content = "\n\n".join(content_parts)
    
    # Clean the content
    full_content = re.sub(r'\s+', ' ', full_content)
    full_content = re.sub(r'\n\s*\n', '\n\n', full_content)
    
    # Extract headings for keywords
    headings = []
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4']):
        heading_text = heading.get_text().strip()
        if heading_text:
            headings.append(heading_text)
    
    # Extract any additional metadata
    meta_description = ""
    meta_tag = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'})
    if meta_tag and 'content' in meta_tag.attrs:
        meta_description = meta_tag['content']
    
    return {
        "title": title,
        "content": full_content,
        "keywords": headings,
        "url": url,
        "meta_description": meta_description
    }

def create_filename_from_url(url):
    """Create a safe filename from URL"""
    # Remove the base URL and leading slash
    path = url.replace(BASE_URL, '').lstrip('/')
    
    # Remove query parameters and anchors
    path = path.split('?')[0].split('#')[0]
    
    # Replace slashes and other invalid characters with underscores
    filename = re.sub(r'[^a-zA-Z0-9]', '_', path)
    
    # Ensure we have a valid filename
    if not filename:
        filename = 'index'
    if not filename.endswith('.json'):
        filename += '.json'
        
    return filename

def crawl_gitbook(start_url, output_dir):
    """Crawl GitBook and save content to JSON files"""
    os.makedirs(output_dir, exist_ok=True)
    
    visited = set()
    to_visit = [start_url]
    
    while to_visit:
        url = to_visit.pop(0)
        
        if url in visited:
            continue
            
        visited.add(url)
        logger.info(f"Processing {url}")
        
        html = fetch_page(url)
        if not html:
            continue
            
        # Extract content
        data = extract_content(html, url)
        if data:
            # Create safe filename
            filename = create_filename_from_url(url)
                
            # Save to file
            output_path = os.path.join(output_dir, filename)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Saved {url} to {output_path}")
        
        # Find new links
        links = extract_links(html, BASE_URL)
        for link in links:
            if link not in visited and link not in to_visit:
                to_visit.append(link)
                
        # Be nice to the server
        time.sleep(1)

if __name__ == "__main__":
    logger.info("Starting GitBook scraper")
    
    # Ensure output directory exists
    output_dir = "../knowledgebase/gitbook"
    os.makedirs(output_dir, exist_ok=True)
    
    # Start crawling
    crawl_gitbook(BASE_URL, output_dir)
    
    logger.info("GitBook scraping completed")

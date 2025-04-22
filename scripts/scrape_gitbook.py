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
BASE_URL = "https://guide.devfolio.co/"  

def fetch_page(url):
    """Fetch a page from GitBook"""
    try:
        logger.info(f"Fetching {url}")
        response = requests.get(url)
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
        
        # Skip external links and anchors
        if href.startswith('/') and not href.startswith('//'):
            full_url = base_url + href
            links.append(full_url)
            
    return links

def clean_text(text):
    """Clean text content"""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove non-printable characters
    text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
    return text.strip()

def extract_content(html, url):
    """Extract title and content from a GitBook page"""
    if not html:
        return None
        
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract title
    title_tag = soup.find('h1') or soup.find('h2') or soup.find('title')
    title = title_tag.get_text() if title_tag else os.path.basename(url)
    
    # Extract main content
    content_div = soup.find('article') or soup.find('main') or soup.find('div', class_='content')
    
    if not content_div:
        logger.warning(f"Could not find main content in {url}")
        content = soup.get_text()
    else:
        content = content_div.get_text()
    
    # Clean content
    content = clean_text(content)
    
    # Extract headings for keywords
    headings = []
    for heading in soup.find_all(['h1', 'h2', 'h3']):
        headings.append(heading.get_text().strip())
    
    return {
        "title": title,
        "content": content,
        "keywords": headings,
        "url": url
    }

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
            filename = re.sub(r'[^a-zA-Z0-9]', '_', os.path.basename(url))
            if not filename:
                filename = 'index'
            if not filename.endswith('.json'):
                filename += '.json'
                
            # Save to file
            output_path = os.path.join(output_dir, filename)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Saved {url} to {output_path}")
        
        # Find new links
        links = extract_links(html, BASE_URL)
        for link in links:
            if link not in visited:
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

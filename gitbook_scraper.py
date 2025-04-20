import os
import asyncio
import aiohttp
import datetime
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from kb_manager import _load_knowledge_base, save_knowledge_base

logger = logging.getLogger(__name__)

GITBOOK_URL = os.environ.get("GITBOOK_URL", "")

async def fetch_page(session, url):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.text()
            logger.warning(f"Failed to fetch {url}: Status {response.status}")
            return None
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None

def extract_links(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        
        if href.startswith('/') or href.startswith(base_url):
            full_url = urljoin(base_url, href)
            links.append(full_url)
    
    return links

def extract_content(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    
    title_tag = soup.find('h1') or soup.find('title')
    title = title_tag.text.strip() if title_tag else "Untitled"
    
    main = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
    
    if not main:
        return None
    
    paragraphs = []
    for p in main.find_all(['p', 'li']):
        text = p.text.strip()
        if text and len(text) > 15:  # Skip really short bits
            paragraphs.append(text)
    
    if not paragraphs:
        return None
    
    categories = []
    
    if 'judg' in url.lower() or 'judg' in title.lower():
        categories.append('judging')
    
    if 'setup' in url.lower() or 'config' in url.lower() or 'setup' in title.lower():
        categories.append('setup')
    
    if 'invite' in url.lower() or 'invite' in title.lower():
        categories.append('invite')
    
    if not categories:
        categories.append('general')
    
    return {
        "title": title,
        "url": url,
        "paragraphs": paragraphs,
        "categories": categories
    }

async def crawl_gitbook():
    if not GITBOOK_URL:
        logger.error("No GITBOOK_URL set in environment variables")
        return {"last_updated": None, "topics": {}}
    
    kb = _load_knowledge_base()
    kb["topics"] = {}  # Reset topics for fresh crawl
    visited = set()
    
    async with aiohttp.ClientSession() as session:
        to_visit = [GITBOOK_URL]
        
        while to_visit:
            url = to_visit.pop(0)
            
            if url in visited:
                continue
                
            visited.add(url)
            logger.info(f"Crawling {url}")
            
            html = await fetch_page(session, url)
            if not html:
                continue
            
            content = extract_content(html, url)
            if content:
                kb["topics"][content["title"]] = {
                    "url": content["url"],
                    "paragraphs": content["paragraphs"],
                    "categories": content["categories"]
                }
            
            new_links = extract_links(html, url)
            for link in new_links:
                if link not in visited and "gitbook" in link and link not in to_visit:
                    to_visit.append(link)
            
            await asyncio.sleep(1)  # Politeness delay
    
    kb["last_updated"] = datetime.datetime.now().isoformat()
    return kb

def refresh_knowledge_base():
    # Fix for event loop error
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    kb = loop.run_until_complete(crawl_gitbook())
    save_knowledge_base(kb)
    logger.info(f"Knowledge base refreshed with {len(kb['topics'])} topics")
    
    return {
        "timestamp": kb["last_updated"],
        "topic_count": len(kb["topics"])
    }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    refresh_knowledge_base()
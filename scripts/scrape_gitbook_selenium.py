import os
import json
import time
import logging
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# GitBook base URL
BASE_URL = "https://guide.devfolio.co"

class GitBookScraper:
    def __init__(self, base_url, output_dir):
        self.base_url = base_url
        self.output_dir = output_dir
        self.visited_urls = set()
        self.urls_to_visit = []
        self.setup_browser()
        
    def setup_browser(self):
        """Set up headless Chrome browser"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        
    def extract_links(self):
        """Extract all GitBook internal links from the current page"""
        # Get all links on the page
        elements = self.driver.find_elements(By.TAG_NAME, 'a')
        links = []
        
        for element in elements:
            try:
                href = element.get_attribute('href')
                if href and href.startswith(self.base_url):
                    # Skip anchor links (same page)
                    if '#' in href and href.split('#')[0] in self.visited_urls:
                        continue
                    # Skip query parameters
                    clean_url = href.split('?')[0].split('#')[0]
                    links.append(clean_url)
            except Exception as e:
                logger.error(f"Error getting href: {e}")
                
        return list(set(links))  # Remove duplicates
        
    def extract_content(self, url):
        """Extract the full content from the current page"""
        try:
            # Wait for the content to fully load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "article"))
            )
            
            # Give extra time for any dynamic content to load
            time.sleep(3)
            
            # Get the page title
            title = self.driver.title
            
            # Get the full HTML after JavaScript execution
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract main content - look for the main article container
            content_element = None
            for selector in [
                'article', 
                'main',
                'div.page-content', 
                '.gitbook-markdown-body',
                '.markdown', 
                'div[data-testid="page.content"]'
            ]:
                try:
                    content_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if content_element:
                        break
                except:
                    continue
            
            if not content_element:
                logger.warning(f"Could not find main content container in {url}")
                content_element = self.driver.find_element(By.TAG_NAME, "body")
            
            # Get the full content
            content = content_element.text
            
            # Also extract headings for keywords
            headings = []
            heading_elements = soup.find_all(['h1', 'h2', 'h3'])
            for heading in heading_elements:
                text = heading.get_text().strip()
                if text:
                    headings.append(text)
                    
            # Create a structured content object
            content_object = {
                "title": title,
                "content": content,
                "keywords": headings,
                "url": url,
                "meta_description": ""
            }
            
            # Try to get meta description
            try:
                meta = soup.find('meta', {'name': 'description'})
                if meta:
                    content_object["meta_description"] = meta.get('content', '')
            except:
                pass
                
            return content_object
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None
            
    def create_filename(self, url):
        """Create a safe filename from URL"""
        path = urlparse(url).path.strip('/')
        if not path:
            return "index.json"
            
        # Replace slashes and other invalid chars with underscores
        filename = re.sub(r'[^a-zA-Z0-9]', '_', path)
        if not filename.endswith('.json'):
            filename += '.json'
            
        return filename
        
    def save_content(self, content, url):
        """Save the extracted content to a JSON file"""
        if not content:
            return False
            
        try:
            filename = self.create_filename(url)
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2)
                
            logger.info(f"Saved {url} to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving content for {url}: {e}")
            return False
            
    def scrape_url(self, url):
        """Scrape a single URL"""
        if url in self.visited_urls:
            return
            
        logger.info(f"Processing {url}")
        self.visited_urls.add(url)
        
        try:
            # Load the page
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(2)
            
            # Extract and save content
            content = self.extract_content(url)
            self.save_content(content, url)
            
            # Extract links to visit next
            links = self.extract_links()
            for link in links:
                if link not in self.visited_urls and link not in self.urls_to_visit:
                    self.urls_to_visit.append(link)
                    
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            
    def scrape(self):
        """Main method to scrape the GitBook"""
        try:
            # Start with the base URL
            self.urls_to_visit.append(self.base_url)
            
            while self.urls_to_visit:
                url = self.urls_to_visit.pop(0)
                self.scrape_url(url)
                # Be nice to the server
                time.sleep(1)
                
        finally:
            # Clean up
            self.driver.quit()
            
if __name__ == "__main__":
    logger.info("Starting Selenium-based GitBook scraper")
    
    # Ensure output directory exists
    output_dir = "../knowledgebase/gitbook"
    os.makedirs(output_dir, exist_ok=True)
    
    # Start scraping
    scraper = GitBookScraper(BASE_URL, output_dir)
    scraper.scrape()
    
    logger.info("GitBook scraping completed")

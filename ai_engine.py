import os
import logging
import json
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GITBOOK_URL = os.environ.get("GITBOOK_URL")
KB_FILE = "kb_chunks.json"

client = OpenAI(api_key=OPENAI_API_KEY)

class AIEngine:
    def __init__(self):
        self.docs = []
        
    def initialize_knowledge_base(self):
        """Load or create knowledge base"""
        try:
            if os.path.exists(KB_FILE):
                logger.info("Loading existing knowledge chunks...")
                with open(KB_FILE, 'r') as f:
                    self.docs = json.load(f)
                return True
                
            logger.info(f"Creating new knowledge base from {GITBOOK_URL}")
            return self.refresh_knowledge_base()["success"]
        except Exception as e:
            logger.error(f"Failed to initialize knowledge base: {e}")
            return False
            
    def refresh_knowledge_base(self):
        """Refresh knowledge base from GitBook"""
        try:
            # Scrape content
            content = self._scrape_gitbook()
            
            # Save to file
            with open(KB_FILE, 'w') as f:
                json.dump(content, f)
                
            self.docs = content
            
            return {
                "success": True,
                "chunk_count": len(content)
            }
        except Exception as e:
            logger.error(f"Failed to refresh knowledge base: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _scrape_gitbook(self):
        """Scrape GitBook content"""
        result = []
        
        try:
            # Get main page
            response = requests.get(GITBOOK_URL)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Get main content
            main_content = soup.find('main') or soup.find('article') or soup.body
            
            if not main_content:
                logger.warning("Could not find main content")
                return result
                
            # Extract text chunks
            for element in main_content.find_all(['h1', 'h2', 'h3', 'p']):
                text = element.get_text(strip=True)
                if text and len(text) > 20:  # Skip short snippets
                    result.append({
                        "content": text,
                        "source": GITBOOK_URL
                    })
            
            # Find and follow links to other pages
            links = main_content.find_all('a', href=True)
            followed_count = 0
            
            for link in links:
                href = link['href']
                
                # Only follow links that look like internal GitBook pages
                if href.startswith('/') or (GITBOOK_URL in href and href != GITBOOK_URL):
                    if href.startswith('/'):
                        full_url = GITBOOK_URL.rstrip('/') + href
                    else:
                        full_url = href
                        
                    try:
                        logger.info(f"Following link: {full_url}")
                        subpage = requests.get(full_url)
                        sub_soup = BeautifulSoup(subpage.text, 'html.parser')
                        sub_content = sub_soup.find('main') or sub_soup.find('article') or sub_soup.body
                        
                        if sub_content:
                            for element in sub_content.find_all(['h1', 'h2', 'h3', 'p']):
                                text = element.get_text(strip=True)
                                if text and len(text) > 20:
                                    result.append({
                                        "content": text,
                                        "source": full_url
                                    })
                    except Exception as e:
                        logger.warning(f"Error following link {full_url}: {e}")
                    
                    followed_count += 1
                    if followed_count >= 10:  # Limit number of pages to follow
                        break
            
            logger.info(f"Extracted {len(result)} content chunks from GitBook")
            return result
            
        except Exception as e:
            logger.error(f"Error scraping GitBook: {e}")
            return result
            
    def answer_query(self, query, user_id=None, username=None):
        """Answer a user query using AI"""
        logger.info(f"AI Engine received query: '{query}'")
        
        if not self.docs:
            logger.warning("Knowledge base is empty!")
            return "Sorry, my knowledge base isn't loaded yet. Please try again later."
            
        try:
            # For debugging, let's print what's in the knowledge base
            logger.info(f"Knowledge base has {len(self.docs)} documents")
            
            # Include a reasonable number of docs as context
            context_docs = self.docs[:15]  # Use first 15 chunks to avoid token limits
            context = "\n\n".join([doc["content"] for doc in context_docs])
            
            logger.info(f"Created context with {len(context)} characters")
            
            # Create prompt for the AI
            system_prompt = """You are a helpful assistant specializing in answering questions about judging, 
            judging setup, and judge invitations for technology events and hackathons. 
            Use the provided context to answer the user's question. 
            If the answer cannot be found in the context, say that you don't have that information."""
            
            user_prompt = f"Context:\n{context}\n\nQuestion: {query}"
            
            logger.info("Sending request to OpenAI")
            
            # Get completion from OpenAI
            completion = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0
            )
            
            answer = completion.choices[0].message.content
            logger.info(f"Received answer from OpenAI: '{answer[:50]}...'")
            
            return answer
            
        except Exception as e:
            logger.error(f"Error answering query: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return "I encountered an error while processing your question. Please try again later."

# Create a singleton instance
ai_engine = AIEngine()

# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ai_engine.initialize_knowledge_base()
    answer = ai_engine.answer_query("How do I set up judging?")
    print(answer)
import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class KnowledgeBase:
    """
    Class to manage and query different knowledge sources for the DevfolioAsk bot.
    
    Handles three types of knowledge:
    1. GitBook: Documentation scraped from GitBook
    2. Organizer: Special knowledge provided by organizers
    3. Feedback: Knowledge derived from user feedback
    """
    
    def __init__(self, base_path: str = "knowledgebase"):
        """
        Initialize the knowledge base with paths to different knowledge sources.
        
        Args:
            base_path: Base directory for knowledge files
        """
        self.base_path = base_path
        self.gitbook_path = os.path.join(base_path, "gitbook")
        self.organizer_path = os.path.join(base_path, "organizer")
        self.feedback_path = os.path.join(base_path, "feedback")
        
        # In-memory storage for loaded knowledge
        self.gitbook_data = {}
        self.organizer_data = {}
        self.feedback_data = {}
        
        # Load knowledge on initialization
        self.load_knowledge()
        
    def load_knowledge(self) -> None:
        """Load all knowledge sources into memory."""
        logger.info("Loading knowledge base data...")
        
        # Load GitBook knowledge
        self._load_directory_data(self.gitbook_path, self.gitbook_data)
        
        # Load organizer knowledge
        self._load_directory_data(self.organizer_path, self.organizer_data)
        
        # Load feedback knowledge
        self._load_directory_data(self.feedback_path, self.feedback_data)
        
        logger.info(f"Knowledge base loaded: {len(self.gitbook_data)} GitBook files, " 
                   f"{len(self.organizer_data)} organizer files, "
                   f"{len(self.feedback_data)} feedback files")
        
    def _load_directory_data(self, directory: str, data_dict: Dict[str, Any]) -> None:
        """
        Load all JSON and text files from a directory into a dictionary.
        
        Args:
            directory: Path to the directory containing knowledge files
            data_dict: Dictionary to store the loaded data
        """
        if not os.path.exists(directory):
            logger.warning(f"Knowledge directory does not exist: {directory}")
            return
            
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            
            # Skip directories
            if os.path.isdir(file_path):
                continue
                
            # Load based on file type
            try:
                if filename.endswith('.json'):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data_dict[filename] = json.load(f)
                elif filename.endswith('.txt') or filename.endswith('.md'):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data_dict[filename] = f.read()
                else:
                    logger.debug(f"Skipping unsupported file type: {filename}")
            except Exception as e:
                logger.error(f"Error loading knowledge file {file_path}: {e}")
    
    def query(self, question: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Query the knowledge base for relevant information.
        
        This is a simplified implementation. In a production system, you would use
        more sophisticated retrieval methods like semantic search, embeddings, etc.
        
        Args:
            question: The user's question
            
        Returns:
            Tuple containing:
            - A string with the best answer if found, or a message indicating no information
            - A list of relevant context snippets that can be used for AI response generation
        """
        logger.info(f"Querying knowledge base for: {question[:50]}...")
        
        # Simple keyword matching for now
        keywords = self._extract_keywords(question)
        context = []
        
        # Search in organizer knowledge first (higher priority)
        organizer_context = self._search_data(self.organizer_data, keywords)
        if organizer_context:
            context.extend(organizer_context)
            
        # If not enough context, search in GitBook knowledge
        if len(context) < 3:  # Arbitrary threshold
            gitbook_context = self._search_data(self.gitbook_data, keywords)
            if gitbook_context:
                context.extend(gitbook_context)
                
        # Finally, check feedback knowledge
        feedback_context = self._search_data(self.feedback_data, keywords)
        if feedback_context:
            context.extend(feedback_context)
            
        if not context:
            return "I don't have specific information about that in my knowledge base.", []
            
        return "Found relevant information in the knowledge base.", context
        
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract important keywords from a question.
        
        This is a simple implementation that removes common words.
        In a production system, you might use NLP techniques for keyword extraction.
        
        Args:
            text: The text to extract keywords from
            
        Returns:
            List of keywords
        """
        # Convert to lowercase and split
        words = text.lower().split()
        
        # Common words to ignore
        stop_words = {
            "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
            "how", "when", "where", "who", "will", "is", "are", "am", "i", "to",
            "in", "on", "at", "by", "for", "with", "about", "do", "does", "did"
        }
        
        # Filter out stop words and short words
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        logger.debug(f"Extracted keywords: {keywords}")
        return keywords
        
    def _search_data(self, data: Dict[str, Any], keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Search through data using keywords.
        
        Args:
            data: Dictionary of data to search
            keywords: List of keywords to search for
            
        Returns:
            List of relevant context snippets
        """
        results = []
        
        for filename, content in data.items():
            content_str = json.dumps(content) if isinstance(content, dict) else str(content)
            content_lower = content_str.lower()
            
            # Count keyword matches
            match_count = sum(1 for keyword in keywords if keyword in content_lower)
            
            if match_count > 0:
                # Create a snippet with the relevant section
                # In a real system, you'd extract the most relevant paragraph
                if len(content_str) > 500:
                    snippet = content_str[:500] + "..."
                else:
                    snippet = content_str
                    
                results.append({
                    "source": filename,
                    "relevance": match_count,
                    "content": snippet
                })
                
        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)
        
        # Limit to top 5 results
        return results[:5]
        
    def add_feedback(self, question: str, answer: str, feedback: str) -> bool:
        """
        Add user feedback to the feedback knowledge base.
        
        Args:
            question: The original question
            answer: The bot's answer
            feedback: User's feedback
            
        Returns:
            Boolean indicating success
        """
        logger.info(f"Adding feedback for question: {question[:50]}...")
        
        try:
            # Create a unique filename based on timestamp
            import time
            timestamp = int(time.time())
            filename = f"feedback_{timestamp}.json"
            filepath = os.path.join(self.feedback_path, filename)
            
            # Ensure feedback directory exists
            os.makedirs(self.feedback_path, exist_ok=True)
            
            # Create feedback entry
            feedback_entry = {
                "question": question,
                "answer": answer,
                "feedback": feedback,
                "timestamp": timestamp
            }
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(feedback_entry, f, indent=2)
                
            # Update in-memory data
            self.feedback_data[filename] = feedback_entry
            
            logger.info(f"Feedback saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
            return False

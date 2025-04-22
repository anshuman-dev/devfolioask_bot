import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
import re

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
        gitbook_files = self._load_directory_data(self.gitbook_path, self.gitbook_data)
        logger.info(f"Loaded {len(gitbook_files)} GitBook files: {gitbook_files}")
        
        # Load organizer knowledge
        organizer_files = self._load_directory_data(self.organizer_path, self.organizer_data)
        logger.info(f"Loaded {len(organizer_files)} organizer files: {organizer_files}")
        
        # Load feedback knowledge
        feedback_files = self._load_directory_data(self.feedback_path, self.feedback_data)
        logger.info(f"Loaded {len(feedback_files)} feedback files: {feedback_files}")
        
        logger.info(f"Knowledge base loaded: {len(self.gitbook_data)} GitBook files, " 
                   f"{len(self.organizer_data)} organizer files, "
                   f"{len(self.feedback_data)} feedback files")
        
    def _load_directory_data(self, directory: str, data_dict: Dict[str, Any]) -> List[str]:
        """
        Load all JSON and text files from a directory into a dictionary.
        
        Args:
            directory: Path to the directory containing knowledge files
            data_dict: Dictionary to store the loaded data
            
        Returns:
            List of loaded filenames
        """
        loaded_files = []
        
        if not os.path.exists(directory):
            logger.warning(f"Knowledge directory does not exist: {directory}")
            return loaded_files
            
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
                    loaded_files.append(filename)
                elif filename.endswith('.txt') or filename.endswith('.md'):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data_dict[filename] = f.read()
                    loaded_files.append(filename)
                else:
                    logger.debug(f"Skipping unsupported file type: {filename}")
            except Exception as e:
                logger.error(f"Error loading knowledge file {file_path}: {e}")
                
        return loaded_files
    
    def query(self, question: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Query the knowledge base for relevant information.
        
        Args:
            question: The user's question
            
        Returns:
            Tuple containing:
            - A string with the best answer if found, or a message indicating no information
            - A list of relevant context snippets that can be used for AI response generation
        """
        logger.info(f"Querying knowledge base for: {question[:50]}...")
        
        # Extract keywords from the question
        keywords = self._extract_keywords(question)
        logger.info(f"Extracted keywords: {keywords}")
        
        # Initialize context list
        context = []
        
        # First, look for exact keyword matches in all data sources
        # Prioritize organizer knowledge
        logger.debug("Searching organizer knowledge...")
        organizer_context = self._search_data(self.organizer_data, keywords, question)
        if organizer_context:
            context.extend(organizer_context)
            
        # Then search in GitBook knowledge
        logger.debug("Searching GitBook knowledge...")
        gitbook_context = self._search_data(self.gitbook_data, keywords, question)
        if gitbook_context:
            # Prioritize GitBook entries with high relevance
            high_relevance_entries = [entry for entry in gitbook_context if entry["relevance"] > 1]
            if high_relevance_entries:
                context.extend(high_relevance_entries)
            else:
                context.extend(gitbook_context[:2])  # Limit to top 2 if not highly relevant
                
        # Finally, check feedback knowledge
        logger.debug("Searching feedback knowledge...")
        feedback_context = self._search_data(self.feedback_data, keywords, question)
        if feedback_context:
            context.extend(feedback_context)
            
        # Sort all context by relevance
        context.sort(key=lambda x: x["relevance"], reverse=True)
        
        # Log what we found
        logger.info(f"Found {len(context)} relevant context items")
        for i, item in enumerate(context[:3], 1):  # Log top 3 for debugging
            logger.info(f"Context {i}: {item['source']} (relevance: {item['relevance']})")
            
        if not context:
            return "I don't have specific information about that in my knowledge base.", []
            
        return "Found relevant information in the knowledge base.", context[:5]  # Limit to top 5
        
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract important keywords from a question.
        
        Args:
            text: The text to extract keywords from
            
        Returns:
            List of keywords
        """
        # Convert to lowercase and split
        words = re.findall(r'\w+', text.lower())
        
        # Common words to ignore
        stop_words = {
            "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
            "how", "when", "where", "who", "will", "is", "are", "am", "i", "to",
            "in", "on", "at", "by", "for", "with", "about", "do", "does", "did",
            "should", "can", "could", "would", "might", "may", "there", "these",
            "those", "this", "that", "then", "than", "such", "so", "some", "my",
            "your", "our", "their"
        }
        
        # Filter out stop words and short words
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Add composite keywords based on the question
        question_lower = text.lower()
        
        # Domain-specific composite keywords
        composite_keywords = [
            "judging mode", "judging criteria", "online judging", "offline judging",
            "sponsor judging", "judge", "judges", "adding judges", "judging process",
            "organizer", "organizers", "hackathon", "devfolio", "evaluation",
            "prerequisites", "scoring", "dashboard"
        ]
        
        for phrase in composite_keywords:
            if phrase in question_lower:
                keywords.append(phrase)
        
        return keywords
        
    def _search_data(self, data: Dict[str, Any], keywords: List[str], original_question: str) -> List[Dict[str, Any]]:
        """
        Search through data using keywords.
        
        Args:
            data: Dictionary of data to search
            keywords: List of keywords to search for
            original_question: The original question for context matching
            
        Returns:
            List of relevant context snippets
        """
        results = []
        original_question_lower = original_question.lower()
        
        for filename, content in data.items():
            # Extract the actual content string based on type
            if isinstance(content, dict):
                # If it's a structured knowledge file
                content_str = content.get("content", "")
                # Also check title and keywords
                title = content.get("title", "")
                content_keywords = content.get("keywords", [])
                
                # Extra boost for matching titles and keywords
                title_keyword_boost = 0
                for keyword in keywords:
                    if keyword in title.lower():
                        title_keyword_boost += 2  # Higher boost for title matches
                    if any(keyword in k.lower() for k in content_keywords):
                        title_keyword_boost += 1
            else:
                # Plain string content
                content_str = str(content)
                title_keyword_boost = 0
            
            content_lower = content_str.lower()
            
            # Count keyword matches
            keyword_match_count = sum(1 for keyword in keywords if keyword in content_lower)
            
            # Direct phrase matches from the question get extra weight
            phrase_match_boost = 0
            for i in range(2, 6):  # Check phrases of length 2-5 words
                phrases = self._extract_ngrams(original_question_lower, i)
                for phrase in phrases:
                    if phrase in content_lower and len(phrase) > 5:  # Only meaningful phrases
                        phrase_match_boost += 1
            
            total_relevance = keyword_match_count + title_keyword_boost + phrase_match_boost
            
            if total_relevance > 0:
                # Create a context item with source, content and relevance score
                source_name = filename
                if isinstance(content, dict) and "title" in content:
                    source_name = content["title"]
                
                # Create excerpt for context
                excerpt = self._create_excerpt(content_str, keywords, original_question_lower)
                
                results.append({
                    "source": source_name,
                    "relevance": total_relevance,
                    "content": excerpt
                })
                
        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)
        
        # Limit to top 5 results
        return results[:5]
    
    def _extract_ngrams(self, text: str, n: int) -> List[str]:
        """Extract n-grams from text"""
        words = text.split()
        return [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]
    
    def _create_excerpt(self, content: str, keywords: List[str], question: str) -> str:
        """Create a relevant excerpt from content based on keywords and question"""
        # If content is already reasonably sized, return it all
        if len(content) < 2000:
            return content
            
        # Otherwise, look for the most relevant part
        paragraphs = re.split(r'\n\n+', content)
        scored_paragraphs = []
        
        for para in paragraphs:
            # Skip very short paragraphs
            if len(para) < 20:
                continue
                
            # Score based on keyword matches
            score = sum(1 for keyword in keywords if keyword in para.lower())
            
            # Additional score for question terms
            question_words = question.split()
            score += sum(0.5 for word in question_words if len(word) > 3 and word in para.lower())
            
            scored_paragraphs.append((para, score))
            
        # Sort by score
        scored_paragraphs.sort(key=lambda x: x[1], reverse=True)
        
        # Take top 3 paragraphs, preserving their original order
        top_paras = sorted(
            [p for p, s in scored_paragraphs[:3]], 
            key=lambda p: content.index(p)
        )
        
        # Join and return
        return "\n\n".join(top_paras)
        
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

import logging
import re
from typing import List, Dict, Tuple, Any

logger = logging.getLogger(__name__)

class QueryProcessor:
    """Advanced query processing for better knowledge base matching"""
    
    @staticmethod
    def extract_topic_keywords(query: str) -> List[str]:
        """Extract topic-specific keywords for better matching"""
        # Normalize query
        query = query.lower().strip()
        
        # Specific domain patterns to identify key topics
        topic_patterns = {
            'judging_criteria': [r'judging criteria', r'criteria for judging', r'scoring criteria', 
                               r'evaluation criteria', r'modify criteria', r'change criteria',
                               r'update criteria', r'customize criteria'],
            'invite_judges': [r'invite judges', r'add judges', r'adding judges', r'send invitation',
                            r'judge invitation', r'how to invite', r'invite a judge'],
            'judging_process': [r'judging process', r'how judging works', r'judge projects', 
                              r'how to judge', r'judging dashboard'],
            'judging_modes': [r'judging modes', r'judging mode', r'online judging', 
                            r'offline judging', r'sponsor judging', r'which mode'],
        }
        
        # Check for matches
        matched_topics = []
        for topic, patterns in topic_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query):
                    matched_topics.append(topic)
                    break
        
        # Extract additional keywords
        additional_keywords = []
        words = query.split()
        for word in words:
            if len(word) > 3 and word not in ['what', 'when', 'where', 'which', 'this', 'that', 'have', 'need', 'want']:
                additional_keywords.append(word)
        
        return matched_topics + additional_keywords
    
    @staticmethod
    def preprocess_query(query: str) -> str:
        """Clean up query for better matching"""
        # Remove mentions
        query = re.sub(r'@\w+', '', query)
        # Remove common filler words
        query = re.sub(r'\b(hey|hi|hello|please|thanks|thank you)\b', '', query)
        # Remove extra spaces
        query = re.sub(r'\s+', ' ', query).strip()
        return query

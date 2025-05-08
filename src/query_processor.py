import re
import logging
from typing import Dict, List, Any, Optional
from src.intent_classifier import IntentClassifier
from src.semantic_matcher import SemanticMatcher

logger = logging.getLogger(__name__)

class QueryProcessor:
    """
    Processes user queries through a pipeline to extract intent,
    entities, and semantically relevant scenarios.
    """
    
    def __init__(self, semantic_matcher: SemanticMatcher):
        """
        Initialize the query processor.
        
        Args:
            semantic_matcher: Initialized SemanticMatcher instance
        """
        self.semantic_matcher = semantic_matcher
        self.intent_classifier = IntentClassifier()
        
    def process(self, raw_query: str, conversation_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a raw query through the full pipeline.
        
        Args:
            raw_query: User's original query
            conversation_context: Optional conversation history
            
        Returns:
            Dictionary with processed query info
        """
        logger.info(f"Processing query: {raw_query[:50]}...")
        
        # Step 1: Clean and normalize the query
        cleaned_query = self._clean_query(raw_query)
        
        # Step 2: Classify intent
        intent, intent_confidence = self.intent_classifier.classify(cleaned_query, conversation_context)
        logger.info(f"Classified intent: {intent} (confidence: {intent_confidence:.2f})")
        
        # Step 3: Extract entities 
        entities = self._extract_entities(cleaned_query)
        
        # Step 4: Find semantically relevant scenarios
        relevant_scenarios = []
        if intent not in [IntentClassifier.GREETING_INTENT]:  # Skip for greetings
            scenario_matches = self.semantic_matcher.find_matching_scenarios(cleaned_query, top_k=3)
            relevant_scenarios = [(scenario, score) for scenario, score in scenario_matches]
            
        # Step 5: Process follow-up if needed
        previous_scenario = None
        if intent == IntentClassifier.FOLLOWUP_INTENT and conversation_context:
            previous_scenario = self._find_previous_scenario(conversation_context)
        
        # Construct the processed result
        result = {
            "original_query": raw_query,
            "cleaned_query": cleaned_query,
            "intent": {
                "type": intent,
                "confidence": intent_confidence
            },
            "entities": entities,
            "relevant_scenarios": relevant_scenarios,
            "is_followup": intent == IntentClassifier.FOLLOWUP_INTENT,
            "previous_scenario": previous_scenario
        }
        
        return result
    
    def _clean_query(self, query: str) -> str:
        """
        Clean and normalize a query.
        
        Args:
            query: Raw query string
            
        Returns:
            Cleaned query string
        """
        # Remove bot mentions if present
        query = re.sub(r'@\w+', '', query)
        
        # Remove extra whitespace
        query = re.sub(r'\s+', ' ', query).strip()
        
        # Fix common typos and abbreviations
        replacements = {
            "devofilo": "devfolio",
            "judgement": "judging",
            "hackaton": "hackathon",
            "cant": "can't",
            "doesnt": "doesn't",
            "isnt": "isn't",
            "im": "I'm"
        }
        
        for old, new in replacements.items():
            query = re.sub(r'\b' + old + r'\b', new, query, flags=re.IGNORECASE)
            
        return query
        
    def _extract_entities(self, query: str) -> Dict[str, Any]:
        """
        Extract named entities from a query.
        
        Args:
            query: Cleaned query string
            
        Returns:
            Dictionary of extracted entities
        """
        entities = {}
        
        # Extract hackathon name if present
        hackathon_match = re.search(r'for\s+(?:the\s+)?([A-Za-z0-9\s]+(?:hackathon|event|competition))', query, re.IGNORECASE)
        if hackathon_match:
            entities["hackathon_name"] = hackathon_match.group(1).strip()
            
        # Extract judging mode if mentioned
        if "online judging" in query.lower():
            entities["judging_mode"] = "online"
        elif "offline judging" in query.lower():
            entities["judging_mode"] = "offline"
        elif "sponsor judging" in query.lower():
            entities["judging_mode"] = "sponsor"
            
        # Extract other entity types as needed
        # ...
        
        return entities
        
    def _find_previous_scenario(self, conversation_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find the previously discussed scenario from conversation context.
        
        Args:
            conversation_context: Conversation history
            
        Returns:
            Previous scenario if found, None otherwise
        """
        if not conversation_context or "recent_answers" not in conversation_context:
            return None
            
        # Get the most recent response
        last_answer = conversation_context["recent_answers"][-1]
        
        # Look for scenario titles in the last answer
        for scenario in self.semantic_matcher.scenarios:
            if scenario["title"].lower() in last_answer.lower():
                return scenario
                
        return None
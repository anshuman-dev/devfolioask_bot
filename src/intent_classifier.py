import re
import logging
from typing import Dict, List, Tuple, Any, Optional

logger = logging.getLogger(__name__)

class IntentClassifier:
    """
    Classifies user queries into different intents to better understand user's goals.
    Currently uses rule-based classification with pattern matching.
    """
    
    # Intent types
    QUESTION_INTENT = "question"
    GREETING_INTENT = "greeting"
    PROBLEM_INTENT = "problem"
    FEEDBACK_INTENT = "feedback"
    CLARIFICATION_INTENT = "clarification"
    FOLLOWUP_INTENT = "followup"
    
    def __init__(self):
        """Initialize the intent classifier with predefined patterns."""
        # Compile regex patterns for each intent
        self.intent_patterns = {
            self.GREETING_INTENT: [
                r'^hi\b', r'^hello\b', r'^hey\b', r'^greetings', r'^howdy\b',
                r'^good morning', r'^good afternoon', r'^good evening'
            ],
            self.QUESTION_INTENT: [
                r'^how do I', r'^how can I', r'^how to', r'^what is', r'^where is',
                r'^when', r'^why', r'^which', r'^who', r'^can I', r'^is there',
                r'^tell me about', r'\?$'
            ],
            self.PROBLEM_INTENT: [
                r'not working', r'issue', r'problem', r'error', r'can\'t', r'cannot',
                r'doesn\'t work', r'failed', r'stuck', r'not able to', r'trouble',
                r'having difficulty', r'not showing', r'bug', r'broken'
            ],
            self.FEEDBACK_INTENT: [
                r'feedback', r'suggest', r'opinion', r'review', r'thoughts',
                r'what do you think', r'rate', r'evaluate'
            ],
            self.CLARIFICATION_INTENT: [
                r'what do you mean', r'don\'t understand', r'unclear', r'confused',
                r'explain', r'clarify', r'elaborate', r'more detail'
            ],
            self.FOLLOWUP_INTENT: [
                r'^but ', r'^and ', r'^so ', r'^what about', r'^how about',
                r'^then ', r'^also ', r'^what if', r'^actually', r'^now ',
                r'^ok(ay)? but', r'^no, I meant'
            ]
        }
        
        # Compile all patterns
        self.compiled_patterns = {}
        for intent, patterns in self.intent_patterns.items():
            self.compiled_patterns[intent] = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            
    def classify(self, query: str, conversation_context: Optional[Dict[str, Any]] = None) -> Tuple[str, float]:
        """
        Classify the intent of a user query.
        
        Args:
            query: The user's query
            conversation_context: Optional context from previous interactions
            
        Returns:
            Tuple containing (intent_type, confidence_score)
        """
        # Check for contextual follow-up indicators
        is_likely_followup = False
        if conversation_context and len(conversation_context.get("recent_questions", [])) > 0:
            # Detect likely follow-ups based on length and pronouns
            if (len(query.split()) <= 5 or 
                any(pronoun in query.lower().split() for pronoun in ["it", "they", "them", "that", "those", "these"])):
                is_likely_followup = True
        
        # Score each intent type
        intent_scores = {}
        for intent, patterns in self.compiled_patterns.items():
            # Count matches for this intent
            match_count = sum(1 for pattern in patterns if pattern.search(query))
            
            # Calculate score (0-1)
            score = min(1.0, match_count / max(1, len(patterns) * 0.3))  # Scale appropriately
            
            # Boost follow-up score if contextually likely
            if intent == self.FOLLOWUP_INTENT and is_likely_followup:
                score = max(score, 0.7)  # Minimum confidence of 0.7 for likely follow-ups
                
            intent_scores[intent] = score
            
        # Find the highest scoring intent
        best_intent = max(intent_scores.items(), key=lambda x: x[1])
        
        # Default to question intent if no clear match
        if best_intent[1] < 0.2:
            return self.QUESTION_INTENT, 0.5
            
        return best_intent
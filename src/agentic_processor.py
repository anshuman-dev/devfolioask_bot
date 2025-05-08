import logging
import re
import time
from typing import Dict, List, Any, Tuple, Optional

from src.knowledge import KnowledgeBase
from src.scenario_knowledge import ScenarioKnowledgeBase
from src.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

class AgenticProcessor:
    """
    Integrates the scenario-based knowledge with OpenAI processing
    to provide more intelligent, contextual responses.
    """
    
    def __init__(self):
        self.knowledge_base = KnowledgeBase()
        self.scenario_kb = ScenarioKnowledgeBase()
        self.openai_client = OpenAIClient()
        
    # In src/agentic_processor.py, enhance process_question

    async def process_question(self, question: str, user_id: str = None, chat_id: str = None, 
                        bot = None, conversation_context: Dict[str, Any] = None) -> Tuple[str, str]:
        # Existing code...
        
        # Determine if this is a follow-up question based on conversation context
        is_followup = False
        previous_scenario_id = None
        if conversation_context and conversation_context.get("recent_questions", []):
            # Check if this question seems like a follow-up
            prev_question = conversation_context["recent_questions"][-1]
            prev_answer = conversation_context["recent_answers"][-1]
            
            # Check for follow-up indicators
            if (len(question) < 60 and any(word in question.lower() for word in 
                                        ["they", "it", "that", "those", "these", "their"]) or
            "what about" in question.lower() or
            "how about" in question.lower() or
            not any(word in question.lower() for word in ["how", "what", "where", "when", "who"]) or
            "no, I meant" in question.lower()):
                is_followup = True
                
                # Try to find the previous scenario ID if available
                for scenario in self.scenario_kb.scenarios:
                    if scenario["title"].lower() in prev_answer.lower():
                        previous_scenario_id = scenario["scenario_id"]
                        break
        
        # If this is a follow-up and we have previous scenario, prioritize that
        if is_followup and previous_scenario_id:
            scenario = self.scenario_kb.get_scenario_by_id(previous_scenario_id)
            if scenario:
                # Generate a follow-up specific response
                variables = self._extract_variables_from_question(question, scenario)
                answer = self.scenario_kb.render_scenario_response(
                    scenario, variables, question=question, is_followup=True
                )
                return answer, None
                
        # Rest of the method remains the same...
            
    def _is_greeting(self, text: str) -> bool:
        """Check if message is a simple greeting."""
        greetings = ["hi", "hello", "hey", "hola", "namaste", "greetings", "yo", "hiya", "howdy", "hii", "hiii", "hiiii"]
        text_lower = text.lower().strip()
        
        # Check if the text is just a greeting
        for greeting in greetings:
            if text_lower == greeting or text_lower.startswith(greeting + " ") or text_lower.endswith(" " + greeting):
                return True
                
        # Check common greeting patterns like "hi there", "hello everyone"
        common_patterns = [
            r'^hi\s+\w+$',
            r'^hello\s+\w+$',
            r'^hey\s+\w+$',
            r'^hi+$',  # Matches "hiii", "hiiiiii", etc.
        ]
        
        for pattern in common_patterns:
            if re.match(pattern, text_lower):
                return True
                
        return False
        
    def _get_greeting_response(self) -> str:
        """Generate a greeting response."""
        greetings = [
            "Hello! I'm DevfolioAsk Bot, your assistant for Devfolio platform questions. How can I help you today?",
            "Hi there! I'm here to answer your questions about the Devfolio platform. What would you like to know?",
            "Hey! I'm DevfolioAsk Bot. I can provide information about Devfolio's features, including hackathon setup, judging, submissions, and more. What can I help you with?",
            "Greetings! I'm your Devfolio assistant bot. How can I assist you with your hackathon organization needs?",
            "Hello! I'm here to help with your Devfolio questions. Feel free to ask me about setting up hackathons, judging, or other platform features."
        ]
        
        import random
        return random.choice(greetings)
        
    def _format_conversation_context(self, conversation_context: Dict[str, Any]) -> str:
        """Format conversation context for OpenAI prompt."""
        context_info = ""
        
        # Add judging mode preference if available
        if "judging_mode_preference" in conversation_context and conversation_context["judging_mode_preference"]:
            context_info += f"The user has previously shown interest in {conversation_context['judging_mode_preference']} judging. "
        
        # Add recent conversation history for context
        if "recent_questions" in conversation_context and conversation_context["recent_questions"]:
            context_info += "Recent conversation history: "
            num_history = min(3, len(conversation_context["recent_questions"]))
            for i in range(num_history):
                context_info += f"User: {conversation_context['recent_questions'][-(i+1)]} | Bot: {conversation_context['recent_answers'][-(i+1)]} "
                
        return context_info
        
    def _extract_variables_from_question(self, question: str, scenario: Dict[str, Any]) -> Dict[str, str]:
        """Extract dynamic variables from the question based on scenario needs."""
        variables = {}
        
        # This is a placeholder implementation. In a real system, you would:
        # 1. Analyze the scenario template to identify required variables
        # 2. Use pattern matching or NLP to extract those values from the question
        # 3. Provide default values for any missing variables
        
        # For demonstration, we'll just handle a "hackathon_name" variable
        if "hackathon_name" in scenario.get("required_variables", []):
            # Try to extract a hackathon name using regex
            match = re.search(r'for\s+(?:the\s+)?([A-Za-z0-9\s]+hackathon)', question, re.IGNORECASE)
            if match:
                variables["hackathon_name"] = match.group(1)
            else:
                variables["hackathon_name"] = "your hackathon"
                
        return variables
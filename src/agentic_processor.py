import logging
import re
import time
from typing import Dict, List, Any, Tuple, Optional

from src.knowledge import KnowledgeBase
from src.scenario_knowledge import ScenarioKnowledgeBase
from src.openai_client import OpenAIClient
from src.semantic_matcher import SemanticMatcher
from src.query_processor import QueryProcessor

logger = logging.getLogger(__name__)

class AgenticProcessor:
    """
    Integrates the scenario-based knowledge with OpenAI processing
    to provide more intelligent, contextual responses.
    """
    
    def __init__(self):
        # In __init__ method
        """Initialize the agentic processor with necessary components."""
        self.knowledge_base = KnowledgeBase()
        self.scenario_kb = ScenarioKnowledgeBase()
        self.openai_client = OpenAIClient()
        
        # Initialize semantic matching components
        self.semantic_matcher = SemanticMatcher(self.scenario_kb.scenarios)
        self.query_processor = QueryProcessor(self.semantic_matcher)
        
        # Initialize the agent
        self.agent = DevfolioAgent(
            knowledge_base=self.knowledge_base,
            scenario_kb=self.scenario_kb,
            openai_client=self.openai_client,
            semantic_matcher=self.semantic_matcher,
            query_processor=self.query_processor
        )

# Then replace process_question with this
    async def process_question(self, question: str, user_id: str = None, 
                        chat_id: str = None, 
                        bot = None, 
                        conversation_context: Dict[str, Any] = None) -> Tuple[str, str]:
        """
        Process a question using the agent's reasoning capabilities.
        
        Args:
            question: The user's question
            user_id: The user's Telegram ID for tracking interactions
            chat_id: Chat ID for sending typing indicators
            bot: Bot instance for sending typing indicators
            conversation_context: Previous conversation context
            
        Returns:
            A tuple of (answer, interaction_id)
        """
        try:
            # Show typing indicator if chat_id and bot are provided
            if chat_id and bot:
                await bot.send_chat_action(chat_id=chat_id, action="typing")
            
            # Process the question through the agent
            answer, executed_plan = await self.agent.process_query(question, conversation_context)
            
            # For debugging, log the plan type that was executed
            if executed_plan:
                logger.info(f"Executed plan type: {executed_plan.get('type')}")
            
            interaction_id = None
            return answer, interaction_id
            
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            return f"I'm sorry, I encountered an error while generating a response. Please try again later.", None
            
    
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
    
    def _extract_variables_from_processed_query(self, processed_query: Dict[str, Any], 
                                           scenario: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract dynamic variables from processed query with entity recognition.
        
        Args:
            processed_query: The processed query with entities
            scenario: The scenario to extract variables for
            
        Returns:
            Dictionary of extracted variables
        """
        variables = {}
        
        # Use extracted entities if available
        if "entities" in processed_query and processed_query["entities"]:
            entities = processed_query["entities"]
            
            # Map common entity types to variables
            if "hackathon_name" in entities:
                variables["hackathon_name"] = entities["hackathon_name"]
                
            if "judging_mode" in entities:
                variables["judging_mode"] = entities["judging_mode"]
                
        # Fall back to regex for any missing required variables
        if "required_variables" in scenario:
            for var_name in scenario["required_variables"]:
                if var_name not in variables:
                    # Try to extract using regex patterns
                    if var_name == "hackathon_name" and "hackathon_name" not in variables:
                        match = re.search(r'for\s+(?:the\s+)?([A-Za-z0-9\s]+hackathon)', 
                                       processed_query["cleaned_query"], re.IGNORECASE)
                        if match:
                            variables["hackathon_name"] = match.group(1)
                        else:
                            variables["hackathon_name"] = "your hackathon"
                            
        return variables
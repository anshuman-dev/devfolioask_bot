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
        
    async def process_question(self, question: str, user_id: str = None, chat_id: str = None, 
                         bot = None, conversation_context: Dict[str, Any] = None) -> Tuple[str, str]:
        """
        Process a question using scenario-based knowledge and OpenAI.
        
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
            
            # Handle simple greetings specially
            if self._is_greeting(question) or question == "greeting":
                logger.info(f"Detected greeting: {question}")
                # Return a random greeting response
                return self._get_greeting_response(), None
                
            # Step 1: Try to find matching scenario first
            scenario, confidence, related_scenarios = self.scenario_kb.query(question)
            
            # Step 2: If we have a good scenario match, use it directly
            if scenario and confidence > 0.7:
                logger.info(f"Found high-confidence scenario match: {scenario['title']} ({confidence:.2f})")
                
                # Extract dynamic variables from question if needed
                variables = self._extract_variables_from_question(question, scenario)
                
                # Generate response from scenario template
                answer = self.scenario_kb.render_scenario_response(scenario, variables)
                
                # If we have related scenarios, mention them
                if related_scenarios and len(related_scenarios) > 0:
                    related_info = "\n\nRelated topics you might find helpful:\n"
                    for related in related_scenarios[:2]:  # Limit to 2
                        related_info += f"- {related['title']}\n"
                    answer += related_info
                    
                interaction_id = None
                if user_id:
                    # TODO: Store the interaction for potential feedback
                    pass
                    
                return answer, interaction_id
                
            # Step 3: If we have a medium-confidence match, use it as context for OpenAI
            elif scenario and confidence > 0.4:
                logger.info(f"Found medium-confidence scenario match: {scenario['title']} ({confidence:.2f})")
                
                # Create context from scenario + traditional knowledge base
                scenario_context = f"Scenario: {scenario['title']}\n\n"
                
                # Include the template and components
                if "answer_template" in scenario:
                    scenario_context += f"Template: {scenario['answer_template']}\n\n"
                    
                if "answer_components" in scenario:
                    components = scenario["answer_components"]
                    if "steps" in components and components["steps"]:
                        scenario_context += "Steps:\n" + "\n".join([f"- {step}" for step in components["steps"]]) + "\n\n"
                    if "notes" in components and components["notes"]:
                        scenario_context += f"Notes: {components['notes']}\n\n"
                    if "common_issues" in components and components["common_issues"]:
                        scenario_context += f"Common issues: {components['common_issues']}\n\n"
                
                # Get additional context from traditional KB as fallback
                _, knowledge_context = self.knowledge_base.query(question)
                
                # Combine contexts for OpenAI
                context_info = ""
                if conversation_context:
                    context_info = self._format_conversation_context(conversation_context)
                
                # Generate response using OpenAI
                custom_context = [{"source": "Scenario Match", "content": scenario_context}]
                if knowledge_context:
                    custom_context.extend(knowledge_context)
                    
                answer = await self.openai_client.generate_response(question, custom_context, context_info)
                
                interaction_id = None
                if user_id:
                    # TODO: Store the interaction for potential feedback
                    pass
                    
                return answer, interaction_id
                
            # Step 4: Fallback to traditional knowledge base + OpenAI
            else:
                logger.info(f"No good scenario match, using traditional knowledge base")
                
                # Create context string from conversation context if available
                context_info = ""
                if conversation_context:
                    context_info = self._format_conversation_context(conversation_context)
                
                # Query the knowledge base for relevant information
                _, knowledge_context = self.knowledge_base.query(question)
                
                # Generate response using OpenAI
                if knowledge_context:
                    answer = await self.openai_client.generate_response(question, knowledge_context, context_info)
                else:
                    answer = await self.openai_client.generate_response(
                        question, 
                        [{"source": "No specific source", "content": "No specific information found in the knowledge base."}],
                        context_info
                    )
                
                interaction_id = None
                if user_id:
                    # TODO: Store the interaction for potential feedback
                    pass
                    
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
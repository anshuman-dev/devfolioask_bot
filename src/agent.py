import logging
import json
from typing import Dict, List, Any, Tuple, Optional

from src.knowledge import KnowledgeBase
from src.scenario_knowledge import ScenarioKnowledgeBase
from src.openai_client import OpenAIClient
from src.semantic_matcher import SemanticMatcher
from src.query_processor import QueryProcessor
from src.plan_executor import PlanExecutor

logger = logging.getLogger(__name__)

class DevfolioAgent:
    """
    Main agent class that orchestrates the reasoning and planning process
    for responding to user queries in an agentic way.
    """
    
    def __init__(self, knowledge_base: KnowledgeBase, 
                 scenario_kb: ScenarioKnowledgeBase,
                 openai_client: OpenAIClient,
                 semantic_matcher: SemanticMatcher = None,
                 query_processor: QueryProcessor = None):
        """
        Initialize the Devfolio Agent with required components.
        
        Args:
            knowledge_base: Knowledge base for retrieving information
            scenario_kb: Scenario-based knowledge base
            openai_client: OpenAI client for generating responses
            semantic_matcher: Optional semantic matcher
            query_processor: Optional query processor
        """
        self.knowledge_base = knowledge_base
        self.scenario_kb = scenario_kb
        self.openai_client = openai_client
        
        # Initialize or use provided semantic matcher
        if semantic_matcher:
            self.semantic_matcher = semantic_matcher
        else:
            self.semantic_matcher = SemanticMatcher(self.scenario_kb.scenarios)
            
        # Initialize or use provided query processor
        if query_processor:
            self.query_processor = query_processor
        else:
            self.query_processor = QueryProcessor(self.semantic_matcher)
            
        # Initialize plan executor
        self.plan_executor = PlanExecutor(
            knowledge_base=self.knowledge_base,
            scenario_kb=self.scenario_kb,
            openai_client=self.openai_client,
            semantic_matcher=self.semantic_matcher
        )
        
        logger.info("DevfolioAgent initialized with all components")
        
    async def process_query(self, query: str, user_id: str = None, 
                      conversation_context: Dict[str, Any] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Process a query using the agent's reasoning and planning capabilities.
        
        Args:
            query: The user's query
            user_id: User ID for tracking
            conversation_context: Conversation history and context
            
        Returns:
            Tuple containing (response, executed_plan)
        """
        logger.info(f"Agent processing query: {query[:50]}...")
        try:
            # Step 1: Understand the query
            processed_query = self.query_processor.process(query, conversation_context)
            logger.info(f"Query processed: intent={processed_query['intent']['type']}, "
                       f"is_followup={processed_query.get('is_followup', False)}")
            
            # Special case for greetings - no need for complex reasoning
            if processed_query['intent']['type'] == "greeting":
                return self._get_greeting_response(), {"type": "greeting"}
            
            # Step 2: Create a plan for answering the query
            plan = await self._create_plan(processed_query, conversation_context)
            logger.info(f"Plan created: {plan['type']}")
            
            # Step 3: Execute the plan
            execution_results = await self.plan_executor.execute_plan(plan, processed_query, conversation_context)
            logger.info(f"Plan executed with {len(execution_results.get('steps', []))} steps")
            
            # Step 4: Generate the final response
            response = await self._generate_response(execution_results, processed_query, conversation_context)
            
            # Return the response and the executed plan (for transparency/debugging)
            return response, plan
            
        except Exception as e:
            logger.error(f"Error in agent processing: {e}", exc_info=True)
            return f"I'm sorry, I experienced an error while processing your question. Please try again or rephrase your question.", {"type": "error", "error": str(e)}
            
    async def _create_plan(self, processed_query: Dict[str, Any], 
                     conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a plan for answering the query based on its content and context.
        
        Args:
            processed_query: The processed query data
            conversation_context: Conversation history and context
            
        Returns:
            Plan dictionary with steps to execute
        """
        # For follow-up questions with a clear previous scenario, use a simplified plan
        if processed_query.get('is_followup', False) and processed_query.get('previous_scenario'):
            return {
                "type": "followup_scenario",
                "scenario_id": processed_query['previous_scenario']['scenario_id'],
                "question": processed_query['cleaned_query']
            }
            
        # For high-confidence semantic matches, use a direct scenario plan
        if processed_query.get('relevant_scenarios') and len(processed_query['relevant_scenarios']) > 0:
            top_scenario, confidence = processed_query['relevant_scenarios'][0]
            if confidence > 0.75:
                return {
                    "type": "direct_scenario",
                    "scenario_id": top_scenario['scenario_id'],
                    "confidence": confidence,
                    "related_scenarios": [s['scenario_id'] for s, _ in processed_query['relevant_scenarios'][1:3]]
                }
                
        # For medium-confidence matches, use a hybrid plan
        if processed_query.get('relevant_scenarios') and len(processed_query['relevant_scenarios']) > 0:
            top_scenario, confidence = processed_query['relevant_scenarios'][0]
            if confidence > 0.5:
                return {
                    "type": "hybrid_scenario",
                    "primary_scenario_id": top_scenario['scenario_id'],
                    "confidence": confidence,
                    "related_scenarios": [s['scenario_id'] for s, _ in processed_query['relevant_scenarios'][1:3]],
                    "use_openai_enhancement": True
                }
                
        # For complex or unclear queries, use the reasoning plan with OpenAI
        # This is where the real reasoning shines
        reasoning_plan = await self.openai_client.create_plan(
            processed_query, 
            conversation_context
        )
        
        return reasoning_plan
        
    async def _generate_response(self, execution_results: Dict[str, Any], 
                          processed_query: Dict[str, Any],
                          conversation_context: Dict[str, Any]) -> str:
        """
        Generate the final response based on the execution results.
        
        Args:
            execution_results: Results from plan execution
            processed_query: The processed query
            conversation_context: Conversation context
            
        Returns:
            Formatted response string
        """
        # If the execution already generated a complete response, use it
        if "final_response" in execution_results:
            return execution_results["final_response"]
            
        # Otherwise, use the execution data to generate a response
        response_data = {
            "query": processed_query,
            "execution_results": execution_results,
            "context": conversation_context
        }
        
        # Generate a response using OpenAI
        response = await self.openai_client.generate_agent_response(response_data)
        return response
        
    def _get_greeting_response(self) -> str:
        """Generate a simple greeting response."""
        greetings = [
            "Hello! I'm DevfolioAsk Bot, your assistant for Devfolio platform questions. How can I help you today?",
            "Hi there! I'm here to answer your questions about the Devfolio platform. What would you like to know?",
            "Hey! I'm DevfolioAsk Bot. I can provide information about Devfolio's features, including hackathon setup, judging, submissions, and more. What can I help you with?",
            "Greetings! I'm your Devfolio assistant bot. How can I assist you with your hackathon organization needs?",
            "Hello! I'm here to help with your Devfolio questions. Feel free to ask me about setting up hackathons, judging, or other platform features."
        ]
        
        import random
        return random.choice(greetings)